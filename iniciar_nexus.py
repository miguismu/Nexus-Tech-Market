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
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "nexus-server.log"
CODE_FILE = ROOT / ".admin-code"


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
    env = os.environ.copy()
    if env.get("NEXUS_ADMIN_CODE"):
        return
    if CODE_FILE.exists():
        env["NEXUS_ADMIN_CODE"] = CODE_FILE.read_text(encoding="utf-8").strip()
    else:
        import secrets
        code = secrets.token_urlsafe(12)
        CODE_FILE.write_text(code, encoding="utf-8")
        env["NEXUS_ADMIN_CODE"] = code
    os.environ.clear()
    os.environ.update(env)


def main() -> None:
    if "--detener" in sys.argv:
        stop_all()
        return

    ensure_admin_code()

    if sys.platform == "win32":
        # DETACHED_PROCESS: sobrevive al cierre de la terminal/VS Code.
        creationflags = 0x00000008 | 0x00000200  # DETACHED | NEW_PROCESS_GROUP
        with LOG.open("ab") as log:
            process = subprocess.Popen(
                [sys.executable, "-X", "utf8", str(ROOT / "server.py")],
                cwd=ROOT, stdout=log, stderr=log,
                creationflags=creationflags,
            )
    else:
        with LOG.open("ab") as log:
            process = subprocess.Popen(
                [sys.executable, "-X", "utf8", str(ROOT / "server.py")],
                cwd=ROOT, stdout=log, stderr=log,
                start_new_session=True,
            )

    time.sleep(3)
    if process.poll() is None:
        print("NEXUS activo en https://localhost:5000 (PID", process.pid, ").")
        print("Log:", LOG)
        print("Código del panel de administración:", CODE_FILE.read_text(encoding="utf-8").strip())
        print("Administrador: Miguel Alejandro Muñoz Suárez")
    else:
        print("El servidor no arrancó. Revisa", LOG)


if __name__ == "__main__":
    main()
