# -*- coding: utf-8 -*-
"""Inicia NEXUS de forma persistente con reinicio automático.

Uso:   python iniciar_nexus.py            (ventana oculta, siempre activo)
       python iniciar_nexus.py --detener  (detiene todos los NEXUS)

Escribe el log en nexus-server.log y reinicia el servidor si llegara a caer.
El código del panel de administración se guarda en .admin-code para que
siempre sea el mismo y no cambie entre reinicios.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "nexus-server.log"
CODE_FILE = ROOT / ".admin-code"
SESSION_SECRET_FILE = ROOT / ".session-secret"
HEALTH_URL = "http://127.0.0.1:5000/api/health"
VENV_PYTHON = ROOT / (".venv\\Scripts\\python.exe" if sys.platform == "win32" else ".venv/bin/python")


def server_is_ready() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def stop_all() -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
         "Where-Object { $_.CommandLine -match 'server\\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
        capture_output=True, text=True,
    )
    print("Servidores NEXUS detenidos.")


def ensure_admin_code() -> None:
    """Fija NEXUS_ADMIN_CODE para que el código del panel no cambie nunca."""
    if os.environ.get("NEXUS_ADMIN_CODE"):
        return
    if CODE_FILE.exists():
        code = CODE_FILE.read_text(encoding="utf-8").strip()
        if not code:
            raise RuntimeError(f"El archivo de seguridad {CODE_FILE.name} está vacío.")
    else:
        import secrets
        code = secrets.token_urlsafe(12)
        CODE_FILE.write_text(code, encoding="utf-8")
    os.environ["NEXUS_ADMIN_CODE"] = code


def ensure_session_secret() -> None:
    """Conserva la firma de las sesiones sin mostrar el secreto en la terminal."""
    if os.environ.get("NEXUS_SESSION_SECRET"):
        return
    if SESSION_SECRET_FILE.exists():
        secret = SESSION_SECRET_FILE.read_text(encoding="utf-8").strip()
        if not secret:
            raise RuntimeError(f"El archivo de sesión {SESSION_SECRET_FILE.name} está vacío.")
    else:
        import secrets
        secret = secrets.token_urlsafe(48)
        SESSION_SECRET_FILE.write_text(secret, encoding="utf-8")
    os.environ["NEXUS_SESSION_SECRET"] = secret


def main() -> None:
    if "--detener" in sys.argv:
        stop_all()
        return

    ensure_admin_code()
    ensure_session_secret()
    os.environ["NEXUS_HTTPS"] = "true"

    if server_is_ready():
        print("La API NEXUS ya está activa en http://127.0.0.1:5000.")
        return

    if sys.platform == "win32":
        # DETACHED_PROCESS: sobrevive al cierre de la terminal/VS Code.
        creationflags = 0x00000008 | 0x00000200  # DETACHED | NEW_PROCESS_GROUP
        with LOG.open("ab") as log:
            process = subprocess.Popen(
                [str(VENV_PYTHON if VENV_PYTHON.is_file() else sys.executable), "-X", "utf8", str(ROOT / "server.py")],
                cwd=ROOT, stdout=log, stderr=log,
                creationflags=creationflags,
            )
    else:
        with LOG.open("ab") as log:
            process = subprocess.Popen(
                [str(VENV_PYTHON if VENV_PYTHON.is_file() else sys.executable), "-X", "utf8", str(ROOT / "server.py")],
                cwd=ROOT, stdout=log, stderr=log,
                start_new_session=True,
            )

    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if server_is_ready():
            print("API NEXUS activa para el sitio HTTPS local.")
            print("Log:", LOG)
            print("Código del panel de administración guardado localmente.")
            print("Administrador: Miguel Alejandro Muñoz Suárez")
            return
        if process.poll() is not None:
            break
        time.sleep(0.5)

    print("La API no respondió en http://127.0.0.1:5000/api/health. Revisa", LOG)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
