"""Motor de nomenclatura BIM basado en el manual buildingSMART Spain v1.1 (2023).

El manual está alineado con la serie ISO 19650; no se presenta como una norma ISO
independiente ni convierte los datos que no conoce en valores supuestos.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class DocumentRecord:
    archivo: str
    origen: str
    proyecto: str = ""
    creador: str = ""
    volumen: str = ""
    nivel: str = ""
    tipo: str = ""
    disciplina: str = ""
    numero: str = ""
    descripcion: str = ""
    estado: str = ""
    revision: str = ""
    nombre_propuesto: str = ""
    resultado: str = "SIN VALIDAR"
    detalle: str = "Completa los campos obligatorios y valida la nomenclatura."

    def to_dict(self) -> dict:
        return asdict(self)


CSV_FIELDS = [
    "archivo", "proyecto", "creador", "volumen", "nivel", "tipo", "disciplina",
    "numero", "descripcion", "estado", "revision", "nombre_propuesto", "resultado",
    "detalle", "origen",
]


def load_catalog(path: Path | None = None) -> dict:
    """Carga el catálogo distribuido con la aplicación."""
    if path is None:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        path = base / "catalogos.json"
    with Path(path).open("r", encoding="utf-8") as f:
        catalog = json.load(f)
    for key in ("tipos_documento", "disciplinas", "estados"):
        if key not in catalog:
            raise ValueError(f"El catálogo no contiene la sección '{key}'.")
    return catalog


def _ascii_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def suggest_description(filename: str) -> str:
    """Sugiere UpperCamelCase desde el nombre; no deduce los demás metadatos."""
    stem = Path(filename).stem
    words = re.findall(r"[A-Za-z0-9]+", _ascii_text(stem))
    return "".join(w.lower()[:1].upper() + w.lower()[1:] for w in words)


def normalize_code(value: str) -> str:
    return _ascii_text(value).strip().upper()


def normalize_description(value: str) -> str:
    """Convierte un texto informal a UpperCamelCase, sin inventar contenido."""
    words = re.findall(r"[A-Za-z0-9]+", _ascii_text(value))
    return "".join(w.lower()[:1].upper() + w.lower()[1:] for w in words)


def scan_sources(sources: Iterable[Path], output_folder: Path | None = None) -> list[DocumentRecord]:
    """Recibe archivos individuales y/o carpetas, incluso de distintas ubicaciones.

    Explora las carpetas recursivamente, ignora la carpeta de salida y no
    repite un archivo si fue seleccionado directamente y mediante una carpeta.
    """
    output_resolved = Path(output_folder).expanduser().resolve() if output_folder else None
    found: dict[str, tuple[Path, str]] = {}
    for raw_source in sources:
        source = Path(raw_source).expanduser().resolve()
        if not source.exists():
            raise ValueError(f"La ruta seleccionada no existe: {source}")
        if source.is_dir():
            if output_resolved and (output_resolved == source or output_resolved in source.parents):
                raise ValueError(
                    "La carpeta de salida no puede ser igual a la carpeta de entrada "
                    "ni contenerla. Elige una carpeta de salida independiente."
                )
            candidates = ((p, str(p.relative_to(source))) for p in sorted(
                source.rglob("*"), key=lambda p: str(p).casefold()
            ) if p.is_file())
        elif source.is_file():
            candidates = [(source, source.name)]
        else:
            continue
        for path, label in candidates:
            if path.name.startswith(("~$", ".")) or path.suffix.lower() in {".csv", ".json"}:
                continue
            resolved = path.resolve()
            if output_resolved:
                try:
                    resolved.relative_to(output_resolved)
                    continue
                except ValueError:
                    pass
            key = str(resolved).casefold()
            found.setdefault(key, (resolved, label))

    # Dos archivos en carpetas distintas pueden compartir el nombre informal.
    # En ese caso, mostrar la ruta completa evita ambigüedades al importar un CSV.
    counts: dict[str, int] = {}
    for path, label in found.values():
        counts[label.casefold()] = counts.get(label.casefold(), 0) + 1
    records = []
    for path, label in found.values():
        if counts[label.casefold()] > 1:
            label = str(path)
        records.append(DocumentRecord(
            archivo=label,
            origen=str(path),
            descripcion=suggest_description(path.name),
        ))
    return records


def scan_documents(folder: Path, output_folder: Path | None = None) -> list[DocumentRecord]:
    """Compatibilidad con el lector anterior, que aceptaba solo una carpeta."""
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise ValueError("Selecciona una carpeta de documentos existente.")
    return scan_sources([folder], output_folder)


def validar_campos_nomenclatura(datos: dict, catalog: dict, parcial: bool = False) -> list[str]:
    """Valida longitudes y catálogos; se usa en formulario y en el motor.

    `parcial=True` solo revisa los campos provistos (edición de datos comunes).
    """
    errores = []
    reglas = {
        "proyecto": ("Proyecto", 2, 12, "alfanumerico"),
        "creador": ("Creador", 3, 6, "alfanumerico"),
        "volumen": ("Volumen/Sistema", 2, 3, "alfanumerico"),
        "nivel": ("Nivel/Localización", 3, 3, "alfanumerico"),
        "tipo": ("Tipo de documento", 3, 3, "alfanumerico"),
        "disciplina": ("Disciplina", 3, 3, "letras"),
    }
    obligatorios = {*reglas, "numero"}
    campos = [*reglas, "numero", "descripcion", "estado", "revision"]

    for campo in campos:
        if parcial and campo not in datos:
            continue
        valor = str(datos.get(campo, "") or "").strip()
        if not valor:
            if campo in obligatorios:
                if campo in reglas:
                    nombre, minimo, maximo, _ = reglas[campo]
                    rango = f"exactamente {minimo}" if minimo == maximo else f"entre {minimo} y {maximo}"
                    errores.append(f"{nombre}: es obligatorio; requiere {rango} caracteres.")
                else:
                    errores.append("Número: es obligatorio (001–999).")
            continue

        if campo in reglas:
            nombre, minimo, maximo, patron = reglas[campo]
            n = len(valor)
            if not minimo <= n <= maximo:
                rango = f"exactamente {minimo}" if minimo == maximo else f"entre {minimo} y {maximo}"
                errores.append(f"{nombre}: escribiste {n} caracteres; se requieren {rango}.")
            regex = r"[A-Za-z]+" if patron == "letras" else r"[A-Za-z0-9]+"
            if re.fullmatch(regex, valor) is None:
                reglas_txt = "solo letras sin tildes" if patron == "letras" else "solo letras y números sin espacios ni símbolos"
                errores.append(f"{nombre}: se permiten {reglas_txt}.")
            if campo == "tipo" and valor.upper() not in catalog["tipos_documento"]:
                errores.append(f"Tipo de documento: '{valor}' no está en el Anexo I del catálogo.")
            if campo == "disciplina" and valor.upper() not in catalog["disciplinas"]:
                errores.append(f"Disciplina: '{valor}' no está en el Anexo II del catálogo.")
        elif campo == "numero":
            if re.fullmatch(r"[0-9]{1,3}", valor) is None or not (1 <= int(valor) <= 999):
                errores.append("Número: introduce un entero de 001 a 999 (7 se convierte en 007).")
        elif campo == "estado":
            if len(valor) != 2:
                errores.append(f"Estado: escribiste {len(valor)} caracteres; se requieren exactamente 2.")
            if valor.upper() not in catalog["estados"]:
                errores.append(f"Estado: '{valor}' no figura en el catálogo.")
        elif campo == "revision":
            if re.fullmatch(r"[0-9]{4}", valor) is None:
                errores.append(f"Revisión: escribiste {len(valor)} caracteres; se requieren exactamente 4 dígitos (ej.: 0100).")
        elif campo == "descripcion" and not normalize_description(valor):
            errores.append("Descripción: debe contener letras o números utilizables.")

    return errores


def _validate_record(record: DocumentRecord, catalog: dict, output_folder: Path) -> tuple[str, str, list[str]]:
    """Devuelve (resultado, detalle, advertencias). No realiza inferencias de metadatos."""
    missing = []
    required = {
        "proyecto": record.proyecto,
        "creador": record.creador,
        "volumen": record.volumen,
        "nivel": record.nivel,
        "tipo": record.tipo,
        "disciplina": record.disciplina,
        "numero": record.numero,
    }
    for key, value in required.items():
        if not str(value or "").strip():
            missing.append(key)
    if missing:
        labels = {
            "proyecto": "Proyecto", "creador": "Creador", "volumen": "Volumen/Sistema",
            "nivel": "Nivel/Localización", "tipo": "Tipo de documento",
            "disciplina": "Disciplina", "numero": "Número",
        }
        return "PENDIENTE", "Faltan campos obligatorios: " + ", ".join(labels[x] for x in missing), []

    errores = validar_campos_nomenclatura(record.to_dict(), catalog)
    if errores:
        return "BLOQUEADO", " | ".join(errores), []

    proyecto = normalize_code(record.proyecto)
    creador = normalize_code(record.creador)
    volumen = normalize_code(record.volumen)
    nivel = normalize_code(record.nivel)
    tipo = normalize_code(record.tipo)
    disciplina = normalize_code(record.disciplina)
    numero_raw = str(record.numero).strip()
    estado = normalize_code(record.estado)
    revision = str(record.revision or "").strip()

    checks = [
        (2 <= len(proyecto) <= 12 and re.fullmatch(r"[A-Z0-9]+", proyecto) is not None, "Proyecto debe tener de 2 a 12 caracteres alfanuméricos (A–Z, 0–9)."),
        (3 <= len(creador) <= 6 and re.fullmatch(r"[A-Z0-9]+", creador) is not None, "Creador debe tener de 3 a 6 caracteres alfanuméricos (A–Z, 0–9)."),
        (2 <= len(volumen) <= 3 and re.fullmatch(r"[A-Z0-9]+", volumen) is not None, "Volumen/Sistema debe tener 2 o 3 caracteres alfanuméricos (A–Z, 0–9)."),
        (len(nivel) == 3 and re.fullmatch(r"[A-Z0-9]{3}", nivel) is not None, "Nivel/Localización debe tener exactamente 3 caracteres alfanuméricos (A–Z, 0–9)."),
        (tipo in catalog["tipos_documento"], f"Tipo de documento '{tipo}' no figura en el Anexo I del catálogo."),
        (len(disciplina) == 3 and re.fullmatch(r"[A-Z]{3}", disciplina) is not None and disciplina in catalog["disciplinas"], f"Disciplina '{disciplina}' no figura como código de 3 letras en el Anexo II."),
        (re.fullmatch(r"[0-9]{1,3}", numero_raw) is not None and 1 <= int(numero_raw) <= 999, "Número debe ser un entero entre 001 y 999; se completa a tres dígitos."),
    ]
    for ok, message in checks:
        if not ok:
            return "BLOQUEADO", message, []

    if estado and estado not in catalog["estados"]:
        return "BLOQUEADO", f"Estado '{estado}' no está entre los valores contemplados en el catálogo del manual.", []
    if estado and len(estado) != 2:
        return "BLOQUEADO", "Estado debe tener 2 caracteres.", []
    if revision and re.fullmatch(r"[0-9]{4}", revision) is None:
        return "BLOQUEADO", "Revisión debe tener 4 dígitos (dos de versión mayor y dos de versión menor).", []

    description = normalize_description(record.descripcion)
    parts = [proyecto, creador, volumen, nivel, tipo, disciplina, f"{int(numero_raw):03d}"]
    if description:
        parts.append(description)
    if estado:
        parts.append(estado)
    if revision:
        parts.append(revision)

    ext = Path(record.archivo).suffix
    proposed = "-".join(parts) + ext
    warnings: list[str] = []
    if len(proposed) > 60:
        warnings.append(f"El nombre tiene {len(proposed)} caracteres; el manual recomienda no superar 60.")

    output_folder = Path(output_folder)
    destination = output_folder / proposed
    existing_names = {p.name.casefold() for p in output_folder.iterdir() if p.is_file()} if output_folder.exists() else set()
    if destination.exists() or proposed.casefold() in existing_names:
        return "BLOQUEADO", "Ya existe un archivo con ese nombre en la carpeta de salida.", warnings

    return "LISTO PARA GENERAR", "Campos válidos; revisa el nombre propuesto antes de generar la copia.", warnings


def validate_records(records: Iterable[DocumentRecord], catalog: dict, output_folder: Path) -> list[DocumentRecord]:
    """Valida todos los registros y bloquea nombres duplicados dentro del lote."""
    records = list(records)
    output_folder = Path(output_folder)
    candidates: dict[str, list[DocumentRecord]] = {}

    for record in records:
        record.nombre_propuesto = ""
        result, detail, warnings = _validate_record(record, catalog, output_folder)
        record.resultado = result
        record.detalle = detail
        if result == "LISTO PARA GENERAR":
            # Reconstruir el nombre únicamente después de pasar reglas de formato.
            p = normalize_code(record.proyecto)
            c = normalize_code(record.creador)
            v = normalize_code(record.volumen)
            n = normalize_code(record.nivel)
            t = normalize_code(record.tipo)
            d = normalize_code(record.disciplina)
            number = f"{int(str(record.numero).strip()):03d}"
            record.numero = number
            parts = [p, c, v, n, t, d, number]
            description = normalize_description(record.descripcion)
            if description:
                parts.append(description)
            if record.estado:
                parts.append(normalize_code(record.estado))
            if record.revision:
                parts.append(str(record.revision).strip())
            record.nombre_propuesto = "-".join(parts) + Path(record.archivo).suffix
            if warnings:
                record.detalle += " Advertencia: " + " ".join(warnings)
            candidates.setdefault(record.nombre_propuesto.casefold(), []).append(record)

    for name, same_name in candidates.items():
        if len(same_name) > 1:
            for record in same_name:
                record.resultado = "BLOQUEADO"
                record.detalle = "Dos o más documentos del lote producirían el mismo nombre; modifica los campos diferenciadores."
    return records


def copy_ready(records: Iterable[DocumentRecord], output_folder: Path) -> tuple[int, list[str]]:
    """Crea copias de registros listos. Nunca modifica ni elimina los originales."""
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    copied = 0
    errors: list[str] = []
    for record in records:
        if record.resultado != "LISTO PARA GENERAR":
            continue
        source = Path(record.origen)
        destination = output_folder / record.nombre_propuesto
        if not source.is_file():
            record.resultado = "ERROR DE COPIA"
            record.detalle = "No se encuentra el documento original."
            errors.append(f"{record.archivo}: no se encuentra el archivo original.")
            continue
        existing_names = {p.name.casefold() for p in output_folder.iterdir() if p.is_file()}
        if destination.exists() or record.nombre_propuesto.casefold() in existing_names:
            record.resultado = "BLOQUEADO"
            record.detalle = "El destino ya existe; no se sobrescribió."
            errors.append(f"{record.nombre_propuesto}: el destino ya existe.")
            continue
        try:
            shutil.copy2(source, destination)
            copied += 1
            record.resultado = "GENERADO"
            record.detalle = f"Copia creada correctamente: {destination.name}"
        except OSError as exc:
            record.resultado = "ERROR DE COPIA"
            record.detalle = f"No se pudo copiar: {exc}"
            errors.append(f"{record.archivo}: {exc}")
    return copied, errors


def export_csv(records: Iterable[DocumentRecord], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())


def import_csv(records: list[DocumentRecord], path: Path) -> tuple[int, list[str]]:
    """Importa metadatos de una plantilla CSV y los relaciona por nombre de archivo."""
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "archivo" not in [x.strip().lower() for x in reader.fieldnames if x]:
            raise ValueError("El CSV debe incluir una columna 'archivo'.")
        rows = list(reader)

    by_name: dict[str, list[dict]] = {}
    for row in rows:
        normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        by_name.setdefault(normalized.get("archivo", "").casefold(), []).append(normalized)

    lookup = {r.archivo.casefold(): r for r in records}
    loaded = 0
    messages: list[str] = []
    field_map = {
        "proyecto": "proyecto", "creador": "creador", "volumen": "volumen",
        "nivel": "nivel", "tipo": "tipo", "disciplina": "disciplina",
        "numero": "numero", "descripcion": "descripcion", "estado": "estado",
        "revision": "revision",
    }
    for name, entries in by_name.items():
        if name not in lookup:
            messages.append(f"CSV: no se encontró en la carpeta '{name}'.")
            continue
        if len(entries) > 1:
            messages.append(f"CSV: el archivo '{name}' aparece más de una vez; no se importó.")
            continue
        record = lookup[name]
        for csv_key, attr in field_map.items():
            if csv_key in entries[0]:
                setattr(record, attr, entries[0][csv_key])
        record.resultado = "SIN VALIDAR"
        record.nombre_propuesto = ""
        record.detalle = "Metadatos importados; vuelve a validar."
        loaded += 1
    return loaded, messages


def export_template(records: Iterable[DocumentRecord], path: Path) -> None:
    """Exporta un CSV editable con columnas documentales y sin nombres inventados."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["archivo", "proyecto", "creador", "volumen", "nivel", "tipo", "disciplina", "numero", "descripcion", "estado", "revision"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            data = r.to_dict()
            writer.writerow({key: data.get(key, "") for key in fields})
