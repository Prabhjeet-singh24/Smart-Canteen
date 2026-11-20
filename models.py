"""Database schema, constants and row -> dict serialisers."""

ORDER_STATUSES = ["Pending", "Confirmed", "Preparing", "Ready for Pickup", "Completed", "Cancelled"]

# Allowed status transitions (admin). Completed / Cancelled are final.
NEXT_STATUS = {
    "Pending": ["Confirmed", "Cancelled"],
    "Confirmed": ["Preparing", "Cancelled"],
    "Preparing": ["Ready for Pickup", "Cancelled"],
    "Ready for Pickup": ["Completed", "Cancelled"],
    "Completed": [],
    "Cancelled": [],
}

ORDER_TYPES = ["Dine-in", "Takeaway"]
PAYMENT_METHODS = ["Cash", "Demo UPI"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    phone         TEXT,
    student_id    TEXT,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_student_id
    ON users (student_id COLLATE NOCASE) WHERE student_id IS NOT NULL AND student_id != '';

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS menu_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id  INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    name         TEXT    NOT NULL,
    description  TEXT,
    price        REAL    NOT NULL CHECK (price >= 0),
    image_url    TEXT,
    is_veg       INTEGER NOT NULL DEFAULT 1,
    is_available INTEGER NOT NULL DEFAULT 1,
    is_popular   INTEGER NOT NULL DEFAULT 0,
    prep_time    INTEGER NOT NULL DEFAULT 10,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_menu_category ON menu_items (category_id);

CREATE TABLE IF NOT EXISTS orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    customer_name  TEXT    NOT NULL,
    student_id     TEXT    NOT NULL,
    phone          TEXT    NOT NULL,
    order_type     TEXT    NOT NULL CHECK (order_type IN ('Dine-in', 'Takeaway')),
    payment_method TEXT    NOT NULL CHECK (payment_method IN ('Cash', 'Demo UPI')),
    payment_status TEXT    NOT NULL DEFAULT 'Pending',
    payment_ref    TEXT,
    status         TEXT    NOT NULL DEFAULT 'Pending'
                   CHECK (status IN ('Pending','Confirmed','Preparing','Ready for Pickup','Completed','Cancelled')),
    subtotal       REAL    NOT NULL,
    tax            REAL    NOT NULL,
    total          REAL    NOT NULL,
    notes          TEXT,
    rating         INTEGER CHECK (rating BETWEEN 1 AND 5),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    completed_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_user    ON orders (user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders (status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders (created_at);

CREATE TABLE IF NOT EXISTS order_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    menu_item_id INTEGER REFERENCES menu_items (id) ON DELETE SET NULL,
    item_name    TEXT    NOT NULL,
    unit_price   REAL    NOT NULL,
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    line_total   REAL    NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items (order_id);
"""


def order_number(order_id):
    return "SC-%05d" % order_id


def user_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
        "student_id": row["student_id"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


def menu_item_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"] or "",
        "price": row["price"],
        "image_url": row["image_url"],
        "category_id": row["category_id"],
        "category": row["category_name"],
        "is_veg": bool(row["is_veg"]),
        "is_available": bool(row["is_available"]),
        "is_popular": bool(row["is_popular"]),
        "prep_time": row["prep_time"],
        "created_at": row["created_at"],
    }


def fetch_order_items(db, order_ids):
    """Return {order_id: [item dicts]} for the given order ids."""
    result = {oid: [] for oid in order_ids}
    if not order_ids:
        return result
    marks = ",".join("?" * len(order_ids))
    rows = db.execute(
        "SELECT * FROM order_items WHERE order_id IN (%s) ORDER BY id" % marks, list(order_ids)
    ).fetchall()
    for r in rows:
        result[r["order_id"]].append({
            "id": r["id"],
            "menu_item_id": r["menu_item_id"],
            "name": r["item_name"],
            "unit_price": r["unit_price"],
            "quantity": r["quantity"],
            "line_total": r["line_total"],
        })
    return result


def order_to_dict(row, items=None):
    d = {
        "id": row["id"],
        "order_number": order_number(row["id"]),
        "user_id": row["user_id"],
        "customer_name": row["customer_name"],
        "student_id": row["student_id"],
        "phone": row["phone"],
        "order_type": row["order_type"],
        "payment_method": row["payment_method"],
        "payment_status": row["payment_status"],
        "payment_ref": row["payment_ref"],
        "status": row["status"],
        "subtotal": row["subtotal"],
        "tax": row["tax"],
        "total": row["total"],
        "notes": row["notes"] or "",
        "rating": row["rating"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
        "next_statuses": NEXT_STATUS.get(row["status"], []),
    }
    if items is not None:
        d["items"] = items
    return d
