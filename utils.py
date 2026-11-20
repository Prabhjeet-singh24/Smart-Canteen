"""Shared helpers: JSON errors, auth decorators, validation, uploads, rate limiting."""
import functools
import re
import threading
import time
import uuid
from pathlib import Path

from flask import current_app, g, jsonify, request, session

from database import get_db


def error(message, status=400, details=None):
    body = {"error": message}
    if details:
        body["details"] = details
    return jsonify(body), status


def get_payload():
    """Return request data as a flat dict (JSON body or form fields)."""
    if request.is_json:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}
    if request.form:
        return request.form.to_dict()
    return {}


# ---------------------------------------------------------------- auth ----
def load_user():
    if "user" in g:
        return g.user
    g.user = None
    uid = session.get("user_id")
    if uid:
        row = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if row is not None and row["is_active"]:
            g.user = row
        else:
            session.clear()
    return g.user


def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if load_user() is None:
            return error("Please log in to continue.", 401)
        return fn(*args, **kwargs)
    return wrapper


def role_required(role):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = load_user()
            if user is None:
                return error("Please log in to continue.", 401)
            if user["role"] != role:
                return error("You do not have permission to do that.", 403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


admin_required = role_required("admin")
customer_required = role_required("customer")


# ---------------------------------------------------------- validation ----
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?\d{10,13}$")
STUDENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-/]{2,19}$")
UPI_RE = re.compile(r"^[A-Za-z0-9._\-]{2,}@[A-Za-z]{2,}$")


def _clean(value, multiline=False):
    value = str(value).replace("\r\n", "\n").strip()
    allowed = "\n" if multiline else ""
    return "".join(ch for ch in value if ch.isprintable() or ch in allowed)


def v_text(data, key, label, errors, min_len=1, max_len=100, required=True, multiline=False):
    raw = data.get(key)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if required:
            errors[key] = "%s is required." % label
        return None
    if not isinstance(raw, (str, int, float)) or isinstance(raw, bool):
        errors[key] = "%s is invalid." % label
        return None
    value = _clean(raw, multiline)
    if len(value) < min_len:
        errors[key] = "%s must be at least %d characters." % (label, min_len)
        return None
    if len(value) > max_len:
        errors[key] = "%s must be at most %d characters." % (label, max_len)
        return None
    return value


def v_email(data, errors, key="email"):
    value = v_text(data, key, "Email", errors, max_len=120)
    if value is None:
        return None
    value = value.lower()
    if not EMAIL_RE.match(value):
        errors[key] = "Enter a valid email address."
        return None
    return value


def v_phone(data, errors, key="phone", required=True):
    value = v_text(data, key, "Phone number", errors, max_len=20, required=required)
    if value is None:
        return None
    value = re.sub(r"[\s\-()]", "", value)
    if not PHONE_RE.match(value):
        errors[key] = "Enter a valid phone number (10 to 13 digits)."
        return None
    return value


def v_student_id(data, errors, key="student_id", required=True):
    value = v_text(data, key, "Student ID", errors, max_len=20, required=required)
    if value is None:
        return None
    if not STUDENT_RE.match(value):
        errors[key] = "Student ID must be 3-20 letters, digits, '-' or '/'."
        return None
    return value.upper()


def v_password(data, key, errors, label="Password"):
    raw = data.get(key)
    if not isinstance(raw, str) or not raw:
        errors[key] = "%s is required." % label
        return None
    if len(raw) < 8:
        errors[key] = "%s must be at least 8 characters." % label
        return None
    if len(raw) > 128:
        errors[key] = "%s is too long." % label
        return None
    if not (re.search(r"[A-Za-z]", raw) and re.search(r"\d", raw)):
        errors[key] = "%s must contain at least one letter and one digit." % label
        return None
    return raw


def to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "on", "yes")


def to_int(value):
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, float) and not value.is_integer():
            return None
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def to_float(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def like_escape(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ------------------------------------------------------------- uploads ----
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


def _detect_image_type(head):
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:3] == b"\xff\xd8\xff":
        return "jpg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def save_image(file_storage, errors, key="image"):
    """Validate (extension, size, real file signature) and store an uploaded
    image under a random file name. Returns '/uploads/<name>' or None."""
    filename = file_storage.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        errors[key] = "Image must be a PNG, JPG, GIF or WEBP file."
        return None
    limit = current_app.config["MAX_IMAGE_BYTES"]
    data = file_storage.read(limit + 1)
    if len(data) > limit:
        errors[key] = "Image is too large (max %d MB)." % (limit // (1024 * 1024))
        return None
    if not data:
        errors[key] = "The image file is empty."
        return None
    kind = _detect_image_type(data[:16])
    if kind is None:
        errors[key] = "The uploaded file is not a valid image."
        return None
    name = "%s.%s" % (uuid.uuid4().hex, kind)
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)
    return "/uploads/" + name


def remove_image(url):
    """Delete a previously uploaded image (never touches bundled assets)."""
    if not url or not url.startswith("/uploads/"):
        return
    name = Path(url).name
    path = Path(current_app.config["UPLOAD_FOLDER"]) / name
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        current_app.logger.warning("Could not delete image %s", path)


# --------------------------------------------------------- rate limits ----
_attempts = {}
_lock = threading.Lock()


def is_locked(key, limit=5, window=600):
    now = time.time()
    with _lock:
        recent = [t for t in _attempts.get(key, []) if now - t < window]
        _attempts[key] = recent
        return len(recent) >= limit


def record_failure(key):
    with _lock:
        _attempts.setdefault(key, []).append(time.time())


def clear_failures(key):
    with _lock:
        _attempts.pop(key, None)


def reset_rate_limits():
    with _lock:
        _attempts.clear()
