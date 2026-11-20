"""Order placement, listing, status updates and ratings."""
import secrets

from flask import Blueprint, current_app, jsonify, request

from database import get_db
from models import (NEXT_STATUS, ORDER_STATUSES, ORDER_TYPES, PAYMENT_METHODS, fetch_order_items,
                    order_to_dict)
from utils import (UPI_RE, customer_required, error, get_payload, like_escape, load_user,
                   login_required, to_int, v_phone, v_student_id, v_text)

bp = Blueprint("orders", __name__, url_prefix="/api")


def _get_full_order(db, order_id):
    row = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if row is None:
        return None
    return order_to_dict(row, fetch_order_items(db, [order_id])[order_id])


@bp.post("/orders")
@customer_required
def create_order():
    user = load_user()
    data = get_payload()
    errors = {}

    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return error("Your cart is empty.", 400, {"items": "Add at least one item."})
    if len(raw_items) > 50:
        return error("Too many items in one order.", 400)
    wanted = {}
    for entry in raw_items:
        if not isinstance(entry, dict):
            return error("Invalid item in order.", 400)
        item_id, qty = to_int(entry.get("menu_item_id")), to_int(entry.get("quantity"))
        if item_id is None or qty is None or not 1 <= qty <= 20:
            return error("Each item needs a valid id and a quantity between 1 and 20.", 400)
        wanted[item_id] = min(20, wanted.get(item_id, 0) + qty)

    order_type = data.get("order_type")
    if order_type not in ORDER_TYPES:
        errors["order_type"] = "Choose Dine-in or Takeaway."
    method = data.get("payment_method")
    if method not in PAYMENT_METHODS:
        errors["payment_method"] = "Choose Cash or Demo UPI."
    name = v_text(data, "customer_name", "Name", errors, min_len=2, max_len=60) \
        if data.get("customer_name") else user["name"]
    phone = v_phone(data, errors, "phone") if data.get("phone") else user["phone"]
    student_id = v_student_id(data, errors, "student_id") if data.get("student_id") else user["student_id"]
    if not phone and "phone" not in errors:
        errors["phone"] = "Phone number is required."
    if not student_id and "student_id" not in errors:
        errors["student_id"] = "Student ID or registration number is required."
    notes = v_text(data, "notes", "Notes", errors, max_len=200, required=False, multiline=True)
    if method == "Demo UPI":
        upi = str(data.get("upi_id") or "").strip()
        if not UPI_RE.match(upi):
            errors["upi_id"] = "Enter a valid demo UPI ID such as name@upi."
    if errors:
        return error("Please correct the highlighted fields.", 400, errors)

    db = get_db()
    marks = ",".join("?" * len(wanted))
    rows = db.execute("SELECT id, name, price, is_available FROM menu_items WHERE id IN (%s)" % marks,
                      list(wanted)).fetchall()
    found = {r["id"]: r for r in rows}
    problems = []
    for item_id in wanted:
        r = found.get(item_id)
        if r is None:
            problems.append("An item in your cart no longer exists.")
        elif not r["is_available"]:
            problems.append("%s is currently unavailable." % r["name"])
    if problems:
        return error(" ".join(problems), 409, {"items": problems})

    lines, subtotal = [], 0.0
    for item_id, qty in wanted.items():
        r = found[item_id]
        line = round(r["price"] * qty, 2)
        subtotal += line
        lines.append((item_id, r["name"], r["price"], qty, line))
    subtotal = round(subtotal, 2)
    tax = round(subtotal * current_app.config["TAX_RATE"], 2)
    total = round(subtotal + tax, 2)

    if method == "Demo UPI":
        pay_status, pay_ref = "Paid (Demo)", "DEMO-" + secrets.token_hex(4).upper()
    else:
        pay_status, pay_ref = "Pending", None

    try:
        cur = db.execute(
            "INSERT INTO orders (user_id, customer_name, student_id, phone, order_type, payment_method, "
            "payment_status, payment_ref, status, subtotal, tax, total, notes) "
            "VALUES (?,?,?,?,?,?,?,?, 'Pending', ?,?,?,?)",
            (user["id"], name, student_id, phone, order_type, method, pay_status, pay_ref,
             subtotal, tax, total, notes))
        order_id = cur.lastrowid
        db.executemany(
            "INSERT INTO order_items (order_id, menu_item_id, item_name, unit_price, quantity, line_total) "
            "VALUES (?,?,?,?,?,?)", [(order_id,) + l for l in lines])
        db.commit()
    except Exception:
        db.rollback()
        raise
    return jsonify({"message": "Order placed successfully.", "order": _get_full_order(db, order_id)}), 201


@bp.get("/orders")
@login_required
def list_orders():
    user = load_user()
    db = get_db()
    sql, params = "SELECT * FROM orders WHERE 1=1", []
    if user["role"] != "admin":
        sql += " AND user_id = ?"
        params.append(user["id"])
    status = request.args.get("status")
    if status:
        if status not in ORDER_STATUSES:
            return error("Unknown status filter.", 400)
        sql += " AND status = ?"
        params.append(status)
    q = (request.args.get("q") or "").strip()[:40]
    if q:
        like = "%" + like_escape(q) + "%"
        digits = "".join(ch for ch in q if ch.isdigit())
        clause = ("(customer_name LIKE ? ESCAPE '\\' OR student_id LIKE ? ESCAPE '\\' "
                  "OR phone LIKE ? ESCAPE '\\'")
        params += [like, like, like]
        if digits:
            clause += " OR id = ?"
            params.append(int(digits))
        sql += " AND " + clause + ")"
    sql += " ORDER BY id DESC LIMIT 300"
    rows = db.execute(sql, params).fetchall()
    items = fetch_order_items(db, [r["id"] for r in rows])
    return jsonify({"orders": [order_to_dict(r, items[r["id"]]) for r in rows], "count": len(rows)})


@bp.get("/orders/<int:order_id>")
@login_required
def get_order(order_id):
    user = load_user()
    order = _get_full_order(get_db(), order_id)
    # Customers get 404 for other people's orders so ids cannot be probed.
    if order is None or (user["role"] != "admin" and order["user_id"] != user["id"]):
        return error("Order not found.", 404)
    return jsonify({"order": order})


@bp.put("/orders/<int:order_id>/status")
@login_required
def update_status(order_id):
    user = load_user()
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if row is None or (user["role"] != "admin" and row["user_id"] != user["id"]):
        return error("Order not found.", 404)
    new = get_payload().get("status")
    if new not in ORDER_STATUSES:
        return error("Invalid status.", 400, {"status": "Choose one of: " + ", ".join(ORDER_STATUSES)})
    current = row["status"]
    if user["role"] != "admin":
        if new != "Cancelled" or current != "Pending":
            return error("You can only cancel an order while it is still Pending.", 403)
    if new not in NEXT_STATUS[current]:
        return error("Cannot change an order from '%s' to '%s'." % (current, new), 409)

    updates = {"status": new}
    if new == "Completed":
        updates["completed_at"] = "NOW"
        if row["payment_method"] == "Cash":
            updates["payment_status"] = "Paid"
    if new == "Cancelled" and row["payment_status"] == "Paid (Demo)":
        updates["payment_status"] = "Refunded (Demo)"
    sets, values = [], []
    for col, val in updates.items():
        if val == "NOW":
            sets.append("%s = datetime('now','localtime')" % col)
        else:
            sets.append("%s = ?" % col)
            values.append(val)
    sets.append("updated_at = datetime('now','localtime')")
    db.execute("UPDATE orders SET %s WHERE id = ?" % ", ".join(sets), values + [order_id])
    db.commit()
    return jsonify({"message": "Order status updated to %s." % new, "order": _get_full_order(db, order_id)})


@bp.post("/orders/<int:order_id>/rating")
@customer_required
def rate_order(order_id):
    user = load_user()
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, user["id"])).fetchone()
    if row is None:
        return error("Order not found.", 404)
    if row["status"] != "Completed":
        return error("You can rate an order once it is completed.", 409)
    if row["rating"] is not None:
        return error("You have already rated this order.", 409)
    rating = to_int(get_payload().get("rating"))
    if rating is None or not 1 <= rating <= 5:
        return error("Rating must be between 1 and 5.", 400, {"rating": "Choose 1 to 5 stars."})
    db.execute("UPDATE orders SET rating=? WHERE id=?", (rating, order_id))
    db.commit()
    return jsonify({"message": "Thanks for your feedback!", "order": _get_full_order(db, order_id)})
