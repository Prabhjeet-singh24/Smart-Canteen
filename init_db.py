"""Database initialisation script.

Usage (from the project root):
    python database/init_db.py            # create tables, sample menu, admin account
    python database/init_db.py --demo     # also add demo customers and sample orders

The admin account is created only if no admin exists yet. Credentials come from
ADMIN_EMAIL / ADMIN_PASSWORD (environment or .env). If ADMIN_PASSWORD is not set a
random password is generated and printed ONCE.
"""
import argparse
import os
import random
import secrets
import string
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(os.path.dirname(HERE), "backend")
sys.path.insert(0, BACKEND)

from werkzeug.security import generate_password_hash  # noqa: E402

from config import Config  # noqa: E402
from database import connect, init_schema  # noqa: E402
from utils import EMAIL_RE  # noqa: E402

HASH_METHOD = "pbkdf2:sha256:600000"

CATEGORIES = [
    ("Breakfast", "South-Indian and morning favourites"),
    ("Meals", "Filling lunch and dinner plates"),
    ("Snacks", "Quick bites between classes"),
    ("Fast Food", "Burgers, rolls and more"),
    ("Beverages", "Hot and cold drinks"),
    ("Desserts", "Something sweet"),
]

# name, description, price, category, veg, prep minutes, popular, image file
MENU = [
    ("Masala Dosa", "Crisp rice crepe filled with spiced potato, served with sambar and chutney.", 60, "Breakfast", 1, 10, 1, "masala-dosa.svg"),
    ("Idli Sambar", "Three soft steamed idlis with hot sambar and coconut chutney.", 40, "Breakfast", 1, 8, 0, "idli-sambar.svg"),
    ("Poha", "Flattened rice tempered with mustard, peanuts and curry leaves.", 35, "Breakfast", 1, 6, 0, "poha.svg"),
    ("Aloo Paratha", "Stuffed whole-wheat flatbread with curd and pickle.", 50, "Breakfast", 1, 10, 0, "aloo-paratha.svg"),
    ("Veg Thali", "Dal, two sabzis, rice, roti, salad and a sweet.", 90, "Meals", 1, 12, 1, "veg-thali.svg"),
    ("Chicken Biryani", "Fragrant basmati layered with spiced chicken, served with raita.", 130, "Meals", 0, 15, 1, "chicken-biryani.svg"),
    ("Paneer Butter Masala Combo", "Creamy paneer gravy with two rotis and onion salad.", 110, "Meals", 1, 12, 0, "paneer-butter-masala.svg"),
    ("Egg Curry Rice", "Home-style egg curry with steamed rice.", 80, "Meals", 0, 12, 0, "egg-curry-rice.svg"),
    ("Rajma Chawal", "Kidney-bean curry with steamed rice.", 70, "Meals", 1, 10, 0, "rajma-chawal.svg"),
    ("Samosa (2 pcs)", "Golden pastry filled with spiced potato and peas.", 25, "Snacks", 1, 4, 1, "samosa.svg"),
    ("Vada Pav", "Mumbai-style potato fritter in a soft bun with chutneys.", 20, "Snacks", 1, 5, 1, "vada-pav.svg"),
    ("Pav Bhaji", "Buttery mashed vegetable curry with toasted pav.", 70, "Snacks", 1, 10, 0, "pav-bhaji.svg"),
    ("Veg Sandwich", "Grilled sandwich with fresh vegetables and mint chutney.", 40, "Snacks", 1, 6, 0, "veg-sandwich.svg"),
    ("Veg Burger", "Crispy vegetable patty, lettuce and sauce in a toasted bun.", 55, "Fast Food", 1, 8, 0, "veg-burger.svg"),
    ("Chicken Burger", "Juicy chicken patty with cheese and mayo.", 80, "Fast Food", 0, 10, 0, "chicken-burger.svg"),
    ("French Fries", "Crispy salted fries with ketchup.", 50, "Fast Food", 1, 6, 1, "french-fries.svg"),
    ("Veg Hakka Noodles", "Wok-tossed noodles with crunchy vegetables.", 75, "Fast Food", 1, 10, 0, "hakka-noodles.svg"),
    ("Chicken Roll", "Spiced chicken wrapped in a flaky paratha.", 70, "Fast Food", 0, 10, 0, "chicken-roll.svg"),
    ("Masala Chai", "Hot ginger-cardamom tea.", 15, "Beverages", 1, 3, 1, "masala-chai.svg"),
    ("Filter Coffee", "Strong South-Indian filter coffee.", 20, "Beverages", 1, 3, 0, "filter-coffee.svg"),
    ("Cold Coffee", "Chilled blended coffee with ice cream.", 45, "Beverages", 1, 5, 0, "cold-coffee.svg"),
    ("Fresh Lime Soda", "Sweet or salted lime soda.", 30, "Beverages", 1, 3, 0, "lime-soda.svg"),
    ("Mango Lassi", "Thick chilled yoghurt and mango drink.", 40, "Beverages", 1, 4, 0, "mango-lassi.svg"),
    ("Gulab Jamun (2 pcs)", "Soft milk dumplings in warm sugar syrup.", 30, "Desserts", 1, 3, 0, "gulab-jamun.svg"),
    ("Ice Cream Cup", "Vanilla, chocolate or strawberry scoop.", 35, "Desserts", 1, 2, 0, "ice-cream.svg"),
    ("Chocolate Brownie", "Warm fudgy brownie.", 50, "Desserts", 1, 4, 0, "brownie.svg"),
]


def _random_password():
    alphabet = string.ascii_letters + string.digits
    pwd = "".join(secrets.choice(alphabet) for _ in range(12))
    return pwd + "a1"


def _password_ok(pwd):
    return len(pwd) >= 8 and any(c.isalpha() for c in pwd) and any(c.isdigit() for c in pwd)


def ensure_admin(conn):
    """Create the admin account if none exists. Returns (email, generated_password|None)."""
    if conn.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        return None, None
    email = (os.environ.get("ADMIN_EMAIL") or "admin@smartcanteen.local").strip().lower()
    name = os.environ.get("ADMIN_NAME") or "Canteen Admin"
    password = os.environ.get("ADMIN_PASSWORD") or ""
    generated = None
    if not EMAIL_RE.match(email):
        raise SystemExit("ADMIN_EMAIL is not a valid email address.")
    if not password:
        password = generated = _random_password()
    elif not _password_ok(password):
        raise SystemExit("ADMIN_PASSWORD must be at least 8 characters with a letter and a digit.")
    conn.execute(
        "INSERT INTO users (name, email, phone, student_id, password_hash, role) VALUES (?,?,?,?,?, 'admin')",
        (name, email, None, None, generate_password_hash(password, method=HASH_METHOD)))
    conn.commit()
    return email, generated


def seed_menu(conn):
    if conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0] or \
            conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]:
        return False
    conn.executemany("INSERT INTO categories (name, description) VALUES (?,?)", CATEGORIES)
    cat = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM categories")}
    conn.executemany(
        "INSERT INTO menu_items (category_id, name, description, price, image_url, is_veg, prep_time, is_popular) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [(cat[c], n, d, p, "assets/images/" + img, v, t, pop) for n, d, p, c, v, t, pop, img in MENU])
    conn.commit()
    return True


def seed_demo(conn):
    """Optional demo customers + orders so dashboards and reports are not empty."""
    if conn.execute("SELECT 1 FROM users WHERE email='demo.student@smartcanteen.local'").fetchone():
        return False
    rnd = random.Random(7)
    pwd = generate_password_hash("Demo@12345", method=HASH_METHOD)
    people = [("Aarav Patil", "demo.student@smartcanteen.local", "9876500001", "CS2021001"),
              ("Diya Kulkarni", "diya@smartcanteen.local", "9876500002", "ME2022014"),
              ("Rohan Shaikh", "rohan@smartcanteen.local", "9876500003", "EC2020033")]
    ids = []
    for n, e, p, s in people:
        cur = conn.execute("INSERT INTO users (name,email,phone,student_id,password_hash) VALUES (?,?,?,?,?)",
                           (n, e, p, s, pwd))
        ids.append((cur.lastrowid, n, p, s))
    menu = conn.execute("SELECT id, name, price FROM menu_items WHERE is_available=1").fetchall()
    tax_rate = Config.TAX_RATE
    now = datetime.now()
    for _ in range(45):
        uid, n, p, s = rnd.choice(ids)
        when = now - timedelta(days=rnd.randint(0, 40), hours=rnd.randint(0, 8), minutes=rnd.randint(0, 59))
        picks = rnd.sample(menu, rnd.randint(1, 3))
        lines = [(m["id"], m["name"], m["price"], rnd.randint(1, 3)) for m in picks]
        subtotal = round(sum(l[2] * l[3] for l in lines), 2)
        tax = round(subtotal * tax_rate, 2)
        old = (now - when).days >= 1
        status = rnd.choice(["Completed"] * 8 + ["Cancelled"]) if old else rnd.choice(
            ["Pending", "Confirmed", "Preparing", "Ready for Pickup", "Completed"])
        method = rnd.choice(["Cash", "Demo UPI"])
        pay = "Paid (Demo)" if method == "Demo UPI" else ("Paid" if status == "Completed" else "Pending")
        if status == "Cancelled" and method == "Demo UPI":
            pay = "Refunded (Demo)"
        stamp = when.strftime("%Y-%m-%d %H:%M:%S")
        done = (when + timedelta(minutes=rnd.randint(8, 25))).strftime("%Y-%m-%d %H:%M:%S") \
            if status == "Completed" else None
        rating = rnd.choice([3, 4, 4, 5, 5, 5]) if status == "Completed" and rnd.random() < 0.6 else None
        cur = conn.execute(
            "INSERT INTO orders (user_id,customer_name,student_id,phone,order_type,payment_method,payment_status,"
            "status,subtotal,tax,total,rating,created_at,updated_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid, n, s, p, rnd.choice(["Dine-in", "Takeaway"]), method, pay, status, subtotal, tax,
             round(subtotal + tax, 2), rating, stamp, stamp, done))
        conn.executemany(
            "INSERT INTO order_items (order_id,menu_item_id,item_name,unit_price,quantity,line_total) VALUES (?,?,?,?,?,?)",
            [(cur.lastrowid, i, nm, pr, q, round(pr * q, 2)) for i, nm, pr, q in lines])
    conn.commit()
    return True


def init_database(db_path=None, demo=False, quiet=False):
    conn = connect(db_path or Config.DATABASE)
    try:
        init_schema(conn)
        seeded = seed_menu(conn)
        email, generated = ensure_admin(conn)
        demo_added = seed_demo(conn) if demo else False
    finally:
        conn.close()
    if not quiet:
        print("Database ready: %s" % (db_path or Config.DATABASE))
        if seeded:
            print("  - sample categories and menu items added")
        if email:
            print("  - admin account created: %s" % email)
            if generated:
                print("  - GENERATED ADMIN PASSWORD (shown only once): %s" % generated)
                print("    Set ADMIN_PASSWORD in .env before first run if you want to choose your own.")
        if demo_added:
            print("  - demo customers added (password for all: Demo@12345) with sample orders")
    return {"admin_email": email, "generated_password": generated}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialise the Smart Canteen database.")
    parser.add_argument("--demo", action="store_true", help="add demo customers and sample orders")
    parser.add_argument("--db", help="path of the SQLite file (default: from config)")
    args = parser.parse_args()
    init_database(args.db, demo=args.demo)
