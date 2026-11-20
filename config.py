"""Application configuration.

All secrets and environment-specific values come from environment variables
(or from a .env file in the project root). Nothing sensitive is hard-coded.
"""
import os
import secrets
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent      # .../backend
ROOT_DIR = BASE_DIR.parent                      # project root


def _load_env_file(path):
    """Tiny .env loader (KEY=VALUE per line) so no extra dependency is needed."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


_load_env_file(ROOT_DIR / ".env")
_load_env_file(BASE_DIR / ".env")


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _get_secret_key():
    """Use SECRET_KEY from the environment. If it is missing (local development
    only) generate a random key once and keep it in backend/instance/secret_key
    so that sessions survive restarts. The key is never committed to git."""
    key = os.environ.get("SECRET_KEY", "").strip()
    if key:
        return key
    instance_dir = BASE_DIR / "instance"
    instance_dir.mkdir(exist_ok=True)
    key_file = instance_dir / "secret_key"
    if key_file.is_file():
        stored = key_file.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    generated = secrets.token_hex(32)
    key_file.write_text(generated, encoding="utf-8")
    return generated


class Config:
    SECRET_KEY = _get_secret_key()
    DEBUG = _env_bool("FLASK_DEBUG", False)

    DATABASE = os.environ.get("DATABASE_PATH") or str(ROOT_DIR / "database" / "canteen.db")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or str(BASE_DIR / "uploads")
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024          # hard request limit (4 MB)
    MAX_IMAGE_BYTES = 2 * 1024 * 1024             # per uploaded image (2 MB)

    # Session / cookie security
    SESSION_COOKIE_NAME = "smart_canteen_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)  # set true behind HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Business settings
    TAX_RATE = _env_float("TAX_RATE", 0.05)        # 5 % GST by default
    CHEFS = _env_int("CANTEEN_CHEFS", 6)           # shown on the home page

    # CORS / origin checks. localhost / 127.0.0.1 on any port are allowed by
    # default (so the frontend can run on e.g. http://localhost:5500).
    CORS_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]

    # Serve the frontend from Flask too (same origin => simplest setup)
    FRONTEND_DIR = os.environ.get("FRONTEND_DIR") or str(ROOT_DIR / "frontend")
    SERVE_FRONTEND = _env_bool("SERVE_FRONTEND", True)

    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = _env_int("PORT", 5000)
