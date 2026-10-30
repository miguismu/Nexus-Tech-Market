# -*- coding: utf-8 -*-
"""Genera un certificado HTTPS local confiable para NEXUS (candado en Chrome).

Ejecuta:  python make_cert.py

Crea certs/localhost.crt y certs/localhost.key con el nombre "localhost" y
confía el certificado en el almacén de Windows (Usuarios actuales), de modo que
Chrome muestre el candado al abrir https://localhost:5500.
"""

from __future__ import annotations

import subprocess
import ipaddress
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CERT_DIR = ROOT / "certs"
CERT_FILE = CERT_DIR / "localhost.crt"
KEY_FILE = CERT_DIR / "localhost.key"


def _run(command: list[str]) -> bool:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr or result.stdout)
        return False
    return True


def _openssl_command() -> list[str] | None:
    """Busca OpenSSL: en PATH, en Python (cryptography) o genera con cryptography."""
    try:
        subprocess.run(["openssl", "version"], capture_output=True)
        return ["openssl"]
    except FileNotFoundError:
        pass
    for candidate in (
        r"C:\Program Files\Git\usr\bin\openssl.exe",
        r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
        r"C:\Program Files (x86)\OpenSSL-Win64\bin\openssl.exe",
    ):
        if Path(candidate).exists():
            return [candidate]
    return None


def generate_certificate() -> bool:
    CERT_DIR.mkdir(exist_ok=True)
    try:
        # Preferido: cryptography (viene incluido con pip, sin OpenSSL externo)
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        import datetime

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        san = x509.SubjectAlternativeName(
            [x509.DNSName("localhost"), x509.DNSName("127.0.0.1"), x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]
        )
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=825))
            .add_extension(san, critical=False)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256())
        )
        KEY_FILE.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
        CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        return True
    except ImportError:
        pass
    openssl = _openssl_command()
    if openssl is None:
        print("Instala la librería cryptography con:  py -m pip install cryptography")
        return False
    command = openssl + [
        "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(KEY_FILE), "-out", str(CERT_FILE),
        "-days", "825", "-subj", "/CN=localhost",
        "-addext", "subjectAltName=DNS:localhost,DNS:127.0.0.1,IP:127.0.0.1",
        "-addext", "extendedKeyUsage=serverAuth",
    ]
    return _run(command)


def trust_certificate() -> None:
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "Import-Certificate -FilePath '%s' -CertStoreLocation Cert:\\CurrentUser\\Root"
                % CERT_FILE,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("Certificado instalado en CurrentUser\\Root.")
        else:
            print("No se pudo instalar el certificado. Ejecuta este script con la cuenta que usa Chrome.")
    except Exception as error:  # noqa: BLE001
        print("No se pudo confiar el certificado automáticamente:", error)


if __name__ == "__main__":
    if generate_certificate():
        trust_certificate()
        print("Listo. Ejecuta `py run_https.py` y abre https://localhost:5500")
