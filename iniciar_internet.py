"""BIM DOC MANAGER 7.0 — acceso por enlace temporal, sin correo.

Expone el servidor web local solamente a través de un Quick Tunnel HTTPS
Cloudflare. Cualquier persona que reciba el enlace COMPLETO, incluida la
clave ?key=, puede abrir su propio espacio de trabajo temporal.
Los documentos no se escriben en carpetas permanentes del proyecto.

No se solicita correo ni contraseña. El enlace actúa como una credencial:
no debe publicarse donde terceros puedan obtenerlo.
"""
from __future__ import annotations

import json
import os
import queue
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from mobile_web import SessionStore, server_factory

ROOT = Path(__file__).resolve().parent
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com\b", re.IGNORECASE)


def find_cloudflared() -> str | None:
    """Localiza cloudflared instalado; no descarga ni ejecuta nada desconocido."""
    paths = [ROOT / "cloudflared.exe", ROOT / "cloudflared"]
    for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        root = os.environ.get(env_name)
        if root:
            paths.append(Path(root) / "cloudflared" / "cloudflared.exe")
    for executable in paths:
        if executable.is_file():
            return str(executable)
    return shutil.which("cloudflared")


def tunnel_command(cloudflared: str, port: int) -> list[str]:
    """Túnel de prueba sin autenticación por email, con API protegida por clave.

    El comando sin banderas extra funciona con las versiones soportadas de
    cloudflared y genera una dirección trycloudflare.com temporal.
    """
    return [cloudflared, "tunnel", "--url", f"http://127.0.0.1:{port}"]


def remote_url(message: str, key: str) -> str | None:
    """Extrae el dominio HTTPS de los logs o salida JSON de cloudflared."""
    candidate = URL_PATTERN.search(message.replace("\\/", "/"))
    if not candidate:
        try:
            line = json.loads(message)
            if isinstance(line, dict):
                for item in line.values():
                    if isinstance(item, str):
                        candidate = URL_PATTERN.search(item)
                        if candidate:
                            break
        except (ValueError, TypeError):
            return None
    if candidate:
        return candidate.group().rstrip("/") + "/?key=" + quote(key, safe="")
    return None


def _listen_tunnel(proc: subprocess.Popen, events: queue.Queue) -> None:
    try:
        for line in proc.stdout:
            events.put(line.rstrip())
    finally:
        events.put(None)


def run(cloudflared: str, ready_timeout: float = 65.0) -> int:
    """Arranca el túnel, mantiene la sesión activa y limpia al terminar."""
    # 256 bits de entropía por sesión. No se guarda en disco.
    key = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="bim_doc_internet_") as temp_dir:
        sessions = SessionStore(Path(temp_dir))
        # No exponer este puerto directamente a la red local o a Internet.
        server = ThreadingHTTPServer(("127.0.0.1", 0), server_factory(sessions, key))
        port = server.server_address[1]
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        events: queue.Queue = queue.Queue()
        proc = None
        try:
            print("\n" + "=" * 70)
            print("  BIM DOC MANAGER 7.0 — ACCESO REMOTO POR ENLACE")
            print("=" * 70)
            print("  Sin correo ni códigos de verificación.")
            print("  Creando enlace HTTPS para entrar desde cualquier red…\n")

            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.Popen(
                tunnel_command(cloudflared, port),
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **kwargs,
            )
            threading.Thread(target=_listen_tunnel, args=(proc, events), daemon=True).start()
            deadline = time.monotonic() + ready_timeout
            recent = []
            link = None
            while time.monotonic() < deadline and link is None:
                try:
                    line = events.get(timeout=0.5)
                except queue.Empty:
                    if proc.poll() is not None:
                        break
                    continue
                if line is None:
                    break
                recent.append(line)
                recent = recent[-12:]
                link = remote_url(line, key)
                if any(word in line.lower() for word in ("error", "fatal", "failed")):
                    print("  Aviso de Cloudflare:", line[:240])

            if link is None:
                print("\n  No se pudo generar el enlace HTTPS.")
                print("  Verifica Internet y que cloudflared esté instalado.")
                for line in recent[-5:]:
                    print("  " + line[:240])
                return 1

            print("\n  ENLACE PARA COMPARTIR CON TUS COMPAÑEROS:")
            print("\n    " + link + "\n")
            print("  1) Copia TODO el enlace, incluyendo la clave después de ?key=.")
            print("  2) Envíalo por privado a las personas que quieras invitar.")
            print("  3) Podrán entrar por cualquier Wi-Fi o datos móviles SIN correo.")
            print("  4) Cada navegador tiene sus propios documentos independientes.")
            print("  5) Mantén abierto este computador y descarga el ZIP antes de salir.")
            print("\n  IMPORTANTE: Cualquiera con el enlace COMPLETO tendrá acceso a")
            print("  la aplicación. No lo publiques en redes sociales.")
            print("  El enlace cambia cada vez que inicias el programa.")
            print("\n  Ctrl+C para cerrar el acceso remoto.\n")
            try:
                while proc.poll() is None:
                    time.sleep(0.4)
            except KeyboardInterrupt:
                print("\n  Cerrando acceso remoto…")
            return 0
        except OSError as exc:
            print(f"  Error al iniciar Cloudflare Tunnel: {exc}")
            return 1
        finally:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=4)
            server.shutdown()
            server.server_close()
            worker.join(timeout=4)
            print("  Acceso cerrado; se eliminaron los archivos temporales.")


def main() -> int:
    executable = find_cloudflared()
    if not executable:
        print("\nNo se encontró cloudflared (Cloudflare Tunnel).\n")
        print("Primero ejecuta INSTALAR_CLOUDFLARED.bat.")
        print("O usa PowerShell: winget install --id Cloudflare.cloudflared -e")
        print("Descarga oficial: https://developers.cloudflare.com/tunnel/downloads/")
        print("Después abre INICIAR_INTERNET.bat.\n")
        return 1
    return run(executable)


if __name__ == "__main__":
    raise SystemExit(main())
