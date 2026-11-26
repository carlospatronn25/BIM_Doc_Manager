"""BIM DOC MANAGER 7.0: enlace HTTPS fijo por dominio gratuito de ngrok.

Requisitos: ngrok v3 configurado en una cuenta (config add-authtoken).
El dominio pertenece a la cuenta ngrok y no cambia al reiniciar. La clave
se crea una sola vez en el perfil local del usuario y tampoco cambia.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import urlopen

from mobile_web import SessionStore, server_factory

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".config")) / "BIM_Doc_Manager_7_0"
CONFIG_FILE = CONFIG_DIR / "enlace_fijo.json"
API_BASE = "http://127.0.0.1:4040/api"


def find_ngrok() -> str | None:
    for p in (ROOT / "ngrok.exe", ROOT / "ngrok"):
        if p.is_file():
            return str(p)
    return shutil.which("ngrok") or shutil.which("ngrok.exe")


def load_settings() -> dict:
    """No cambia una clave ya creada; si el archivo está corrupto, falla cerrado."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            settings = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Configuracion danada: {CONFIG_FILE}. {exc}") from exc
        if not isinstance(settings, dict) or not isinstance(settings.get("key"), str) or len(settings["key"]) < 32:
            raise ValueError(f"Clave de acceso no valida en {CONFIG_FILE}. No se generara otra automaticamente.")
        return settings
    settings = {"key": secrets.token_urlsafe(32), "public_url": ""}
    save_settings(settings, creating=True)
    return settings


def save_settings(settings: dict, *, creating: bool = False) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if creating:
        with CONFIG_FILE.open("x", encoding="utf-8") as file:
            json.dump(settings, file, ensure_ascii=False, indent=2)
    else:
        temporary = CONFIG_FILE.with_name(CONFIG_FILE.name + ".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(settings, file, ensure_ascii=False, indent=2)
        temporary.replace(CONFIG_FILE)
    try:
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass


def rotate_key() -> int:
    try:
        settings = load_settings()
        settings["key"] = secrets.token_urlsafe(32)
        save_settings(settings)
    except (OSError, ValueError) as exc:
        print("Error al cambiar la clave:", exc)
        return 1
    print("Clave cambiada. El enlace anterior dejara de funcionar en el proximo inicio.")
    print("La direccion HTTPS de ngrok seguira siendo la misma; cambia ?key=.")
    return 0


def local_api_in_use() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 4040), timeout=0.25):
            return True
    except OSError:
        return False


def endpoint_from_data(data: dict, port: int) -> str | None:
    """Busca SOLO el endpoint apuntado a nuestro servidor; nunca toma otro túnel."""
    upstream_end = f":{port}"
    for item in data.get("endpoints", []) + data.get("tunnels", []):
        if not isinstance(item, dict):
            continue
        public = item.get("url") or item.get("public_url", "")
        if not isinstance(public, str) or urlparse(public).scheme != "https":
            continue
        upstream = item.get("upstream", {}) or {}
        addr = upstream.get("url", "") if isinstance(upstream, dict) else ""
        config = item.get("config", {}) or {}
        if not addr and isinstance(config, dict):
            addr = config.get("addr", "")
        addr = str(addr).rstrip("/")
        if addr == str(port) or addr.endswith(upstream_end) or addr.endswith("/" + str(port)):
            return public.rstrip("/")
    return None


def lookup_public_url(port: int) -> str | None:
    for endpoint in ("/endpoints", "/tunnels"):
        try:
            with urlopen(API_BASE + endpoint, timeout=0.5) as resp:
                payload = json.load(resp)
            url = endpoint_from_data(payload, port)
            if url:
                return url
        except (URLError, HTTPError, TimeoutError, ValueError, OSError):
            continue
    return None


def _read_log(proc: subprocess.Popen, lines: list[str]) -> None:
    if proc.stdout is None:
        return
    for line in proc.stdout:
        lines.append(line.strip())
        if len(lines) > 30:
            del lines[:-30]


def main() -> int:
    if "--rotar-clave" in sys.argv:
        return rotate_key()

    executable = find_ngrok()
    if not executable:
        print("No se encontro ngrok. Ejecuta CONFIGURAR_NGROK.bat primero.")
        print("Descarga oficial: https://ngrok.com/download/windows")
        return 1
    if local_api_in_use():
        print("Ya hay un proceso usando 127.0.0.1:4040 (ngrok u otro programa).")
        print("Cierra ese tunel antes de iniciar el enlace fijo; no se usara el de otro proceso.")
        return 1
    try:
        settings = load_settings()
    except (OSError, ValueError) as exc:
        print("No se pudo cargar la clave privada:", exc)
        return 1

    with tempfile.TemporaryDirectory(prefix="bim_doc_fijo_") as temp:
        sessions = SessionStore(Path(temp))
        server = ThreadingHTTPServer(("127.0.0.1", 0), server_factory(sessions, settings["key"]))
        local_port = server.server_address[1]
        web_thread = threading.Thread(target=server.serve_forever, daemon=True)
        web_thread.start()
        proc = None
        logs: list[str] = []
        try:
            print("\n" + "=" * 68)
            print(" BIM DOC MANAGER 7.0 - ENLACE FIJO SIN CORREO")
            print("=" * 68)
            print(" Iniciando servidor local y conexion ngrok...\n")
            flags = {}
            if sys.platform == "win32":
                flags["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.Popen(
                [executable, "http", str(local_port), "--log=stdout"],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **flags,
            )
            threading.Thread(target=_read_log, args=(proc, logs), daemon=True).start()
            deadline = time.monotonic() + 45
            public_url = None
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                public_url = lookup_public_url(local_port)
                if public_url:
                    break
                time.sleep(0.5)
            if not public_url:
                print("No se pudo detectar el dominio HTTPS de ngrok.")
                print("Comprueba que configuraste el authtoken de ngrok (CONFIGURAR_NGROK.bat).")
                if logs:
                    print("Ultimos mensajes del tunel:")
                    for line in logs[-8:]:
                        print("  " + line[:250])
                return 1

            original_domain = str(settings.get("public_url", "")).strip()
            if original_domain and original_domain != public_url:
                print("ATENCION: ngrok devolvio un dominio DISTINTO al de la primera ejecucion.")
                print("Se esperaba:", original_domain)
                print("Se obtuvo:", public_url)
                print("Revisa que sea la misma cuenta ngrok y el mismo dominio asignado.")
                print("No se reemplazara silenciosamente el enlace guardado.")
                return 1
            if not original_domain:
                settings["public_url"] = public_url
                save_settings(settings)

            url = public_url + "/?key=" + quote(settings["key"], safe="")
            print("\n ENLACE FIJO PARA COMPARTIR (SERA EL MISMO AL REINICIAR):\n")
            print("   " + url + "\n")
            print(" - Abre el enlace COMPLETO desde cualquier Wi-Fi o datos moviles.")
            print(" - No se solicitan correos ni codigos de ingreso.")
            print(" - El enlace contiene una CLAVE PRIVADA: solo compartelo con gente de confianza.")
            print(" - Cada navegador ve y modifica solamente sus propios documentos.")
            print(" - El computador y esta ventana deben permanecer encendidos.")
            print(" - Descarga los documentos antes de cerrar: se borran al salir.")
            print(" - Para invalidar el enlace antiguo, ejecuta CAMBIAR_CLAVE_ENLACE.bat")
            print(" - Ctrl+C para cerrar el acceso remoto.\n")
            try:
                while proc.poll() is None:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                print("\nCerrando el acceso remoto...")
            if proc.poll() is not None:
                print("El tunel ngrok se ha desconectado.")
                return 1
            return 0
        except (OSError, ValueError) as exc:
            print("Error al iniciar el enlace fijo:", exc)
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
            web_thread.join(timeout=4)
            print("Acceso cerrado. Datos temporales eliminados.")


if __name__ == "__main__":
    raise SystemExit(main())
