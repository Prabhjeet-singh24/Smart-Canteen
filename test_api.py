"""API tests.  Run from the project root:  python -m unittest discover -s backend/tests -v"""
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

from app import create_app  # noqa: E402
import utils  # noqa: E402

spec = importlib.util.spec_from_file_location("init_db", os.path.join(ROOT, "database", "init_db.py"))
init_db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(init_db)

ADMIN_EMAIL, ADMIN_PW = "admin@test.local", "AdminPass1"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


class Base(unittest.TestCase):
    def setUp(self):
        utils.reset_rate_limits()
        self.tmp = tempfile.mkdtemp()
        os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"] = ADMIN_EMAIL, ADMIN_PW
        self.db_path = os.path.join(self.tmp, "t.db")
        self.app = create_app({"DATABASE": self.db_path, "UPLOAD_FOLDER": os.path.join(self.tmp, "up"),
                               "TESTING": True, "SERVE_FRONTEND": False})
        init_db.init_database(self.db_path, quiet=True)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def register(self, client=None, email="stu@test.local", sid="CS100", phone="9876543210"):
        return (client or self.client).post("/api/register", json={
            "name": "Test Student", "email": email, "phone": phone, "student_id": sid,
            "password": "Passw0rdX", "confirm_password": "Passw0rdX"})

    def admin_client(self):
        c = self.app.test_client()
        r = c.post("/api/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW, "role": "admin"})
        self.assertEqual(r.status_code, 200, r.get_json())
        return c

    def place_order(self, client, items=None, **extra):
        body = {"items": items or [{"menu_item_id": 1, "quantity": 2}, {"menu_item_id": 2, "quantity": 1}],
                "order_type": "Takeaway", "payment_method": "Cash"}
        body.update(extra)
        return client.post("/api/orders", json=body)


class AuthTests(Base):
    def test_register_login_logout_profile(self):
        r = self.register()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.get("/api/profile").get_json()["user"]["email"], "stu@test.local")
        self.assertNotIn("password", str(r.get_json()))
        self.client.post("/api/logout")
        self.assertEqual(self.client.get("/api/profile").status_code, 401)
        r = self.client.post("/api/login", json={"email": "STU@test.local", "password": "Passw0rdX"})
        self.assertEqual(r.status_code, 200)

    def test_register_validation_and_duplicates(self):
        r = self.client.post("/api/register", json={"name": "A", "email": "bad", "password": "short"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.get_json()["details"])
        self.assertEqual(self.register().status_code, 201)
        dup = self.register(client=self.app.test_client(), sid="OTHER1")
        self.assertEqual(dup.status_code, 409)
        self.assertIn("email", dup.get_json()["details"])
        dup2 = self.register(client=self.app.test_client(), email="x@test.local")
        self.assertEqual(dup2.status_code, 409)
        self.assertIn("student_id", dup2.get_json()["details"])

    def test_password_is_hashed(self):
        self.register()
        import sqlite3
        pw = sqlite3.connect(self.db_path).execute(
            "SELECT password_hash FROM users WHERE email='stu@test.local'").fetchone()[0]
        self.assertNotIn("Passw0rdX", pw)
        self.assertTrue(pw.startswith("pbkdf2:"))

    def test_invalid_login(self):
        self.register()
        c = self.app.test_client()
        r = c.post("/api/login", json={"email": "stu@test.local", "password": "wrongpass1"})
        self.assertEqual(r.status_code, 401)
        r = c.post("/api/login", json={"email": "nobody@test.local", "password": "wrongpass1"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error"], "Invalid email or password.")
        self.assertEqual(c.post("/api/login", json={}).status_code, 400)

    def test_login_lockout(self):
        for _ in range(5):
            self.client.post("/api/login", json={"email": "a@test.local", "password": "bad-pass-1"})
        r = self.client.post("/api/login", json={"email": "a@test.local", "password": "bad-pass-1"})
        self.assertEqual(r.status_code, 429)

    def test_admin_login_rules(self):
        self.register()
        c = self.app.test_client()
        r = c.post("/api/login", json={"email": "stu@test.local", "password": "Passw0rdX", "role": "admin"})
        self.assertEqual(r.status_code, 401)  # customer cannot use admin login
        r = c.post("/api/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW, "role": "customer"})
        self.assertEqual(r.status_code, 403)
        self.admin_client()

    def test_change_password_and_profile_update(self):
        self.register()
        r = self.client.post("/api/change-password", json={
            "current_password": "wrong", "new_password": "NewPass123", "confirm_password": "NewPass123"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/change-password", json={
            "current_password": "Passw0rdX", "new_password": "NewPass123", "confirm_password": "NewPass123"})
        self.assertEqual(r.status_code, 200)
        r = self.client.put("/api/profile", json={"name": "New Name", "email": "stu@test.local",
                                                 "phone": "9123456780", "student_id": "CS100"})
        self.assertEqual(r.get_json()["user"]["name"], "New Name")
        c = self.app.test_client()
        self.assertEqual(c.post("/api/login", json={"email": "stu@test.local", "password": "NewPass123"}).status_code, 200)


class MenuTests(Base):
    def test_menu_list_filters_and_detail(self):
        data = self.client.get("/api/menu").get_json()
        self.assertGreaterEqual(data["count"], 20)
        self.assertEqual(data["tax_rate"], 0.05)
        nonveg = self.client.get("/api/menu?veg=nonveg").get_json()["items"]
        self.assertTrue(nonveg and all(not i["is_veg"] for i in nonveg))
        asc = [i["price"] for i in self.client.get("/api/menu?sort=price_asc").get_json()["items"]]
        self.assertEqual(asc, sorted(asc))
        self.assertTrue(self.client.get("/api/menu?q=biryani").get_json()["count"] >= 1)
        self.assertEqual(self.client.get("/api/menu?q=%25").get_json()["count"], 0)  # wildcard is escaped
        self.assertEqual(self.client.get("/api/menu/1").status_code, 200)
        self.assertEqual(self.client.get("/api/menu/9999").status_code, 404)

    def test_menu_management_requires_admin(self):
        body = {"name": "Test Dish", "price": "50", "category_id": "1"}
        self.assertEqual(self.client.post("/api/menu", data=body).status_code, 401)
        self.register()
        self.assertEqual(self.client.post("/api/menu", data=body).status_code, 403)
        self.assertEqual(self.client.delete("/api/menu/1").status_code, 403)

    def test_admin_menu_crud_and_upload(self):
        admin = self.admin_client()
        r = admin.post("/api/menu", data={"name": "Test Dish", "price": "55.5", "category_id": "1",
                                           "is_veg": "1", "is_available": "1",
                                           "image": (io.BytesIO(PNG), "dish.png")},
                       content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201, r.get_json())
        item = r.get_json()["item"]
        self.assertTrue(item["image_url"].startswith("/uploads/"))
        self.assertEqual(self.client.get(item["image_url"]).status_code, 200)
        # price + availability change
        r = admin.put("/api/menu/%d" % item["id"], data={"price": "60", "is_available": "0"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["item"]["price"], 60)
        self.assertFalse(r.get_json()["item"]["is_available"])
        # validation
        self.assertEqual(admin.put("/api/menu/%d" % item["id"], data={"price": "-5"}).status_code, 400)
        bad = admin.post("/api/menu", data={"name": "Evil", "price": "5", "category_id": "1",
                                            "image": (io.BytesIO(b"<script>alert(1)</script>"), "x.png")},
                         content_type="multipart/form-data")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(admin.post("/api/menu", data={"name": "Test Dish", "price": "5",
                                                       "category_id": "1"}).status_code, 409)
        self.assertEqual(admin.delete("/api/menu/%d" % item["id"]).status_code, 200)
        self.assertEqual(self.client.get(item["image_url"]).status_code, 404)
        self.assertEqual(self.client.get("/api/menu/%d" % item["id"]).status_code, 404)

    def test_categories(self):
        admin = self.admin_client()
        r = admin.post("/api/categories", json={"name": "Specials"})
        self.assertEqual(r.status_code, 201)
        cid = r.get_json()["category"]["id"]
        self.assertEqual(admin.post("/api/categories", json={"name": "specials"}).status_code, 409)
        self.assertEqual(admin.put("/api/categories/%d" % cid, json={"name": "Chef Specials"}).status_code, 200)
        self.assertEqual(admin.delete("/api/categories/1").status_code, 409)  # has items
        self.assertEqual(admin.delete("/api/categories/%d" % cid).status_code, 200)


class OrderTests(Base):
    def test_order_flow(self):
        self.register()
        r = self.place_order(self.client)
        self.assertEqual(r.status_code, 201, r.get_json())
        order = r.get_json()["order"]
        item1 = self.client.get("/api/menu/1").get_json()["item"]
        item2 = self.client.get("/api/menu/2").get_json()["item"]
        subtotal = item1["price"] * 2 + item2["price"]
        self.assertAlmostEqual(order["subtotal"], subtotal)
        self.assertAlmostEqual(order["tax"], round(subtotal * 0.05, 2))
        self.assertEqual(order["status"], "Pending")
        self.assertEqual(len(order["items"]), 2)
        self.assertEqual(len(self.client.get("/api/orders").get_json()["orders"]), 1)
        self.assertEqual(self.client.get("/api/orders/%d" % order["id"]).status_code, 200)

    def test_order_validation(self):
        self.register()
        self.assertEqual(self.client.post("/api/orders", json={"items": []}).status_code, 400)
        self.assertEqual(self.place_order(self.client, items=[{"menu_item_id": 1, "quantity": 0}]).status_code, 400)
        self.assertEqual(self.place_order(self.client, items=[{"menu_item_id": 9999, "quantity": 1}]).status_code, 409)
        self.assertEqual(self.place_order(self.client, payment_method="Bitcoin").status_code, 400)
        self.assertEqual(self.place_order(self.client, payment_method="Demo UPI").status_code, 400)  # no UPI id
        r = self.place_order(self.client, payment_method="Demo UPI", upi_id="student@upi")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["order"]["payment_status"], "Paid (Demo)")
        self.assertEqual(self.app.test_client().post("/api/orders", json={}).status_code, 401)

    def test_client_cannot_set_prices_and_unavailable_blocked(self):
        self.register()
        r = self.place_order(self.client, items=[{"menu_item_id": 1, "quantity": 1, "price": 0.01}])
        self.assertGreater(r.get_json()["order"]["subtotal"], 1)
        admin = self.admin_client()
        admin.put("/api/menu/3", data={"is_available": "0"})
        self.assertEqual(self.place_order(self.client, items=[{"menu_item_id": 3, "quantity": 1}]).status_code, 409)

    def test_admin_cannot_order(self):
        self.assertEqual(self.place_order(self.admin_client()).status_code, 403)

    def test_privacy_between_customers(self):
        self.register()
        oid = self.place_order(self.client).get_json()["order"]["id"]
        other = self.app.test_client()
        self.register(client=other, email="o@test.local", sid="CS200", phone="9000000001")
        self.assertEqual(other.get("/api/orders/%d" % oid).status_code, 404)
        self.assertEqual(other.get("/api/orders").get_json()["count"], 0)
        self.assertEqual(other.put("/api/orders/%d/status" % oid, json={"status": "Cancelled"}).status_code, 404)

    def test_status_lifecycle_and_cancel_rules(self):
        self.register()
        oid = self.place_order(self.client).get_json()["order"]["id"]
        admin = self.admin_client()
        url = "/api/orders/%d/status" % oid
        self.assertEqual(self.client.put(url, json={"status": "Confirmed"}).status_code, 403)
        self.assertEqual(admin.put(url, json={"status": "Completed"}).status_code, 409)  # skipping steps
        self.assertEqual(admin.put(url, json={"status": "Nonsense"}).status_code, 400)
        for s in ("Confirmed", "Preparing", "Ready for Pickup", "Completed"):
            r = admin.put(url, json={"status": s})
            self.assertEqual(r.status_code, 200, r.get_json())
        done = r.get_json()["order"]
        self.assertEqual(done["payment_status"], "Paid")
        self.assertIsNotNone(done["completed_at"])
        self.assertEqual(admin.put(url, json={"status": "Cancelled"}).status_code, 409)
        # customer cancels pending order
        oid2 = self.place_order(self.client).get_json()["order"]["id"]
        r = self.client.put("/api/orders/%d/status" % oid2, json={"status": "Cancelled"})
        self.assertEqual(r.status_code, 200)

    def test_rating(self):
        self.register()
        oid = self.place_order(self.client).get_json()["order"]["id"]
        self.assertEqual(self.client.post("/api/orders/%d/rating" % oid, json={"rating": 5}).status_code, 409)
        admin = self.admin_client()
        for s in ("Confirmed", "Preparing", "Ready for Pickup", "Completed"):
            admin.put("/api/orders/%d/status" % oid, json={"status": s})
        self.assertEqual(self.client.post("/api/orders/%d/rating" % oid, json={"rating": 9}).status_code, 400)
        self.assertEqual(self.client.post("/api/orders/%d/rating" % oid, json={"rating": 4}).status_code, 200)
        self.assertEqual(self.client.get("/api/stats").get_json()["rating"], 4.0)

    def test_admin_search_and_filter(self):
        self.register()
        oid = self.place_order(self.client).get_json()["order"]["id"]
        admin = self.admin_client()
        self.assertEqual(admin.get("/api/orders?status=Pending").get_json()["count"], 1)
        self.assertEqual(admin.get("/api/orders?status=Completed").get_json()["count"], 0)
        self.assertEqual(admin.get("/api/orders?q=SC-%05d" % oid).get_json()["count"], 1)
        self.assertEqual(admin.get("/api/orders?q=Test%20Student").get_json()["count"], 1)
        self.assertEqual(admin.get("/api/orders?status=Bogus").status_code, 400)


class AdminTests(Base):
    def test_admin_endpoints_protected(self):
        for path in ("/api/admin/dashboard", "/api/admin/customers", "/api/admin/reports"):
            self.assertEqual(self.client.get(path).status_code, 401)
        self.register()
        for path in ("/api/admin/dashboard", "/api/admin/customers", "/api/admin/reports"):
            self.assertEqual(self.client.get(path).status_code, 403)

    def test_dashboard_reports_use_real_data(self):
        self.register()
        self.place_order(self.client)
        oid2 = self.place_order(self.client).get_json()["order"]
        self.client.put("/api/orders/%d/status" % oid2["id"], json={"status": "Cancelled"})
        admin = self.admin_client()
        stats = admin.get("/api/admin/dashboard").get_json()["stats"]
        self.assertEqual(stats["total_orders"], 2)
        self.assertEqual(stats["pending_orders"], 1)
        self.assertEqual(stats["total_customers"], 1)
        first = self.client.get("/api/orders").get_json()["orders"][-1]
        self.assertAlmostEqual(stats["total_revenue"], first["total"])  # cancelled excluded
        rep = admin.get("/api/admin/reports").get_json()
        self.assertEqual(len(rep["daily"]), 14)
        self.assertEqual(len(rep["weekly"]), 8)
        self.assertEqual(len(rep["monthly"]), 12)
        self.assertAlmostEqual(rep["daily"][-1]["revenue"], first["total"])
        self.assertAlmostEqual(rep["monthly"][-1]["revenue"], first["total"])
        self.assertEqual(rep["popular_items"][0]["quantity"], 2)

    def test_customer_management(self):
        self.register()
        self.place_order(self.client)
        admin = self.admin_client()
        lst = admin.get("/api/admin/customers?q=stu").get_json()["customers"]
        self.assertEqual(len(lst), 1)
        uid = lst[0]["id"]
        self.assertEqual(lst[0]["order_count"], 1)
        self.assertEqual(len(admin.get("/api/admin/customers/%d" % uid).get_json()["orders"]), 1)
        self.assertEqual(admin.put("/api/admin/customers/%d" % uid, json={"is_active": False}).status_code, 200)
        self.assertEqual(self.client.get("/api/profile").status_code, 401)  # session revoked
        r = self.app.test_client().post("/api/login", json={"email": "stu@test.local", "password": "Passw0rdX"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(admin.delete("/api/admin/customers/%d" % uid).status_code, 409)  # has orders


class SecurityTests(Base):
    def test_sql_injection_attempts(self):
        r = self.client.post("/api/login", json={"email": "' OR 1=1 --", "password": "x"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.client.get("/api/menu?q=' OR 1=1 --").get_json()["count"], 0)

    def test_foreign_origin_blocked(self):
        r = self.client.post("/api/login", json={"email": "a@b.co", "password": "x"},
                             headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)

    def test_cors_for_local_frontend(self):
        r = self.client.get("/api/menu", headers={"Origin": "http://localhost:5500"})
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "http://localhost:5500")
        self.assertEqual(r.headers["Access-Control-Allow-Credentials"], "true")

    def test_json_errors(self):
        r = self.client.get("/api/nope")
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", r.get_json())
        self.assertEqual(self.client.delete("/api/menu").status_code, 405)

    def test_cookie_flags(self):
        r = self.register()
        cookie = r.headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)


if __name__ == "__main__":
    unittest.main()
