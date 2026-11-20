"""Menu items, categories and public statistics."""
import sqlite3

from flask import Blueprint, current_app, jsonify, request

from database import get_db
from models import menu_item_to_dict
from utils import (admin_required, error, get_payload, like_escape, remove_image, save_image,
                   to_bool, to_float, to_int, v_text)

bp = Blueprint("menu", __name__, url_prefix="/api")

SORTS = {
    "price_asc": "m.price ASC, m.name ASC",
    "price_desc": "m.price DESC, m.name ASC",
    "name": "m.name COLLATE NOCASE ASC",
    "popular": "m.is_popular DESC, m.name COLLATE NOCASE ASC",
}
BASE_SELECT = ("SELECT m.*, c.name AS category_name FROM menu_items m "
               "JOIN categories c ON c.id = m.category_id")


# ------------------------------------------------------------ categories ----
@bp.get("/categories")
def list_categories():
    rows = get_db().execute(
        "SELECT c.id, c.name, c.description, COUNT(m.id) AS item_count "
        "FROM categories c LEFT JOIN menu_items m ON m.category_id = c.id "
        "GROUP BY c.id ORDER BY c.name COLLATE NOCASE").fetchall()
    return jsonify({"categories": [dict(r) for r in rows]})


@bp.post("/categories")
@admin_required
def create_category():
    data = get_payload()
    errors = {}
    name = v_text(data, "name", "Category name", errors, min_len=2, max_len=40)
    desc = v_text(data, "description", "Description", errors, max_len=120, required=False)
    if errors:
        return error("Invalid category.", 400, errors)
    db = get_db()
    try:
        cur = db.execute("INSERT INTO categories (name, description) VALUES (?, ?)", (name, desc))
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return error("A category with this name already exists.", 409, {"name": "Already exists."})
    return jsonify({"message": "Category added.",
                    "category": {"id": cur.lastrowid, "name": name, "description": desc}}), 201


@bp.put("/categories/<int:cid>")
@admin_required
def update_category(cid):
    data = get_payload()
    errors = {}
    name = v_text(data, "name", "Category name", errors, min_len=2, max_len=40)
    desc = v_text(data, "description", "Description", errors, max_len=120, required=False)
    if errors:
        return error("Invalid category.", 400, errors)
    db = get_db()
    if db.execute("SELECT 1 FROM categories WHERE id=?", (cid,)).fetchone() is None:
        return error("Category not found.", 404)
    try:
        db.execute("UPDATE categories SET name=?, description=? WHERE id=?", (name, desc, cid))
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return error("A category with this name already exists.", 409, {"name": "Already exists."})
    return jsonify({"message": "Category updated."})


@bp.delete("/categories/<int:cid>")
@admin_required
def delete_category(cid):
    db = get_db()
    if db.execute("SELECT 1 FROM categories WHERE id=?", (cid,)).fetchone() is None:
        return error("Category not found.", 404)
    used = db.execute("SELECT COUNT(*) FROM menu_items WHERE category_id=?", (cid,)).fetchone()[0]
    if used:
        return error("This category still has %d menu item(s). Move or delete them first." % used, 409)
    db.execute("DELETE FROM categories WHERE id=?", (cid,))
    db.commit()
    return jsonify({"message": "Category deleted."})


# ------------------------------------------------------------- menu items ----
@bp.get("/menu")
def list_menu():
    args = request.args
    sql = BASE_SELECT + " WHERE 1=1"
    params = []
    q = (args.get("q") or "").strip()[:60]
    if q:
        like = "%" + like_escape(q) + "%"
        sql += (" AND (m.name LIKE ? ESCAPE '\\' OR m.description LIKE ? ESCAPE '\\'"
                " OR c.name LIKE ? ESCAPE '\\')")
        params += [like, like, like]
    category = to_int(args.get("category")) if args.get("category") else None
    if category:
        sql += " AND m.category_id = ?"
        params.append(category)
    veg = (args.get("veg") or "").lower()
    if veg in ("veg", "1", "true"):
        sql += " AND m.is_veg = 1"
    elif veg in ("nonveg", "non-veg", "0", "false"):
        sql += " AND m.is_veg = 0"
    if to_bool(args.get("available")):
        sql += " AND m.is_available = 1"
    if to_bool(args.get("popular")):
        sql += " AND m.is_popular = 1"
    sql += " ORDER BY " + SORTS.get(args.get("sort"), SORTS["name"])
    limit = to_int(args.get("limit")) if args.get("limit") else None
    if limit and 0 < limit <= 200:
        sql += " LIMIT %d" % limit
    rows = get_db().execute(sql, params).fetchall()
    return jsonify({"items": [menu_item_to_dict(r) for r in rows],
                    "count": len(rows),
                    "tax_rate": current_app.config["TAX_RATE"]})


@bp.get("/menu/<int:item_id>")
def get_menu_item(item_id):
    row = get_db().execute(BASE_SELECT + " WHERE m.id = ?", (item_id,)).fetchone()
    if row is None:
        return error("Menu item not found.", 404)
    return jsonify({"item": menu_item_to_dict(row)})


def _validate_item(data, db, partial=False):
    """Return (clean_fields, errors). With partial=True only supplied keys are checked."""
    errors, clean = {}, {}
    has = lambda k: (not partial) or (k in data)  # noqa: E731
    if has("name"):
        name = v_text(data, "name", "Name", errors, min_len=2, max_len=80)
        if name is not None:
            clean["name"] = name
    if has("description"):
        clean["description"] = v_text(data, "description", "Description", errors,
                                      max_len=300, required=False, multiline=True) or ""
    if has("price"):
        price = to_float(data.get("price"))
        if price is None or price <= 0 or price > 10000:
            errors["price"] = "Price must be a number between 0.01 and 10000."
        else:
            clean["price"] = round(price, 2)
    if has("category_id"):
        cid = to_int(data.get("category_id"))
        if cid is None or db.execute("SELECT 1 FROM categories WHERE id=?", (cid,)).fetchone() is None:
            errors["category_id"] = "Choose a valid category."
        else:
            clean["category_id"] = cid
    if has("prep_time") and (not partial or "prep_time" in data):
        raw = data.get("prep_time")
        minutes = 10 if raw in (None, "") else to_int(raw)
        if minutes is None or not 1 <= minutes <= 120:
            errors["prep_time"] = "Preparation time must be 1-120 minutes."
        else:
            clean["prep_time"] = minutes
    for flag, default in (("is_veg", True), ("is_available", True), ("is_popular", False)):
        if flag in data:
            clean[flag] = 1 if to_bool(data.get(flag)) else 0
        elif not partial:
            clean[flag] = 1 if default else 0
    return clean, errors


@bp.post("/menu")
@admin_required
def create_menu_item():
    data = get_payload()
    db = get_db()
    clean, errors = _validate_item(data, db)
    image = request.files.get("image")
    image_url = None
    if image and image.filename and not errors:
        image_url = save_image(image, errors)
    if errors:
        return error("Please correct the highlighted fields.", 400, errors)
    dup = db.execute("SELECT 1 FROM menu_items WHERE category_id=? AND name=? COLLATE NOCASE",
                     (clean["category_id"], clean["name"])).fetchone()
    if dup:
        remove_image(image_url)
        return error("This item already exists in that category.", 409, {"name": "Already exists."})
    cur = db.execute(
        "INSERT INTO menu_items (category_id, name, description, price, image_url, is_veg, "
        "is_available, is_popular, prep_time) VALUES (?,?,?,?,?,?,?,?,?)",
        (clean["category_id"], clean["name"], clean["description"], clean["price"], image_url,
         clean["is_veg"], clean["is_available"], clean["is_popular"], clean["prep_time"]))
    db.commit()
    row = db.execute(BASE_SELECT + " WHERE m.id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"message": "Menu item added.", "item": menu_item_to_dict(row)}), 201


@bp.put("/menu/<int:item_id>")
@admin_required
def update_menu_item(item_id):
    db = get_db()
    existing = db.execute("SELECT * FROM menu_items WHERE id=?", (item_id,)).fetchone()
    if existing is None:
        return error("Menu item not found.", 404)
    data = get_payload()
    clean, errors = _validate_item(data, db, partial=True)
    new_image = None
    image = request.files.get("image")
    if image and image.filename and not errors:
        new_image = save_image(image, errors)
    if errors:
        return error("Please correct the highlighted fields.", 400, errors)

    name = clean.get("name", existing["name"])
    cat = clean.get("category_id", existing["category_id"])
    dup = db.execute("SELECT 1 FROM menu_items WHERE category_id=? AND name=? COLLATE NOCASE AND id<>?",
                     (cat, name, item_id)).fetchone()
    if dup:
        remove_image(new_image)
        return error("This item already exists in that category.", 409, {"name": "Already exists."})

    old_image = existing["image_url"]
    if new_image:
        clean["image_url"] = new_image
    elif to_bool(data.get("remove_image")):
        clean["image_url"] = None
    if not clean:
        return error("Nothing to update.", 400)
    clean["updated_at"] = None  # placeholder replaced below
    del clean["updated_at"]
    sets = ", ".join("%s = ?" % col for col in clean) + ", updated_at = datetime('now','localtime')"
    db.execute("UPDATE menu_items SET %s WHERE id = ?" % sets, list(clean.values()) + [item_id])
    db.commit()
    if "image_url" in clean and old_image != clean["image_url"]:
        remove_image(old_image)
    row = db.execute(BASE_SELECT + " WHERE m.id=?", (item_id,)).fetchone()
    return jsonify({"message": "Menu item updated.", "item": menu_item_to_dict(row)})


@bp.delete("/menu/<int:item_id>")
@admin_required
def delete_menu_item(item_id):
    db = get_db()
    row = db.execute("SELECT image_url FROM menu_items WHERE id=?", (item_id,)).fetchone()
    if row is None:
        return error("Menu item not found.", 404)
    db.execute("DELETE FROM menu_items WHERE id=?", (item_id,))  # order history keeps its snapshot
    db.commit()
    remove_image(row["image_url"])
    return jsonify({"message": "Menu item deleted."})


# ------------------------------------------------------- public statistics ----
@bp.get("/stats")
def public_stats():
    db = get_db()
    items = db.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]
    rating = db.execute("SELECT AVG(rating), COUNT(rating) FROM orders WHERE rating IS NOT NULL").fetchone()
    measured = db.execute(
        "SELECT AVG((julianday(completed_at) - julianday(created_at)) * 1440.0) FROM orders "
        "WHERE status='Completed' AND completed_at IS NOT NULL "
        "AND created_at >= datetime('now','localtime','-30 days')").fetchone()[0]
    if measured is not None and measured > 0:
        avg_minutes, basis = round(measured), "completed orders (last 30 days)"
    else:
        est = db.execute("SELECT AVG(prep_time) FROM menu_items WHERE is_available=1").fetchone()[0]
        avg_minutes, basis = (round(est) if est else None), "menu preparation estimates"
    return jsonify({
        "chefs": current_app.config["CHEFS"],
        "menu_items": items,
        "rating": round(rating[0], 1) if rating[0] is not None else None,
        "rating_count": rating[1],
        "avg_minutes": avg_minutes,
        "avg_minutes_basis": basis,
    })
