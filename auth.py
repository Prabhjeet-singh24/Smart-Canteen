"""Authentication and profile endpoints."""
import sqlite3

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db
from models import user_to_dict
from utils import (clear_failures, error, get_payload, is_locked, load_user, login_required,
                   record_failure, reset_rate_limits, v_email, v_password, v_phone,
                   v_student_id, v_text)

bp = Blueprint("auth", __name__, url_prefix="/api")

HASH_METHOD = "pbkdf2:sha256:600000"
# Used to keep login timing similar when the e-mail does not exist.
_DUMMY_HASH = generate_password_hash("dummy-password-1", method="pbkdf2:sha256:600000")


def _unique_violation(exc):
    msg = str(exc).lower()
    if "users.email" in msg:
        return {"email": "An account with this email already exists."}
    if "student_id" in msg:
        return {"student_id": "This Student ID is already registered."}
    return {"email": "This account already exists."}


@bp.post("/register")
def register():
    data = get_payload()
    errors = {}
    name = v_text(data, "name", "Name", errors, min_len=2, max_len=60)
    email = v_email(data, errors)
    phone = v_phone(data, errors)
    student_id = v_student_id(data, errors)
    password = v_password(data, "password", errors)
    if password is not None and data.get("confirm_password") is not None \
            and data.get("confirm_password") != password:
        errors["confirm_password"] = "Passwords do not match."
    if errors:
        return error("Please correct the highlighted fields.", 400, errors)

    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (name, email, phone, student_id, password_hash, role) "
            "VALUES (?, ?, ?, ?, ?, 'customer')",
            (name, email, phone, student_id, generate_password_hash(password, method=HASH_METHOD)),
        )
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        return error("Registration failed.", 409, _unique_violation(exc))

    user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"message": "Account created successfully.", "user": user_to_dict(user)}), 201


@bp.post("/login")
def login():
    data = get_payload()
    email = str(data.get("email") or "").strip().lower()
    password = data.get("password")
    wanted_role = data.get("role")
    if not email or not isinstance(password, str) or not password:
        return error("Email and password are required.", 400)

    key = "%s|%s" % (request.remote_addr, email)
    if is_locked(key):
        return error("Too many failed attempts. Please try again in a few minutes.", 429)

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    good = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)
    if not user or not good or not user["is_active"] \
            or (wanted_role == "admin" and user["role"] != "admin"):
        record_failure(key)
        if user and good and not user["is_active"]:
            return error("This account has been disabled. Please contact the canteen office.", 403)
        return error("Invalid email or password.", 401)
    if wanted_role == "customer" and user["role"] == "admin":
        return error("Admin accounts must sign in from the admin login page.", 403)

    clear_failures(key)
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"message": "Logged in successfully.", "user": user_to_dict(user)})


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@bp.get("/profile")
@login_required
def get_profile():
    return jsonify({"user": user_to_dict(load_user())})


@bp.put("/profile")
@login_required
def update_profile():
    user = load_user()
    data = get_payload()
    errors = {}
    name = v_text(data, "name", "Name", errors, min_len=2, max_len=60)
    email = v_email(data, errors)
    phone = v_phone(data, errors)
    student_id = v_student_id(data, errors, required=user["role"] != "admin")
    if errors:
        return error("Please correct the highlighted fields.", 400, errors)
    db = get_db()
    try:
        db.execute("UPDATE users SET name=?, email=?, phone=?, student_id=? WHERE id=?",
                   (name, email, phone, student_id, user["id"]))
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        return error("Could not update profile.", 409, _unique_violation(exc))
    fresh = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return jsonify({"message": "Profile updated.", "user": user_to_dict(fresh)})


@bp.post("/change-password")
@login_required
def change_password():
    user = load_user()
    data = get_payload()
    errors = {}
    current = data.get("current_password")
    if not isinstance(current, str) or not current:
        errors["current_password"] = "Current password is required."
    new = v_password(data, "new_password", errors, "New password")
    if new is not None and data.get("confirm_password") is not None \
            and data.get("confirm_password") != new:
        errors["confirm_password"] = "Passwords do not match."
    if not errors and not check_password_hash(user["password_hash"], current):
        errors["current_password"] = "Current password is incorrect."
    if not errors and current == new:
        errors["new_password"] = "New password must be different from the current one."
    if errors:
        return error("Could not change password.", 400, errors)
    db = get_db()
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (generate_password_hash(new, method=HASH_METHOD), user["id"]))
    db.commit()
    return jsonify({"message": "Password changed successfully."})
