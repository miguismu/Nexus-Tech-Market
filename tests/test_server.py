import unittest
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server import Base, Product, _catalog_rows, create_app


class NexusApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-session-secret",
            "ADMIN_ACCESS_CODE": "test-panel-code-123",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        })
        self.client = self.app.test_client()
        self.csrf_token = self.client.get("/api/security").get_json()["csrf_token"]

    def request_headers(self):
        return {"X-CSRF-Token": self.csrf_token}

    def tearDown(self):
        self.app.extensions["nexus_engine"].dispose()

    def login_as_admin(self):
        response = self.client.post(
            "/api/admin/login",
            json={"admin": "Miguel Alejandro Muñoz Suárez", "code": "test-panel-code-123"},
            headers=self.request_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.csrf_token = response.get_json()["csrf_token"]

    def create_order(self):
        product = self.client.get("/api/products").get_json()["products"][0]
        response = self.client.post(
            "/api/orders",
            json={
                "customer_name": "Estudiante de prueba",
                "customer_email": "estudiante@example.com",
                "items": [{"product_id": product["id"], "quantity": 2}],
            },
            headers=self.request_headers(),
        )
        return response

    def test_catalog_and_health(self):
        health = self.client.get("/api/health")
        products = self.client.get("/api/products")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "ok")
        self.assertGreaterEqual(len(products.get_json()["products"]), 10)

    def test_catalog_has_no_duplicate_products_and_keeps_requested_additions(self):
        rows = _catalog_rows()
        ids = [row["id"] for row in rows]
        names = [row["name"].casefold() for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue({
            "apple-iphone-16-128",
            "apple-ipad-a16-128",
            "ps5-slim-digital-bundle",
            "samsung-galaxy-a55",
        }.issubset(ids))
        for row in rows:
            self.assertTrue(row.get("image_url"), row["id"])
            self.assertTrue(row.get("product_url"), row["id"])

    def test_frontend_entry_and_assets_are_served(self):
        page = self.client.get("/")
        stylesheet = self.client.get("/styles.css")
        vision = self.client.get("/vision.html")

        self.assertEqual(page.status_code, 200)
        self.assertIn(b"NEXUS", page.data)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertEqual(vision.status_code, 200)
        page.close()
        stylesheet.close()
        vision.close()
        self.assertEqual(self.client.get("/.env").status_code, 404)

    def test_startup_refreshes_existing_catalog_prices(self):
        catalog_row = _catalog_rows()[0]
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory) / 'existing.db'}"
            engine = create_engine(database_url)
            Base.metadata.create_all(engine)
            factory = sessionmaker(bind=engine)
            with factory() as db:
                db.add(Product(
                    id=catalog_row["id"],
                    name=catalog_row["name"],
                    category=catalog_row["category"],
                    tag=catalog_row["tag"],
                    description=catalog_row["description"],
                    price=1,
                    glyph=catalog_row["glyph"],
                ))
                db.commit()
            engine.dispose()

            app = create_app({
                "TESTING": True,
                "SECRET_KEY": "test-session-secret",
                "SQLALCHEMY_DATABASE_URI": database_url,
            })
            try:
                products = app.test_client().get("/api/products").get_json()["products"]
                refreshed = next(item for item in products if item["id"] == catalog_row["id"])
                self.assertEqual(refreshed["price"], catalog_row["price"])
            finally:
                app.extensions["nexus_engine"].dispose()

    def test_order_requires_csrf_and_server_calculates_total(self):
        self.assertEqual(
            self.client.post("/api/orders", json={}).status_code,
            403,
        )
        response = self.create_order()
        self.assertEqual(response.status_code, 201)
        order = response.get_json()["order"]
        self.assertEqual(order["status"], "pendiente")
        self.assertGreater(order["total"], 0)
        self.assertEqual(order["total"], 2 * order["items"][0]["unit_price"])

    def test_rejection_requires_reason_and_review_is_one_way(self):
        order = self.create_order().get_json()["order"]
        self.assertEqual(
            self.client.post(
                f"/api/admin/orders/{order['id']}/decision",
                json={"decision": "approved"},
                headers=self.request_headers(),
            ).status_code,
            401,
        )
        self.login_as_admin()
        no_reason = self.client.post(
            f"/api/admin/orders/{order['id']}/decision",
            json={"decision": "rejected", "note": ""},
            headers=self.request_headers(),
        )
        self.assertEqual(no_reason.status_code, 400)
        approved = self.client.post(
            f"/api/admin/orders/{order['id']}/decision",
            json={"decision": "approved"},
            headers=self.request_headers(),
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.get_json()["order"]["status"], "aprobada")
        duplicate = self.client.post(
            f"/api/admin/orders/{order['id']}/decision",
            json={"decision": "rejected", "note": "No cumple la simulación"},
            headers=self.request_headers(),
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_invalid_product_is_rejected(self):
        response = self.client.post(
            "/api/orders",
            json={
                "customer_name": "Estudiante",
                "customer_email": "estudiante@example.com",
                "items": [{"product_id": "no-existe", "quantity": 1}],
            },
            headers=self.request_headers(),
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
