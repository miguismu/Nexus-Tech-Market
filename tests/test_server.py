import unittest
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from server import ApplicationMetadata, Base, Product, _catalog_rows, create_app


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

    def test_assistant_does_not_repeat_unrecognized_speech(self):
        response = self.client.post("/api/assistant", json={"message": "consulta no reconocida"})
        self.assertEqual(response.status_code, 200)
        answer = response.get_json()["answer"]
        self.assertNotIn("Te escuché decir", answer)
        self.assertIn("¿Qué necesitas saber?", answer)

    def test_corrected_product_images_are_distinct_and_served(self):
        products = {row["id"]: row for row in _catalog_rows()}
        product_ids = (
            "surface-go-4",
            "microsoft-surface-go-windows-tablet",
            "hp-elite-x3",
            "hp-elite-x3-desk-dock",
        )
        image_paths = [products[product_id]["image_url"] for product_id in product_ids]

        self.assertEqual(len(image_paths), len(set(image_paths)))
        for image_path in image_paths:
            if urlsplit(image_path).scheme in {"http", "https"}:
                self.assertTrue(urlsplit(image_path).netloc, image_path)
                continue
            response = self.client.get(f"/{image_path}")
            self.assertEqual(response.status_code, 200, image_path)
            self.assertIn(response.mimetype, {"image/svg+xml", "image/jpeg"}, image_path)
            response.close()

        api_products = {
            product["id"]: product
            for product in self.client.get("/api/products").get_json()["products"]
        }
        order_response = self.client.post(
            "/api/orders",
            json={
                "customer_name": "Estudiante de prueba",
                "customer_email": "estudiante@example.com",
                "items": [{"product_id": product_id, "quantity": 1} for product_id in product_ids],
            },
            headers=self.request_headers(),
        )
        self.assertEqual(order_response.status_code, 201)
        order = order_response.get_json()["order"]
        self.assertTrue(order["payment_code"].startswith("PAY-"))
        self.assertEqual(
            order["total"],
            sum(api_products[product_id]["price"] for product_id in product_ids),
        )

    def test_surface_go_4_has_product_photo_and_used_price_reference(self):
        surface = next(row for row in _catalog_rows() if row["id"] == "surface-go-4")
        self.assertEqual(
            surface["image_url"],
            "https://cdn.a1tech.deals/products/A1T-HF8YYCGWZ1/0_d8255f52.jpg",
        )
        self.assertEqual(surface["price"], 796236)
        self.assertEqual(surface["checked_on"], "2026-11-03")
        self.assertIn("US$249,99", surface["description"])
        self.assertIn("Foto ilustrativa", surface["seller"])

    def test_hp_elite_x3_bundle_has_real_photo_and_labeled_used_price_reference(self):
        hp = next(row for row in _catalog_rows() if row["id"] == "hp-elite-x3-desk-dock")
        self.assertEqual(
            hp["image_url"],
            "https://upload.wikimedia.org/wikipedia/commons/8/8e/HP_Elite_X3.jpg",
        )
        self.assertEqual(hp["price"], 716625)
        self.assertEqual(hp["checked_on"], "2026-11-03")
        self.assertIn("US$150–300", hp["description"])
        self.assertIn("Languaeditor / Wikimedia Commons", hp["seller"])
        self.assertIn("el dock no aparece", hp["seller"])

    def test_xbox_series_s_uses_official_product_image(self):
        xbox = next(row for row in _catalog_rows() if row["id"] == "xbox-series-s")
        self.assertEqual(xbox["name"], "Xbox Series S 512 GB")
        self.assertEqual(
            xbox["image_url"],
            "https://assets.xboxservices.com/assets/24/d0/"
            "24d00bc1-5aac-48ad-bed8-398cbebaefa4.jpg?n=XSS_Sharing_200x200.jpg",
        )

    def test_surface_go_1_uses_real_product_photo_and_labeled_used_price_reference(self):
        surface = next(
            row for row in _catalog_rows()
            if row["id"] == "microsoft-surface-go-windows-tablet"
        )
        self.assertEqual(surface["image_url"], "images/surface-go-1.jpg")
        self.assertEqual(surface["price"], 750000)
        self.assertEqual(surface["checked_on"], "2026-11-03")
        self.assertIn("no una oferta confirmada", surface["description"])
        self.assertIn("Wikimedia Commons (CC0)", surface["seller"])

        image_path = Path(__file__).resolve().parents[1] / surface["image_url"]
        with image_path.open("rb") as image_file:
            self.assertEqual(image_file.read(3), b"\xff\xd8\xff")
        image = self.client.get(f"/{surface['image_url']}")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.mimetype, "image/jpeg")
        image.close()

    def test_samsung_galaxy_a55_is_restored_with_its_own_product_image(self):
        xbox_and_a55 = {row["id"]: row for row in _catalog_rows()}
        a55 = xbox_and_a55["samsung-galaxy-a55"]
        self.assertEqual(a55["name"], "Samsung Galaxy A55 5G · 256 GB")
        self.assertIn("Super AMOLED", a55["description"])
        self.assertGreater(a55["price"], 0)
        self.assertEqual(a55["image_url"], "images/samsung-galaxy-a55.svg")
        image = self.client.get(f"/{a55['image_url']}")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.mimetype, "image/svg+xml")
        image.close()

    def test_database_contains_application_purpose_and_contents(self):
        with self.app.extensions["nexus_session_factory"]() as db:
            metadata = {
                row.metadata_key: row.value
                for row in db.scalars(select(ApplicationMetadata)).all()
            }
        self.assertEqual(metadata["name"], "NEXUS Tech Market")
        self.assertIn("solicitudes", metadata["purpose"])
        self.assertIn("purchase_requests", metadata["database_contents"])
        self.assertIn("asistente de voz", metadata["features"])
        self.assertIn("no procesa pagos", metadata["payment_notice"])

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

    def test_miguismu_local_domain_is_allowed_for_live_server_api(self):
        origin = "https://miguismu-nexus-tech-market.127.0.0.1.sslip.io:5501"
        response = self.client.get("/api/health", headers={"Origin": origin})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")
        untrusted = self.client.get(
            "/api/health",
            headers={"Origin": "https://example.com"},
        )
        self.assertNotIn("Access-Control-Allow-Origin", untrusted.headers)

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
                a55 = next(row for row in _catalog_rows() if row["id"] == "samsung-galaxy-a55")
                db.add(Product(
                    id=a55["id"],
                    name="Samsung Galaxy A57 5G · 256 GB",
                    category=a55["category"],
                    tag=a55["tag"],
                    description="Datos antiguos del Galaxy A57.",
                    price=2499900,
                    glyph=a55["glyph"],
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
                with app.extensions["nexus_session_factory"]() as db:
                    restored = db.get(Product, "samsung-galaxy-a55")
                    self.assertEqual(restored.name, a55["name"])
                    self.assertEqual(restored.price, a55["price"])
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

    def test_payment_code_verification_returns_order_products_without_customer_data(self):
        order = self.create_order().get_json()["order"]
        response = self.client.get(f"/api/orders/verify/{order['payment_code'].lower()}")

        self.assertEqual(response.status_code, 200)
        verified = response.get_json()
        self.assertEqual(verified["payment_code"], order["payment_code"])
        self.assertEqual(verified["number"], order["number"])
        self.assertEqual(
            verified["items"],
            [{
                "product_id": order["items"][0]["product_id"],
                "product_name": order["items"][0]["product_name"],
                "quantity": order["items"][0]["quantity"],
            }],
        )
        self.assertNotIn("customer_name", verified)
        self.assertNotIn("customer_email", verified)

    def test_payment_code_verification_reports_unknown_codes(self):
        response = self.client.get("/api/orders/verify/PAY-000000-0000000000")
        self.assertEqual(response.status_code, 404)
        self.assertIn("código", response.get_json()["error"].lower())

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
