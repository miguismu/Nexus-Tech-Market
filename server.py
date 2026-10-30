"""Backend de demostración para NEXUS Tech Market."""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory, session
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


ROOT = Path(__file__).resolve().parent
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_ORIGINS = {
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:5501",
    "http://localhost:5501",
    "https://127.0.0.1:5500",
    "https://localhost:5500",
    "https://127.0.0.1:5501",
    "https://localhost:5501",
}
PRODUCT_FIELDS = ("id", "name", "category", "tag", "description", "price", "glyph")


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    tag: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    glyph: Mapped[str] = mapped_column(String(12), nullable=False)


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    payment_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(254), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pendiente")
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_note: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list["PurchaseItem"]] = relationship(
        back_populates="purchase_request", cascade="all, delete-orphan"
    )


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(140), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_request: Mapped[PurchaseRequest] = relationship(back_populates="items")


def _catalog_rows() -> list[dict[str, Any]]:
    with (ROOT / "catalog.json").open(encoding="utf-8") as catalog_file:
        rows = json.load(catalog_file)
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("catalog.json debe contener una lista de productos.")
    return rows


def _error(message: str, status: int):
    return jsonify({"error": message}), status


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("NEXUS_SESSION_SECRET") or secrets.token_urlsafe(32),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", f"sqlite:///{(ROOT / 'nexus.db').as_posix()}"
        ),
        ADMIN_ACCESS_CODE=os.environ.get("NEXUS_ADMIN_CODE") or secrets.token_urlsafe(12),
        ADMIN_NAME=os.environ.get("NEXUS_ADMIN_NAME") or "Miguel Alejandro Muñoz Suárez",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("NEXUS_HTTPS", "").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
        MAX_CONTENT_LENGTH=32 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    database_url = app.config["SQLALCHEMY_DATABASE_URI"]
    engine_options: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
    engine = create_engine(database_url, **engine_options)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    app.extensions["nexus_session_factory"] = session_factory
    app.extensions["nexus_engine"] = engine

    with session_factory() as db:
        products_by_id = {product.id: product for product in db.scalars(select(Product)).all()}
        for row in _catalog_rows():
            product = products_by_id.get(row["id"])
            if product is None:
                # catalog.json also carries image/store metadata that is not SQL model data.
                db.add(Product(**{field: row[field] for field in PRODUCT_FIELDS}))
                continue
            for field in PRODUCT_FIELDS[1:]:
                setattr(product, field, row[field])
        db.commit()

    if not os.environ.get("NEXUS_ADMIN_CODE") and not app.config.get("TESTING"):
        app.logger.warning(
            "Código local del panel NEXUS (secreto; no lo publiques): %s",
            app.config["ADMIN_ACCESS_CODE"],
        )
    app.logger.info("Administrador de NEXUS: %s", app.config["ADMIN_NAME"])

    @app.after_request
    def add_security_headers(response):
        origin = request.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.vary.add("Origin")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    @app.get("/index.html")
    def storefront():
        return send_from_directory(ROOT, "index.html")

    @app.get("/<path:filename>")
    def frontend_files(filename: str):
        public_files = {
            "app.js",
            "assistant.js",
            "catalog.json",
            "favicon.svg",
            "styles.css",
            "vision.html",
        }
        if filename.startswith("images/"):
            requested = filename.split("/", 1)[1]
            if ".." in requested or "/" in requested or "\\" in requested:
                return _error("No existe ese recurso.", 404)
            return send_from_directory(ROOT / "images", requested)
        if filename not in public_files:
            return _error("No existe ese recurso.", 404)
        return send_from_directory(ROOT, filename)

    def csrf_is_valid() -> bool:
        stored = session.get("csrf_token", "")
        supplied = request.headers.get("X-CSRF-Token", "")
        return bool(stored and supplied and hmac.compare_digest(stored, supplied))

    def require_csrf():
        if not csrf_is_valid():
            return _error("Token de seguridad inválido o vencido. Recarga la página e inténtalo de nuevo.", 403)
        return None

    def require_admin():
        if not session.get("nexus_admin"):
            return _error("Debes iniciar sesión en el panel de revisión.", 401)
        return None

    def serialize_order(order: PurchaseRequest) -> dict[str, Any]:
        created_at = order.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return {
            "id": order.id,
            "number": order.number,
            "payment_code": order.payment_code,
            "customer_name": order.customer_name,
            "status": order.status,
            "total": order.total,
            "decision_note": order.decision_note,
            "created_at": created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "items": [
                {
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                }
                for item in order.items
            ],
        }

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "database": "postgresql" if database_url.startswith("postgres") else "sqlite"})

    @app.get("/api/security")
    def security_token():
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return jsonify({"csrf_token": session["csrf_token"]})

    @app.get("/api/orders/verify/<code>")
    def verify_purchase(code: str):
        """Consulta pública del estado de una compra por código de pago (sin datos personales)."""
        clean = code.strip().upper()
        if not 6 <= len(clean) <= 40:
            return _error("Código de compra inválido.", 400)
        with session_factory() as db:
            order = db.scalars(
                select(PurchaseRequest).where(PurchaseRequest.payment_code == clean)
            ).first()
            if order is None:
                return _error("No encontramos una compra con ese código.", 404)
            return jsonify({
                "number": order.number,
                "payment_code": order.payment_code,
                "status": order.status,
                "total": order.total,
                "created_at": order.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            })

    @app.post("/api/assistant")
    def assistant():
        """Reglas locales del asistente NEXUS; el navegador lee la respuesta en voz alta."""
        data = request.get_json(silent=True)
        message = data.get("message") if isinstance(data, dict) else None
        if not isinstance(message, str) or not message.strip() or len(message) > 300:
            return _error("Escribe una consulta válida de hasta 300 caracteres.", 400)
        return jsonify({"answer": _assistant_reply(message.strip())})

    def _assistant_reply(message: str) -> str:
        text = message.lower()
        if re.fullmatch(r"\s*(hola|holi|buenos d[ií]as|buenas tardes|buenas noches|quiubo|qu[eé] m[aá]s)[!. ¡¿?]*\s*", text):
            return "¡Hola! Qué gusto saludarte. Soy Extremo NEXUS. Puedes preguntarme por productos, precios, el carrito o cómo crear una solicitud de compra."
        if any(k in text for k in ("quién eres", "quien eres", "cómo te llamas", "como te llamas", "qué puedes hacer", "que puedes hacer")):
            return "Soy Extremo NEXUS, el asistente de esta tienda académica. Te ayudo a explorar productos, revisar cotizaciones y entender las solicitudes de compra."
        if any(k in text for k in ("pay-", "pay ", "código de compra", "codigo de compra", "verificar", "verifica")):
            return ("Cuando registras una compra, NEXUS genera un código PAY con firma HMAC: "
                    "por ejemplo PAY-261029-A1B2C3D4E5. Escríbelo en el consultor de compras de la "
                    "portada para ver el estado de tu orden en segundos.")
        if any(k in text for k in ("voz", "habla", "audio", "escuch", "microfono")):
            return ("Tengo voz propia: pulsa el botón 🎙 para hablar y te responderé en voz alta con "
                    "mi esfera animada. Puedes silenciarme con el botón de altavoz.")
        if any(k in text for k in ("precio", "cotiz", "cuesta", "valor", "cuánto", "cuanto")):
            return ("Los valores de cada ficha son cotizaciones de referencia en pesos colombianos, "
                    "con fecha de consulta. Usa la pestaña «Descargar» de cada ficha para guardar la "
                    "cotización con su código.")
        if any(k in text for k in ("compr", "carrito", "solicitud", "pedido", "pago")):
            return ("Añade productos al carrito y elige «Crear solicitud». Al registrarse descargas la "
                    "constancia y el registro de pago simulado. No se procesan pagos reales.")
        if any(k in text for k in ("aprob", "rechaz", "revisi", "panel", "estado")):
            return ("Las solicitudes quedan pendientes hasta que una persona revisora las apruebe o "
                    "rechace en el panel con el código de seguridad de la terminal.")
        if any(k in text for k in ("gamer", "juego", "handheld", "legion", "rog", "redmagic")):
            return ("En la categoría «Videojuegos» y «Celulares Gamer» tienes ROG Ally, ROG Ally X, "
                    "ROG Xbox Ally, Legion Go, ROG Phone 9 Pro y REDMAGIC 10 Pro, todos con precio en COP.")
        if any(k in text for k in ("windows", "lumia", "surface", "microsoft")):
            return ("La categoría «Celulares Windows» reúne Lumia 1520, Lumia 1320, HP Elite x3 y el "
                    "Surface Duo 2; son referencias de colección e importación con precio en COP.")
        if any(k in text for k in ("catálogo", "catalogo", "producto", "celular", "tablet", "computador")):
            return ("Filtra el catálogo por categoría o busca por nombre. Cada ficha incluye imagen, "
                    "cotización descargable y enlace a la tienda de referencia.")
        if any(k in text for k in ("segur", "candado", "https", "código", "codigo", "clave")):
            return ("La página usa CSRF, cookies HttpOnly y cabeceras de seguridad. Para el candado "
                    "HTTPS ejecuta el backend con run_https.py y acepta el certificado local.")
        return (f"Te escuché decir: «{message.strip()}». Puedo ayudarte con el catálogo, las características y precios de referencia, "
                "el carrito, las cotizaciones o las solicitudes de compra. ¿Qué quieres consultar?")

    @app.get("/api/products")
    def products():
        catalog_by_id = {row["id"]: row for row in _catalog_rows()}
        with session_factory() as db:
            rows = db.scalars(select(Product).order_by(Product.category, Product.name)).all()
            return jsonify({
                "products": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "category": item.category,
                        "tag": item.tag,
                        "description": item.description,
                        "price": item.price,
                        "glyph": item.glyph,
                        "image_url": catalog_by_id[item.id].get("image_url", ""),
                        "product_url": catalog_by_id[item.id].get("product_url", ""),
                        "seller": catalog_by_id[item.id].get("seller", ""),
                        "checked_on": catalog_by_id[item.id].get("checked_on", ""),
                    }
                    for item in rows
                    if item.id in catalog_by_id
                ]
            })

    @app.post("/api/orders")
    def create_order():
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _error("El cuerpo de la solicitud debe ser JSON válido.", 400)
        name = data.get("customer_name")
        email = data.get("customer_email")
        requested_items = data.get("items")
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 100:
            return _error("Escribe un nombre de 2 a 100 caracteres.", 400)
        if not isinstance(email, str) or len(email) > 254 or not EMAIL_PATTERN.fullmatch(email.strip()):
            return _error("Escribe un correo electrónico válido.", 400)
        if not isinstance(requested_items, list) or not 1 <= len(requested_items) <= 20:
            return _error("La solicitud debe incluir entre 1 y 20 productos.", 400)

        requested: dict[str, int] = {}
        for item in requested_items:
            if not isinstance(item, dict):
                return _error("Hay un producto con formato inválido.", 400)
            product_id, quantity = item.get("product_id"), item.get("quantity")
            if (
                not isinstance(product_id, str)
                or not product_id
                or isinstance(quantity, bool)
                or not isinstance(quantity, int)
                or not 1 <= quantity <= 10
            ):
                return _error("Cada producto debe tener un identificador y una cantidad entre 1 y 10.", 400)
            requested[product_id] = requested.get(product_id, 0) + quantity
            if requested[product_id] > 10:
                return _error("La cantidad máxima por producto es 10.", 400)

        with session_factory() as db:
            catalog = {
                product.id: product
                for product in db.scalars(select(Product).where(Product.id.in_(requested))).all()
            }
            if len(catalog) != len(requested):
                return _error("Uno o más productos ya no están disponibles en el catálogo.", 400)
            items = [
                PurchaseItem(
                    product_id=product.id,
                    product_name=product.name,
                    quantity=quantity,
                    unit_price=product.price,
                )
                for product_id, quantity in requested.items()
                for product in [catalog[product_id]]
            ]
            total = sum(item.unit_price * item.quantity for item in items)
            number = f"NX-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(3).upper()}"
            # Código de compra verificador: HMAC del número de orden con el secreto de sesión.
            digest = hmac.new(
                app.config["SECRET_KEY"].encode(), number.encode(), hashlib.sha256
            ).hexdigest()[:10].upper()
            payment_code = f"PAY-{number[3:]}-{digest}"
            order = PurchaseRequest(
                number=number,
                payment_code=payment_code,
                customer_name=name.strip(),
                customer_email=email.strip().lower(),
                status="pendiente",
                total=total,
                items=items,
            )
            db.add(order)
            db.commit()
            return jsonify({"order": serialize_order(order)}), 201

    @app.post("/api/admin/login")
    def admin_login():
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        data = request.get_json(silent=True)
        code = data.get("code") if isinstance(data, dict) else None
        expected = app.config["ADMIN_ACCESS_CODE"]
        admin_name = app.config["ADMIN_NAME"]
        valid_code = isinstance(code, str) and hmac.compare_digest(code, expected)
        valid_name = (
            isinstance(data, dict)
            and isinstance(data.get("admin"), str)
            and hmac.compare_digest(
                data["admin"].strip().casefold().encode("utf-8"),
                admin_name.casefold().encode("utf-8"),
            )
        )
        if not (valid_code and valid_name):
            return _error("Credenciales incorrectas: usa tu nombre completo y el código de seguridad.", 401)
        session.clear()
        session["csrf_token"] = secrets.token_urlsafe(32)
        session["nexus_admin"] = True
        session["nexus_admin_name"] = admin_name
        session.permanent = True
        return jsonify({"authenticated": True, "admin_name": admin_name, "csrf_token": session["csrf_token"]})

    @app.get("/api/admin/orders")
    def admin_orders():
        auth_error = require_admin()
        if auth_error:
            return auth_error
        with session_factory() as db:
            rows = db.scalars(
                select(PurchaseRequest).order_by(PurchaseRequest.created_at.desc()).limit(100)
            ).all()
            return jsonify({"orders": [serialize_order(order) for order in rows]})

    @app.post("/api/admin/orders/<int:order_id>/decision")
    def decide_order(order_id: int):
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        auth_error = require_admin()
        if auth_error:
            return auth_error
        data = request.get_json(silent=True)
        decision = data.get("decision") if isinstance(data, dict) else None
        note = data.get("note", "") if isinstance(data, dict) else ""
        if decision not in {"approved", "rejected"}:
            return _error("La decisión debe ser approved o rejected.", 400)
        if not isinstance(note, str) or len(note.strip()) > 250:
            return _error("El motivo no puede superar 250 caracteres.", 400)
        if decision == "rejected" and len(note.strip()) < 3:
            return _error("Escribe un motivo de al menos 3 caracteres para rechazar.", 400)

        with session_factory() as db:
            order = db.get(PurchaseRequest, order_id)
            if order is None:
                return _error("No existe esa solicitud.", 404)
            if order.status != "pendiente":
                return _error("Esta solicitud ya fue revisada y no puede cambiar de estado.", 409)
            order.status = "aprobada" if decision == "approved" else "rechazada"
            order.decision_note = note.strip()
            order.decided_at = datetime.now(timezone.utc)
            db.commit()
            return jsonify({"order": serialize_order(order)})

    @app.post("/api/admin/logout")
    def admin_logout():
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        session.clear()
        return jsonify({"authenticated": False})

    @app.errorhandler(413)
    def request_too_large(error):
        del error
        return jsonify({"error": "La solicitud excede el tamaño permitido."}), 413

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        app.logger.exception("Error de base de datos NEXUS: %s", error.__class__.__name__)
        return _error("No se pudo completar la operación en la base de datos.", 500)

    return app


if __name__ == "__main__":
    """Punto de entrada estable con waitress (evita ERR_CONNECTION_RESET de Werkzeug+TLS en Windows)."""
    app = create_app()
    from waitress import serve
    cert_file = ROOT / "certs" / "localhost.crt"
    key_file = ROOT / "certs" / "localhost.key"
    if cert_file.exists() and key_file.exists():
        print("NEXUS activo: http://localhost:5000 (waitress · estable)")
        print("Certificado local disponible; el candado HTTPS se obtiene con run_https.py o Live Server.")
    else:
        print("NEXUS activo: http://localhost:5000 (waitress · estable)")
    print("Administrador del panel: Miguel Alejandro Muñoz Suárez · código en .admin-code")
    serve(app, host="0.0.0.0", port=5000, threads=6, connection_limit=200, channel_timeout=120)
