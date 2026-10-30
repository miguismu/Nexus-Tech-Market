"""Inicia la API NEXUS por HTTPS local para usar con Live Server seguro."""

from __future__ import annotations

import os
import secrets
import ssl
from socketserver import ThreadingMixIn
from pathlib import Path
from wsgiref.simple_server import WSGIServer, make_server

ROOT = Path(__file__).resolve().parent
CERT_FILE = ROOT / "certs" / "localhost.crt"
KEY_FILE = ROOT / "certs" / "localhost.key"


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    allow_reuse_address = True
    ssl_context: ssl.SSLContext

    def get_request(self):
        client_socket, address = super().get_request()
        try:
            return self.ssl_context.wrap_socket(client_socket, server_side=True), address
        except Exception:
            client_socket.close()
            raise


def main() -> None:
    if not CERT_FILE.is_file() or not KEY_FILE.is_file():
        raise SystemExit("Falta el certificado. Ejecuta `py make_cert.py` y vuelve a iniciar.")

    os.environ["NEXUS_HTTPS"] = "true"
    admin_code_file = ROOT / ".admin-code"
    admin_code = os.environ.get("NEXUS_ADMIN_CODE")
    if not admin_code:
        if admin_code_file.is_file():
            admin_code = admin_code_file.read_text(encoding="utf-8").strip()
        else:
            admin_code = secrets.token_urlsafe(12)
            admin_code_file.write_text(admin_code, encoding="utf-8")
        os.environ["NEXUS_ADMIN_CODE"] = admin_code
    from server import create_app

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(CERT_FILE, KEY_FILE)
    ThreadingWSGIServer.ssl_context = context
    httpd = make_server("127.0.0.1", 5443, create_app(), server_class=ThreadingWSGIServer)
    print("API NEXUS segura en https://localhost:5443 (Ctrl+C para detener).")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
