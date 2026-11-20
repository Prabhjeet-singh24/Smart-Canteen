"""Admin dashboard, customer management and reports."""
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from database import get_db
from models import ORDER_STATUSES, fetch_order_items, order_to_dict, user_to_dict
from utils import admin_required, error, get_payload, like_escape, load_user, to_bool

bp = Blueprint("admin", __name__, url_prefix="/api/admin")

# Revenue = every order that was not cancelled.
REVENUE_WHERE = "status != 'Cancelled'"


def _popular(db, limit):
    rows = db.execute(
        "SELECT oi.item_name AS name, SUM(oi.quantity) AS quantity, SUM(oi.line_total) AS revenue "
        "FROM order_items oi JOIN orders o ON o.id = oi.order_id WHERE o.status != 'Cancelled' "
        "GROUP BY oi.item_name ORDER BY quantity DESC, revenue DESC LIMIT ?", (limit,)).fetchall()
    return [{"name": r["name"], "quantity": r["quantity"], "revenue": round(r["revenue"], 2)} for r in rows]


@bp.get("/dashboard")
@admin_required
def dashboard():
    db = get_db()
    one = lambda sql, *p: db.execute(sql, p).fetchone()[0]  # noqa: E731
    stats = {
        "total_orders": one("SELECT COUNT(*) FROM orders"),
        "total_revenue": round(one("SELECT COALESCE(SUM(total),0) FROM orders WHERE " + REVENUE_WHERE), 2),
        "total_customers": one("SELECT COUNT(*) FROM users WHERE role='customer'"),
        "total_menu_items": one("SELECT COUNT(*) FROM menu_items"),
        "pending_orders": one("SELECT COUNT(*) FROM orders WHERE status='Pending'"),
        "completed_orders": one("SELECT COUNT(*) FROM orders WHERE status='Completed'"),
        "today_orders": one("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now','localtime')"),
        "today_revenue": round(one("SELECT COALESCE(SUM(total),0) FROM orders WHERE " + REVENUE_WHERE +
                                   " AND date(created_at)=date('now','localtime')"), 2),
    }
    breakdown = {s: 0 for s in ORDER_STATUSES}
    for r in db.execute("SELECT status, COUNT(*) c FROM orders GROUP BY status"):
        breakdown[r["status"]] = r["c"]
    recent = db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 6").fetchall()
    items = fetch_order_items(db, [r["id"] for r in recent])
    return jsonify({"stats": stats, "status_breakdown": breakdown,
                    "recent_orders": [order_to_dict(r, items[r["id"]]) for r in recent],
                    "popular_items": _popular(db, 5)})


@bp.get("/customers")
@admin_required
def customers():
    q = (request.args.get("q") or "").strip()[:40]
    sql = ("SELECT u.*, COUNT(o.id) AS order_count, COALESCE(SUM(CASE WHEN o.status != 'Cancelled' "
           "THEN o.total END), 0) AS total_spent FROM users u LEFT JOIN orders o ON o.user_id = u.id "
           "WHERE u.role = 'customer'")
    params = []
    if q:
        like = "%" + like_escape(q) + "%"
        sql += (" AND (u.name LIKE ? ESCAPE '\\' OR u.email LIKE ? ESCAPE '\\' "
                "OR u.student_id LIKE ? ESCAPE '\\' OR u.phone LIKE ? ESCAPE '\\')")
        params = [like] * 4
    sql += " GROUP BY u.id ORDER BY u.id DESC"
    rows = get_db().execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = user_to_dict(r)
        d["order_count"], d["total_spent"] = r["order_count"], round(r["total_spent"], 2)
        out.append(d)
    return jsonify({"customers": out, "count": len(out)})


@bp.get("/customers/<int:uid>")
@admin_required
def customer_detail(uid):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=? AND role='customer'", (uid,)).fetchone()
    if row is None:
        return error("Customer not found.", 404)
    orders = db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
    items = fetch_order_items(db, [o["id"] for o in orders])
    spent = sum(o["total"] for o in orders if o["status"] != "Cancelled")
    return jsonify({"customer": user_to_dict(row), "total_spent": round(spent, 2),
                    "orders": [order_to_dict(o, items[o["id"]]) for o in orders]})


@bp.put("/customers/<int:uid>")
@admin_required
def update_customer(uid):
    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE id=? AND role='customer'", (uid,)).fetchone() is None:
        return error("Customer not found.", 404)
    data = get_payload()
    if "is_active" not in data:
        return error("Nothing to update.", 400)
    active = 1 if to_bool(data.get("is_active")) else 0
    db.execute("UPDATE users SET is_active=? WHERE id=?", (active, uid))
    db.commit()
    return jsonify({"message": "Account %s." % ("enabled" if active else "disabled")})


@bp.delete("/customers/<int:uid>")
@admin_required
def delete_customer(uid):
    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE id=? AND role='customer'", (uid,)).fetchone() is None:
        return error("Customer not found.", 404)
    if db.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,)).fetchone()[0]:
        return error("This customer has order history and cannot be deleted. Disable the account instead.", 409)
    db.execute("DELETE FROM users WHERE id=?", (uid,))
    db.commit()
    return jsonify({"message": "Customer deleted."})


@bp.get("/reports")
@admin_required
def reports():
    db = get_db()
    today = date.today()
    start = date(today.year - 1, today.month, 1)
    rows = db.execute(
        "SELECT date(created_at) d, COUNT(*) c, SUM(total) r FROM orders WHERE " + REVENUE_WHERE +
        " AND date(created_at) >= ? GROUP BY d", (start.isoformat(),)).fetchall()
    by_day = {r["d"]: (r["c"], r["r"] or 0) for r in rows}

    daily = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        c, r = by_day.get(d.isoformat(), (0, 0))
        daily.append({"label": d.strftime("%d %b"), "orders": c, "revenue": round(r, 2)})

    weekly = []
    monday = today - timedelta(days=today.weekday())
    for i in range(7, -1, -1):
        ws = monday - timedelta(weeks=i)
        c = r = 0
        for k in range(7):
            dc, dr = by_day.get((ws + timedelta(days=k)).isoformat(), (0, 0))
            c, r = c + dc, r + dr
        weekly.append({"label": ws.strftime("%d %b"), "orders": c, "revenue": round(r, 2)})

    monthly = []
    for i in range(11, -1, -1):
        y, m = today.year, today.month - i
        while m <= 0:
            m += 12
            y -= 1
        prefix = "%04d-%02d" % (y, m)
        c = r = 0
        for key, (dc, dr) in by_day.items():
            if key.startswith(prefix):
                c, r = c + dc, r + dr
        monthly.append({"label": date(y, m, 1).strftime("%b %Y"), "orders": c, "revenue": round(r, 2)})

    totals = db.execute(
        "SELECT COUNT(*) c, COALESCE(SUM(total),0) r FROM orders WHERE " + REVENUE_WHERE).fetchone()
    sold = db.execute("SELECT COALESCE(SUM(oi.quantity),0) FROM order_items oi JOIN orders o "
                      "ON o.id=oi.order_id WHERE o.status != 'Cancelled'").fetchone()[0]
    cancelled = db.execute("SELECT COUNT(*) FROM orders WHERE status='Cancelled'").fetchone()[0]
    return jsonify({
        "total_sales": {
            "revenue": round(totals["r"], 2), "orders": totals["c"], "items_sold": sold,
            "cancelled_orders": cancelled,
            "average_order_value": round(totals["r"] / totals["c"], 2) if totals["c"] else 0,
            "revenue_today": daily[-1]["revenue"],
            "revenue_this_week": weekly[-1]["revenue"],
            "revenue_this_month": monthly[-1]["revenue"],
        },
        "daily": daily, "weekly": weekly, "monthly": monthly,
        "popular_items": _popular(db, 10),
        "revenue_definition": "Revenue counts every order that is not Cancelled (tax included).",
    })
