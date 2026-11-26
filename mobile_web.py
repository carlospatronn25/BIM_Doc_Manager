"""BIM DOC MANAGER 7.0 — interfaz web para dispositivos móviles.

A cada navegador se le asigna un espacio de trabajo temporal independiente.
Se necesita la clave del enlace para abrir una sesión.
Motor original: core.py; catálogos originales: catalogos.json.
"""
from __future__ import annotations

import csv
import io
import json
import mimetypes
import secrets
import shutil
import socket
import tempfile
import threading
import uuid
import zipfile
from dataclasses import asdict
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import core

HERE = Path(__file__).resolve().parent
MAX_REQUEST = 60 * 1024 * 1024
MAX_FILE = 40 * 1024 * 1024
FIELDS = ("proyecto", "creador", "volumen", "nivel", "tipo", "disciplina", "numero", "descripcion", "estado", "revision")
COMMON_FIELDS = ("proyecto", "creador", "volumen", "nivel")

VOLUMEN_OPCIONES = [
    ("Z01", "Zona 1"), ("Z02", "Zona 2"), ("Z03", "Zona 3"),
    ("E01", "Edificio 1"), ("E02", "Edificio 2"), ("E03", "Edificio 3"),
    ("FC1", "Fase constructiva 1"), ("FC2", "Fase constructiva 2"),
    ("CN", "Construcción nueva"), ("CE", "Construcción existente"),
    ("PE", "Proyecto ejecución"), ("PC", "Proyecto construcción"),
    ("T01", "Tramo 1"), ("T02", "Tramo 2"), ("T03", "Tramo 3"),
    ("XX", "No aplica"), ("XXX", "No aplica"),
    ("YY", "Varios volúmenes"), ("YYY", "Varios volúmenes"),
    ("ZZ", "Todos los volúmenes"), ("ZZZ", "Todos los volúmenes"),
]
NIVEL_OPCIONES = [
    ("P00", "Nivel sobre rasante 0"), ("P01", "Nivel sobre rasante 1"),
    ("P02", "Nivel sobre rasante 2"), ("P03", "Nivel sobre rasante 3"),
    ("S01", "Nivel bajo rasante 1"), ("S02", "Nivel bajo rasante 2"),
    ("S03", "Nivel bajo rasante 3"), ("Z01", "Zona 1"), ("Z02", "Zona 2"),
    ("T01", "Tramo 1"), ("T02", "Tramo 2"), ("T03", "Tramo 3"),
    ("XXX", "No aplica"), ("YYY", "Varios niveles"), ("ZZZ", "Todos los niveles"),
]


def clean_name(filename: str) -> str:
    # No permitir rutas ni nombres reservados en el servidor.
    filename = str(filename or "").replace("\\", "/").split("/")[-1]
    filename = "".join(ch for ch in filename if ch.isprintable() and ch not in '<>:"|?*')
    return filename.strip(". ")[:190]


def parse_multipart(content_type: str, data: bytes) -> list[tuple[str, bytes]]:
    if not content_type.lower().startswith("multipart/form-data;"):
        raise ValueError("Se requiere un formulario multipart/form-data.")
    message = BytesParser(policy=policy.default).parsebytes(
        b"MIME-Version: 1.0\r\nContent-Type: " + content_type.encode("latin-1") + b"\r\n\r\n" + data
    )
    if not message.is_multipart():
        raise ValueError("No se pudieron interpretar los archivos seleccionados.")
    result = []
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data" or part.get_param("name", header="content-disposition") != "files":
            continue
        filename = clean_name(part.get_filename() or "")
        if not filename or filename.startswith(("~$", ".")) or Path(filename).suffix.lower() in (".csv", ".json"):
            continue
        payload = part.get_payload(decode=True) or b""
        if len(payload) > MAX_FILE:
            raise ValueError(f"{filename}: supera el límite de 40 MB por documento.")
        result.append((filename, payload))
    return result


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.input_dir = self.root / "originales"
        self.output_dir = self.root / "renombrados_BIM"
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = core.load_catalog(HERE / "catalogos.json")
        self.entries: dict[str, core.DocumentRecord] = {}
        self.fingerprints: set[tuple[str, int, bytes]] = set()
        self.fingerprints_by_id: dict[str, tuple[str, int, bytes]] = {}
        self.generated_by_id: dict[str, set[str]] = {}
        self.lock = threading.RLock()

    def add_files(self, uploads: list[tuple[str, bytes]]) -> tuple[int, int]:
        import hashlib
        added, repeated = 0, 0
        with self.lock:
            for filename, data in uploads:
                fingerprint = (filename.casefold(), len(data), hashlib.sha256(data).digest())
                if fingerprint in self.fingerprints:
                    repeated += 1
                    continue
                ident = uuid.uuid4().hex
                # Ruta interna sin dependencia del nombre que vino del navegador.
                target = self.input_dir / ident / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                record = core.DocumentRecord(
                    archivo=filename,
                    origen=str(target),
                    descripcion=core.suggest_description(filename),
                )
                self.entries[ident] = record
                self.fingerprints.add(fingerprint)
                self.fingerprints_by_id[ident] = fingerprint
                added += 1
        return added, repeated

    def records(self) -> list[dict]:
        with self.lock:
            return [dict(id=ident, **asdict(record)) for ident, record in self.entries.items()]

    def delete_records(self, ids: list[str]) -> int:
        """Borra registros y sus copias temporales SOLO de esta sesión.

        Nunca elimina los archivos originales del dispositivo del usuario.
        Valida todos los IDs antes de eliminar uno solo.
        """
        if not isinstance(ids, list) or not ids:
            raise ValueError("Selecciona por lo menos un documento para eliminar.")
        if len(ids) > 1000 or any(not isinstance(ident, str) for ident in ids):
            raise ValueError("Selección de documentos inválida.")
        unique_ids = list(dict.fromkeys(ids))
        with self.lock:
            if any(ident not in self.entries for ident in unique_ids):
                raise ValueError("Uno o más documentos no pertenecen a tu sesión.")
            for ident in unique_ids:
                # La ruta es creada por la aplicación, no se construye desde
                # un nombre de archivo suministrado por el navegador.
                folder = self.input_dir / ident
                if folder.exists():
                    shutil.rmtree(folder)
                for name in self.generated_by_id.pop(ident, set()):
                    # Los nombres de salida son producidos por core.py.
                    output = self.output_dir / name
                    if output.is_file():
                        output.unlink()
                fingerprint = self.fingerprints_by_id.pop(ident, None)
                if fingerprint is not None:
                    self.fingerprints.discard(fingerprint)
                del self.entries[ident]
            return len(unique_ids)

    def clear_documents(self) -> int:
        """Vacía todos los documentos cargados de esta sesión, no otras."""
        with self.lock:
            ids = list(self.entries)
            if ids:
                self.delete_records(ids)
            # También retirar cualquier salida temporal sobrante.
            if self.output_dir.exists():
                shutil.rmtree(self.output_dir)
            self.generated_by_id.clear()
            return len(ids)

    def update(self, ident: str, fields: dict) -> None:
        if not isinstance(fields, dict):
            raise ValueError("Los campos deben enviarse como objeto.")
        values = {key: str(value or "").strip() for key, value in fields.items() if key in FIELDS}
        # Se admiten borradores incompletos, pero no valores presentes inválidos.
        errors = core.validar_campos_nomenclatura({k: v for k, v in values.items() if v}, self.catalog, parcial=True)
        if errors:
            raise ValueError("\n".join(errors))
        with self.lock:
            if ident not in self.entries:
                raise KeyError("Documento no encontrado.")
            record = self.entries[ident]
            for key, value in values.items():
                setattr(record, key, value)
            self._reset(record)

    @staticmethod
    def _reset(record: core.DocumentRecord) -> None:
        record.resultado = "SIN VALIDAR"
        record.nombre_propuesto = ""
        record.detalle = "Campos actualizados; pulsa Validar nomenclatura."

    def apply_common(self, ids: list[str], fields: dict) -> int:
        values = {k: str(v or "").strip() for k, v in fields.items() if k in COMMON_FIELDS and str(v or "").strip()}
        if not values:
            raise ValueError("Completa al menos un dato común.")
        errors = core.validar_campos_nomenclatura(values, self.catalog, parcial=True)
        if errors:
            raise ValueError("\n".join(errors))
        with self.lock:
            count = 0
            for ident in ids:
                if ident not in self.entries:
                    continue
                for key, value in values.items():
                    setattr(self.entries[ident], key, value)
                self._reset(self.entries[ident])
                count += 1
            return count

    def validate(self) -> dict:
        with self.lock:
            core.validate_records(list(self.entries.values()), self.catalog, self.output_dir)
            stats = {status: sum(r.resultado == status for r in self.entries.values()) for status in
                     ("LISTO PARA GENERAR", "PENDIENTE", "BLOQUEADO", "GENERADO")}
            return stats

    def generate(self) -> dict:
        with self.lock:
            # Siempre revalidar para evitar usar nombres desactualizados.
            self.validate()
            ready = sum(r.resultado == "LISTO PARA GENERAR" for r in self.entries.values())
            if not ready:
                raise ValueError("No hay documentos listos; completa los datos y pulsa Validar.")
            count, errors = core.copy_ready(self.entries.values(), self.output_dir)
            for ident, record in self.entries.items():
                if record.resultado == "GENERADO" and record.nombre_propuesto:
                    self.generated_by_id.setdefault(ident, set()).add(record.nombre_propuesto)
            return {"copiados": count, "errores": errors}

    def report_csv(self, template: bool = False) -> bytes:
        with self.lock:
            buffer = io.StringIO(newline="")
            columns = core.CSV_FIELDS if not template else list(core.CSV_FIELDS[:11])
            writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for record in self.entries.values():
                writer.writerow(record.to_dict())
            return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")

    def import_csv(self, data: bytes) -> tuple[int, list[str]]:
        with self.lock:
            path = self.root / "importar.csv"
            path.write_bytes(data)
            try:
                return core.import_csv(list(self.entries.values()), path)
            finally:
                path.unlink(missing_ok=True)

    def output_files(self) -> list[str]:
        """Archivos generados en ESTE espacio de trabajo, nunca de otra sesión."""
        with self.lock:
            files = sorted(
                (p.name for p in self.output_dir.iterdir() if p.is_file()),
                key=str.casefold,
            ) if self.output_dir.exists() else []
            if not files:
                raise ValueError("Todavía no hay archivos generados para guardar.")
            return files

    def output_file(self, filename: str) -> bytes:
        """Descarga un único resultado sin permitir rutas ni archivos externos."""
        if not filename or filename in (".", "..") or Path(filename).name != filename or "\\" in filename:
            raise ValueError("Nombre de archivo inválido.")
        with self.lock:
            if filename not in self.output_files():
                raise ValueError("El documento solicitado no existe en tu espacio de trabajo.")
            return (self.output_dir / filename).read_bytes()

    def result_zip(self) -> bytes:
        with self.lock:
            files = self.output_files()
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
                for filename in files:
                    zip_file.write(self.output_dir / filename, arcname=f"renombrados_BIM/{filename}")
                zip_file.writestr("bitacora_BIM.csv", self.report_csv())
            return output.getvalue()


class SessionStore:
    """Espacios de trabajo independientes, creados con tokens impredecibles.

    Los tokens se usan solo como cabeceras HTTP; no aparecen en las URL ni
    determinan los nombres de las carpetas en el disco.
    """
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._sessions: dict[str, Workspace] = {}

    def create(self) -> str:
        with self.lock:
            token = secrets.token_urlsafe(32)
            while token in self._sessions:
                token = secrets.token_urlsafe(32)
            folder = self.root / uuid.uuid4().hex
            self._sessions[token] = Workspace(folder)
            return token

    def get(self, token: str) -> Workspace | None:
        if not token or len(token) > 256:
            return None
        with self.lock:
            return self._sessions.get(token)


def server_factory(sessions: SessionStore, key: str):
    """API con clave de enlace y sesión independiente por navegador."""
    class MobileHandler(BaseHTTPRequestHandler):
        server_version = "BIMDocManagerMobile/7.0"

        def log_message(self, format: str, *args) -> None:
            # Solo registros básicos para facilitar depuración.
            if self.path.startswith("/api/"):
                super().log_message(format, *args)

        def reply(self, status: int, body: bytes, content_type: str = "application/json; charset=utf-8", filename: str | None = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)

        def reply_json(self, value, status=200):
            self.reply(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

        def authorize(self) -> bool:
            if not secrets.compare_digest(self.headers.get("X-BIM-Key", ""), key):
                self.reply_json({"error": "Acceso no autorizado. Abre el enlace completo mostrado en el computador."}, 403)
                return False
            return True

        def session_workspace(self) -> Workspace | None:
            token = self.headers.get("X-BIM-Session", "")
            workspace = sessions.get(token)
            if workspace is None:
                self.reply_json({"error": "La sesión de este navegador ya no está disponible. Recarga la página para crear una nueva."}, 403)
            return workspace

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html", "/app.css", "/app.js"):
                file = {"/": "index.html", "/index.html": "index.html", "/app.css": "app.css", "/app.js": "app.js"}[path]
                mime = "text/html; charset=utf-8" if file.endswith(".html") else ("text/css; charset=utf-8" if file.endswith(".css") else "text/javascript; charset=utf-8")
                self.reply(200, (HERE / "web_mobile" / file).read_bytes(), mime)
                return
            if not path.startswith("/api/"):
                self.reply_json({"error": "Ruta no encontrada."}, 404)
                return
            if not self.authorize():
                return
            workspace = self.session_workspace()
            if workspace is None:
                return
            try:
                if path == "/api/status":
                    with workspace.lock:
                        self.reply_json({"records": workspace.records(), "catalog": workspace.catalog,
                                         "volumen": VOLUMEN_OPCIONES, "nivel": NIVEL_OPCIONES})
                elif path == "/api/download":
                    self.reply(200, workspace.result_zip(), "application/zip", "BIM_Doc_Manager_renombrados.zip")
                elif path == "/api/outputs":
                    self.reply_json({"files": workspace.output_files()})
                elif path == "/api/output-file":
                    names = parse_qs(urlparse(self.path).query).get("name", [])
                    if len(names) != 1:
                        raise ValueError("Indica exactamente un documento para descargar.")
                    filename = names[0]
                    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                    self.reply(200, workspace.output_file(filename), mime)
                elif path == "/api/report":
                    self.reply(200, workspace.report_csv(), "text/csv; charset=utf-8", "bitacora_BIM.csv")
                elif path == "/api/template":
                    self.reply(200, workspace.report_csv(template=True), "text/csv; charset=utf-8", "plantilla_metadatos_BIM.csv")
                else:
                    self.reply_json({"error": "Ruta no encontrada."}, 404)
            except (ValueError, OSError) as exc:
                self.reply_json({"error": str(exc)}, 400)

        def do_POST(self):
            path = urlparse(self.path).path
            if not self.authorize():
                return
            # Solo la clave del enlace permite crear una sesión privada.
            # Ninguna operación documental se permite sin token de sesión.
            if path == "/api/session":
                self.reply_json({"session": sessions.create()})
                return
            workspace = self.session_workspace()
            if workspace is None:
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.reply_json({"error": "Longitud de solicitud incorrecta."}, 400)
                return
            if length < 0 or length > MAX_REQUEST:
                self.reply_json({"error": "La carga máxima por solicitud es de 60 MB."}, 413)
                return
            try:
                body = self.rfile.read(length)
                if path == "/api/upload":
                    parts = parse_multipart(self.headers.get("Content-Type", ""), body)
                    if not parts:
                        raise ValueError("No se recibieron archivos. Los CSV y JSON no se agregan como documentos.")
                    added, repeated = workspace.add_files(parts)
                    self.reply_json({"agregados": added, "repetidos": repeated, "records": workspace.records()})
                    return
                data = json.loads(body.decode("utf-8")) if body else {}
                if path == "/api/update":
                    workspace.update(str(data.get("id", "")), data.get("fields", {}))
                    self.reply_json({"records": workspace.records()})
                elif path == "/api/common":
                    count = workspace.apply_common(data.get("ids", []), data.get("fields", {}))
                    self.reply_json({"modificados": count, "records": workspace.records()})
                elif path == "/api/delete":
                    count = workspace.delete_records(data.get("ids", []))
                    self.reply_json({"eliminados": count, "records": workspace.records()})
                elif path == "/api/clear":
                    count = workspace.clear_documents()
                    self.reply_json({"eliminados": count, "records": workspace.records()})
                elif path == "/api/validate":
                    self.reply_json({"stats": workspace.validate(), "records": workspace.records()})
                elif path == "/api/generate":
                    info = workspace.generate()
                    self.reply_json({**info, "records": workspace.records()})
                elif path == "/api/import_text":
                    text = data.get("csv", "")
                    if not isinstance(text, str) or len(text) > 4_000_000:
                        raise ValueError("CSV vacío o demasiado grande.")
                    count, messages = workspace.import_csv(text.encode("utf-8-sig"))
                    self.reply_json({"importados": count, "observaciones": messages, "records": workspace.records()})
                else:
                    self.reply_json({"error": "Ruta no encontrada."}, 404)
            except (ValueError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
                self.reply_json({"error": str(exc)}, 400)
            except OSError as exc:
                self.reply_json({"error": f"Error del sistema de archivos: {exc}"}, 500)

    return MobileHandler


def local_ip() -> str:
    # Determina la interfaz local sin enviar tráfico a Internet.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Servidor web de BIM DOC MANAGER para el móvil")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    key = secrets.token_urlsafe(18)
    with tempfile.TemporaryDirectory(prefix="bim_doc_mobile_") as temp_dir:
        sessions = SessionStore(Path(temp_dir))
        server = ThreadingHTTPServer(("0.0.0.0", args.port), server_factory(sessions, key))
        url = f"http://{local_ip()}:{args.port}/?key={key}"
        print("\n" + "=" * 72)
        print("  BIM DOC MANAGER 7.0 — Versión para teléfono (navegador)")
        print("=" * 72)
        print("  1. Conecta el teléfono y el computador a la MISMA red Wi-Fi.")
        print("  2. Mantén esta ventana abierta mientras usas el programa.")
        print("  3. Abre el siguiente enlace COMPLETO en el navegador del teléfono:")
        print("\n     " + url + "\n")
        print("  Si Windows Firewall pregunta, permite acceso solo a redes privadas.")
        print("  No redirijas este puerto a Internet; es una versión para red local.")
        print("  Cada navegador tiene sus propios documentos temporales.")
        print("  Descarga el ZIP antes de cerrar esta ventana.")
        print("  Ctrl+C para detener el servidor.\n")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
