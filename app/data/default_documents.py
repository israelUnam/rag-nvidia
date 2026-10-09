# Copyright 2024
# Directory: rag-openrouter/app/data/default_documents.py

"""
Default documents for seeding the RAG knowledge base.
Loaded from the files in app/data/documents/ (.md and .json).

Markdown files may start with a front matter block:

    ---
    chunk_id: policy_returns_v1
    source: https://help.example.com/return-policy
    ---

If omitted, chunk_id defaults to the file name (without .md) and source to the file name.

JSON project knowledge bases (with a "baseConocimientos" key) are split into one
document per subsection / work package, each starting with a title line that
names the project, so every chunk can be matched to its project.

Projects uploaded as pre-chunked JSONL are stored as
{"baseConocimientos": {"proyecto": {...}}, "registros": [{id, titulo, contenido, metadatos}, ...]}
and each record becomes one document.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

DOCUMENTS_DIR = Path(__file__).parent / "documents"


def _label(key: str) -> str:
    """Turn a camelCase JSON key into a readable label (fechaInicio -> Fecha inicio)."""
    words = re.sub(r'(?<=[a-záéíóúñ])(?=[A-Z])', ' ', key)
    return words[:1].upper() + words[1:].lower() if words != key else key[:1].upper() + key[1:]


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "Sí" if value else "No"
    return str(value)


def _render(value: Any, indent: int = 0) -> List[str]:
    """Render JSON values as indented 'Label: value' lines."""
    pad = "  " * indent
    lines: List[str] = []

    if isinstance(value, dict):
        for key, item in value.items():
            if _is_empty(item):
                continue
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}{_label(key)}:")
                lines.extend(_render(item, indent + 1))
            else:
                lines.append(f"{pad}{_label(key)}: {_format_scalar(item)}")
    elif isinstance(value, list):
        items = [item for item in value if not _is_empty(item)]
        if all(not isinstance(item, (dict, list)) for item in items):
            lines.append(pad + ", ".join(_format_scalar(item) for item in items))
        else:
            for i, item in enumerate(items, start=1):
                if isinstance(item, (dict, list)):
                    lines.append(f"{pad}{i}.")
                    lines.extend(_render(item, indent + 1))
                else:
                    lines.append(f"{pad}{i}. {_format_scalar(item)}")
    elif not _is_empty(value):
        lines.append(pad + _format_scalar(value))

    return lines


def _project_units(data: Dict[str, Any]) -> Iterator[Tuple[str, str, Any]]:
    """Yield (unit_id, title, content) for each subsection / work package."""
    for key, section in data.items():
        if key == "baseConocimientos" or not isinstance(section, dict):
            continue
        section_title = section.get("seccion") or _label(key)

        if isinstance(section.get("secciones"), list):
            for i, sub in enumerate(section["secciones"], start=1):
                content = {k: v for k, v in sub.items() if k != "titulo"}
                yield f"{key}-{i}", f"{section_title} | {sub.get('titulo', i)}", content
            continue

        for sub_key, sub_value in section.items():
            if sub_key in ("seccion", "proyecto", "titulo") or _is_empty(sub_value):
                continue
            if isinstance(sub_value, list) and all(isinstance(item, dict) for item in sub_value):
                for i, item in enumerate(sub_value, start=1):
                    code = item.get("codigo") or str(i)
                    name = f"{item.get('codigo', '')} {item.get('nombre', '')}".strip()
                    yield f"{key}-{sub_key}-{code}", f"{section_title} | {_label(sub_key)} {name}".strip(), item
            else:
                yield f"{key}-{sub_key}", f"{section_title} | {_label(sub_key)}", sub_value


def _parse_json(path: Path) -> List[Dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return parse_json_data(data, path.stem, path.name)


def parse_json_data(data: Dict[str, Any], stem: str, file_name: str) -> List[Dict[str, str]]:
    """Split a JSON knowledge base into documents; chunk_ids are prefixed with '<stem>__'."""
    project = (data.get("baseConocimientos") or {}).get("proyecto") or {}
    if not project:
        return [{
            'chunk_id': stem,
            'source': file_name,
            'text': "\n".join(_render(data))
        }]

    project_name = project.get("nombre", stem)
    if isinstance(data.get("registros"), list):
        return _record_documents(data["registros"], project_name, stem, file_name)

    documents = []
    for unit_id, title, content in _project_units(data):
        body = "\n".join(_render(content))
        if not body.strip():
            continue
        documents.append({
            'chunk_id': f"{stem}__{unit_id}",
            'source': f"{file_name}#{unit_id}",
            'text': f"# Proyecto: {project_name} | {title}\n\n{body}"
        })
    return documents


def _record_documents(records: List[Any], project_name: str, stem: str, file_name: str) -> List[Dict[str, str]]:
    """
    Documents from pre-chunked records (one JSONL line each: id, titulo, contenido, metadatos).
    The content is used as is; a project title line is added when it does not start with one.
    """
    documents = []
    for i, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        body = str(record.get("contenido") or "").strip()
        if not body:
            continue
        record_id = str(record.get("id") or f"registro-{i}").strip()
        if not body.startswith("#"):
            title = record.get("titulo") or record_id
            body = f"# Proyecto: {project_name} | {title}\n\n{body}"
        documents.append({
            'chunk_id': f"{stem}__{record_id}",
            'source': f"{file_name}#{record_id}",
            'text': body
        })
    return documents


def _record_fields(records: List[Any]) -> Dict[str, str]:
    """First value of every 'Label: value' line in the records' content, keyed by lowercase label."""
    fields: Dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        for line in str(record.get("contenido") or "").splitlines():
            label, sep, value = line.partition(":")
            label, value = label.strip().lower(), value.strip()
            if sep and value and 0 < len(label) <= 60 and label not in fields:
                fields[label] = value
    return fields


def _record_description(records: List[Any]) -> Optional[str]:
    """Paragraphs after 'Descripción del Proyecto:' in the project charter records."""
    for record in records:
        if not isinstance(record, dict):
            continue
        lines = str(record.get("contenido") or "").splitlines()
        for i, line in enumerate(lines):
            if line.strip().lower().startswith("descripción del proyecto:"):
                paragraphs = []
                for following in lines[i + 1:]:
                    if paragraphs and re.match(r"^\s*[A-ZÁÉÍÓÚÑ][^:.]{0,40}:", following):
                        break
                    if following.strip():
                        paragraphs.append(following.strip())
                return " ".join(paragraphs) or None
    return None


def _number(value: Optional[str]) -> Optional[float]:
    """Parse amounts such as '$800,000.00 MXN' or '800000.00'."""
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _iso_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    val = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
        return val
    if "/" in val:
        parts = val.split("/")
        if len(parts) == 3:
            day, month, year = parts
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return val


def _records_summary(path: Path, data: Dict[str, Any]) -> Dict[str, Any]:
    records = data["registros"]
    project = data["baseConocimientos"]["proyecto"]
    fields = _record_fields(records)
    resumen = next(
        (r.get("metadatos") or {} for r in records
         if isinstance(r, dict) and (r.get("metadatos") or {}).get("tipo") == "resumen_control"),
        {}
    )
    periodo = re.search(r"(\d{1,2}/\d{1,2}/\d{4})\D+(\d{1,2}/\d{1,2}/\d{4})", fields.get("periodo del proyecto", ""))
    paquetes = fields.get("paquetes de trabajo totales") or fields.get("número de paquetes de trabajo")
    completados = fields.get("paquetes de trabajo completados") or fields.get("paquetes completados")

    return {
        'id': project.get("id"),
        'slug': path.stem,
        'nombre': (project.get("nombre") or path.stem).strip(),
        'director': fields.get("director del proyecto"),
        'area': fields.get("área responsable"),
        'prioridad': fields.get("prioridad"),
        'beneficiarios': fields.get("beneficiarios"),
        'descripcion': _record_description(records),
        'objetivo': fields.get("objetivo general"),
        'estado': resumen.get("estado") or fields.get("estado del proyecto"),
        'fechaInicio': _iso_date(periodo.group(1)) if periodo else None,
        'fechaTermino': _iso_date(periodo.group(2)) if periodo else None,
        'presupuestoAsignado': _number(fields.get("presupuesto asignado")),
        'costoRealEjecutado': resumen.get("costoRealEjecutado") or _number(fields.get("costo real ejecutado (ac)")),
        'paquetesTrabajo': int(_number(paquetes)) if _number(paquetes) is not None else None,
        'paquetesCompletados': int(_number(completados)) if _number(completados) is not None else None,
    }


def _project_summary(path: Path, data: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(data.get("registros"), list):
        return _records_summary(path, data)

    acta = (data.get("actaConstitucion") or {}).get("secciones") or []
    campos = acta[0].get("campos", {}) if acta else {}
    objetivos = next((s.get("campos", {}) for s in acta if s.get("titulo") == "Objetivos"), {})
    resumen = (data.get("controlProyecto") or {}).get("resumen") or {}
    project = data["baseConocimientos"]["proyecto"]

    return {
        'id': project.get("id"),
        'slug': path.stem,
        'nombre': (project.get("nombre") or path.stem).strip(),
        'director': campos.get("Director del Proyecto"),
        'area': campos.get("Área Responsable"),
        'prioridad': campos.get("Prioridad"),
        'beneficiarios': campos.get("Beneficiarios"),
        'descripcion': campos.get("Descripción"),
        'objetivo': objetivos.get("Objetivo general"),
        'estado': resumen.get("estado"),
        'fechaInicio': resumen.get("fechaInicio"),
        'fechaTermino': resumen.get("fechaTermino"),
        'presupuestoAsignado': resumen.get("presupuestoAsignado"),
        'costoRealEjecutado': resumen.get("costoRealEjecutado"),
        'paquetesTrabajo': resumen.get("paquetesTrabajo"),
        'paquetesCompletados': resumen.get("paquetesCompletados"),
    }


def extract_markdown_metadata(content: str, stem: str) -> Dict[str, Any]:
    """Extract project metadata from a Markdown document (front matter, title, inline bold fields)."""
    meta: Dict[str, Any] = {}
    body = content

    # 1. Front matter if present
    if content.startswith("---"):
        lines = content.splitlines()
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                for meta_line in lines[1:i]:
                    key, sep, value = meta_line.partition(":")
                    if sep:
                        meta[key.strip().lower()] = value.strip()
                body = "\n".join(lines[i + 1:])
                break

    # 2. Project Name / Title
    nombre = meta.get("nombre") or meta.get("title") or meta.get("proyecto")
    if not nombre:
        h1 = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if h1:
            raw_title = h1.group(1).strip()
            raw_title = re.sub(r"^(?:documento\s+de\s+proyecto|proyecto)\s*:\s*", "", raw_title, flags=re.IGNORECASE).strip()
            nombre = raw_title
    if not nombre:
        nombre = stem.replace("-", " ").replace("_", " ").title()

    # 3. Flexible field extractor
    def _find_field(pattern: str) -> Optional[str]:
        # Matches:
        # **Label:** Value
        # **Label: Value**
        # Label: Value
        pat = rf"(?:\*\*)?(?:{pattern})(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.+?)(?:\*\*)?$"
        m = re.search(pat, body, re.IGNORECASE | re.MULTILINE)
        if not m or not m.group(1):
            return None
        val = m.group(1).strip()
        return val.strip("*").strip()

    id_val = meta.get("id") or _find_field(r"Clave(?:\s+(?:de|del)\s+Proyecto)?|ID(?:\s+(?:de|del)\s+Proyecto)?")
    director = meta.get("director") or _find_field(r"Director(?:\s+(?:de|del)\s+Proyecto)?")
    area = meta.get("area") or _find_field(r"[AÁ]rea(?:\s+Responsable)?")
    prioridad = meta.get("prioridad") or _find_field(r"Prioridad")
    estado = meta.get("estado") or _find_field(r"Estado(?:\s+(?:de|del)\s+Proyecto)?")
    beneficiarios = meta.get("beneficiarios") or _find_field(r"Beneficiarios")
    presupuesto = meta.get("presupuesto") or _find_field(r"Presupuesto(?:\s+Asignado)?")
    costo_real = meta.get("costo_real") or meta.get("costoreal") or _find_field(r"Costo\s+Real(?:\s+Ejecutado)?")
    fecha_inicio = meta.get("fecha_inicio") or meta.get("fechainicio") or _find_field(r"Fecha\s+Inicio")
    fecha_termino = meta.get("fecha_termino") or meta.get("fechatermino") or _find_field(r"Fecha\s+T[eé]rmino")
    paquetes_trabajo = _find_field(r"Paquetes(?:\s+de\s+trabajo)?(?:\s+totales)?")
    paquetes_completados = _find_field(r"Paquetes(?:\s+de\s+trabajo)?\s+completados")

    # 4. Description (paragraphs under 'Resumen Ejecutivo' or 'Descripción')
    desc = None
    desc_match = re.search(r"##\s*(?:\d+[\.\)]?\s*)?(?:Resumen\s+Ejecutivo|Descripción)[^\n\r]*[\r\n]+(.*?)(?=\n##|\n---|\Z)", body, re.DOTALL | re.IGNORECASE)
    if desc_match:
        paragraphs = [p.strip() for p in desc_match.group(1).split("\n\n") if p.strip() and not p.strip().startswith("```") and not p.strip().startswith("<!--")]
        if paragraphs:
            desc = paragraphs[0]

    # 5. Objective (under 'Objetivo General' or 'Objetivos')
    obj = None
    obj_match = re.search(r"###?\s*(?:\d+(?:\.\d+)?[\.\)]?\s*)?Objetivo\s+General[^\n\r]*[\r\n]+(.*?)(?=\n#|\n---|\Z)", body, re.DOTALL | re.IGNORECASE)
    if obj_match:
        paragraphs = [p.strip() for p in obj_match.group(1).split("\n\n") if p.strip() and not p.strip().startswith("```")]
        if paragraphs:
            obj = paragraphs[0]

    if not beneficiarios:
        ben_match = re.search(r"(?:población|comunidad|beneficiarios)\s+de\s+(?:más\s+de\s+)?([0-9,.]+\s*(?:estudiantes|personas|usuarios|alumnos))", body, re.IGNORECASE)
        if ben_match:
            beneficiarios = ben_match.group(1).strip()

    return {
        "id": id_val or stem,
        "slug": stem,
        "nombre": nombre,
        "director": director,
        "area": area,
        "prioridad": prioridad,
        "estado": estado or "Activo",
        "beneficiarios": beneficiarios,
        "descripcion": desc or meta.get("descripcion"),
        "objetivo": obj or meta.get("objetivo"),
        "presupuestoAsignado": _number(presupuesto),
        "costoRealEjecutado": _number(costo_real),
        "fechaInicio": _iso_date(fecha_inicio),
        "fechaTermino": _iso_date(fecha_termino),
        "paquetesTrabajo": int(_number(paquetes_trabajo)) if _number(paquetes_trabajo) is not None else None,
        "paquetesCompletados": int(_number(paquetes_completados)) if _number(paquetes_completados) is not None else None,
    }


def parse_markdown_data(content: str, stem: str, file_name: str) -> List[Dict[str, str]]:
    """Split a Markdown project document into section-based chunks; chunk_ids prefixed with '<stem>__'."""
    meta = extract_markdown_metadata(content, stem)
    project_name = meta["nombre"]
    
    # Strip YAML front matter if present
    body = content
    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]

    # Clean HTML comments like <!-- PÁGINA 1: ... -->
    clean_body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)

    # Split by level 2 headings: '## ' (fallback to level 1 if no '## ')
    has_h2 = bool(re.search(r"(?m)^##\s+", clean_body))
    split_pattern = r"(?m)^##\s+" if has_h2 else r"(?m)^#\s+"

    raw_sections = re.split(split_pattern, clean_body)
    documents = []

    # If the text before the first section heading has content (title/metadata), include it
    preamble = raw_sections[0].strip() if raw_sections else ""
    if preamble:
        preamble_lines = [l for l in preamble.splitlines() if l.strip() and not l.strip().startswith("#")]
        if preamble_lines:
            documents.append({
                'chunk_id': f"{stem}__info-general",
                'source': f"{file_name}#info-general",
                'text': f"# Proyecto: {project_name} | Información General\n\n{preamble}"
            })

    # Subsequent sections:
    for idx, sec in enumerate(raw_sections[1:], start=1):
        lines = sec.strip().splitlines()
        if not lines:
            continue
        heading_title = lines[0].strip()
        sec_content = "\n".join(lines[1:]).strip()
        if not sec_content:
            continue
        
        safe_heading = re.sub(r"[^\w]+", "-", heading_title.lower()).strip("-")
        unit_id = f"sec-{idx}" if not safe_heading else f"sec-{idx}-{safe_heading[:40].rstrip('-')}"
        
        documents.append({
            'chunk_id': f"{stem}__{unit_id}",
            'source': f"{file_name}#{unit_id}",
            'text': f"# Proyecto: {project_name} | {heading_title}\n\n{sec_content}"
        })

    # If no sections were produced, produce one document for the whole content
    if not documents and clean_body.strip():
        documents.append({
            'chunk_id': stem,
            'source': file_name,
            'text': f"# Proyecto: {project_name}\n\n{clean_body.strip()}"
        })

    return documents


def load_projects(directory: Path = DOCUMENTS_DIR) -> List[Dict[str, Any]]:
    """Summary of every JSON and Markdown project knowledge base in the directory."""
    projects = []
    # 1. JSON projects
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data.get("baseConocimientos") or {}).get("proyecto"):
            projects.append(_project_summary(path, data))
    # 2. Markdown projects (.md)
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            projects.append(extract_markdown_metadata(text, path.stem))
    return projects


def document_titles(documents: List[Dict[str, str]]) -> Dict[str, str]:
    """Map each document chunk_id to its readable title (first Markdown heading)."""
    titles = {}
    for doc in documents:
        first_line = doc['text'].strip().splitlines()[0] if doc['text'].strip() else ""
        if first_line.startswith("#"):
            titles[doc['chunk_id']] = first_line.lstrip("# ").removeprefix("Proyecto: ")
    return titles


def load_documents(directory: Path = DOCUMENTS_DIR) -> List[Dict[str, str]]:
    """Load every .md and .json file in the directory, sorted by file name."""
    documents: List[Dict[str, str]] = []
    for path in sorted(directory.iterdir()):
        if path.suffix == ".md" and path.read_text(encoding="utf-8").strip():
            documents.extend(parse_markdown_data(path.read_text(encoding="utf-8"), path.stem, path.name))
        elif path.suffix == ".json":
            documents.extend(_parse_json(path))
    return documents


def reload_documents() -> None:
    """Re-read the documents directory in place, so modules that imported DEFAULT_DOCUMENTS see the changes."""
    DEFAULT_DOCUMENTS[:] = load_documents()


# Default documents for seeding
DEFAULT_DOCUMENTS: List[Dict[str, str]] = load_documents()
