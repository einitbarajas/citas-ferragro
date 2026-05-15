# -*- coding: utf-8 -*-
"""Genera ESPECIFICACION_REQUISITOS_IEEE830_FERRAGRO.docx copiando la plantilla IEEE 830."""
from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

from docx import Document
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parent
TEMPLATE = Path(r"c:\Users\ebarajas\Downloads\plantillaformatoieee830(RESERVIFY).docx")
REQ_JSON = ROOT / "_req_dump.json"
OUTPUT = ROOT / "ESPECIFICACION_REQUISITOS_IEEE830_FERRAGRO.docx"


def _delete_paragraph(paragraph: Paragraph) -> None:
    element = paragraph._element
    element.getparent().remove(element)


def _insert_after(paragraph: Paragraph, text: str, style_name: str | None = None) -> Paragraph:
    new_p = paragraph._element.makeelement(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
    )
    paragraph._element.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    if style_name:
        try:
            new_para.style = style_name
        except KeyError:
            pass
    new_para.add_run(text)
    return new_para


def _set_text(paragraph: Paragraph, text: str) -> None:
    if not paragraph.runs:
        paragraph.add_run(text)
        return
    paragraph.runs[0].text = text
    for run in paragraph.runs[1:]:
        run.text = ""


def _load_req_rows(sheet: str) -> list[tuple[str, str]]:
    if not REQ_JSON.exists():
        return []
    data = json.loads(REQ_JSON.read_text(encoding="utf-8"))
    rows = []
    for row in data.get("sheets", {}).get(sheet, []):
        cells = row.get("cells", [])
        if len(cells) < 3:
            continue
        num, desc = str(cells[1]).strip(), str(cells[2]).strip()
        if num.isdigit() and desc:
            rows.append((num, re.sub(r"\s+", " ", desc)))
    return rows


def _replace_global(doc: Document) -> None:
    mapping = {
        "RESERVIFY": "FERRAGRO",
        "Reservify": "Ferragro",
        "reservify": "ferragro",
        "restaurantes": "entregas de materiales",
        "restaurante": "empresa / bodega",
        "reservas": "citas de entrega",
        "reserva": "cita de entrega",
        "comensales": "proveedores",
        "mesas": "franjas horarias",
        "mesa": "franja horaria",
        "Wompi": "[no aplica en Ferragro]",
        "TypeScript": "JavaScript (React)",
    }
    for paragraph in doc.paragraphs:
        text = paragraph.text
        if not text:
            continue
        new = text
        for old, new_val in mapping.items():
            new = new.replace(old, new_val)
        if new != text:
            _set_text(paragraph, new)


def _patch_cover(doc: Document) -> None:
    for p in doc.paragraphs[:40]:
        t = p.text.strip()
        if t == "Proyecto: FERRAGRO" or t.startswith("Proyecto: RESERVIFY"):
            _set_text(p, "Proyecto: FERRAGRO — Gestión de Citas de Entrega de Materiales")
        if "Revisión" in t and "1.0" in t:
            _set_text(p, "Revisión 1.0")


def _patch_intro_blocks(doc: Document) -> None:
    replacements = {
        "En Colombia, la oferta de aplicaciones": (
            "En el sector agroindustrial, la coordinación de entregas de materiales requiere "
            "ventanas horarias controladas y trazabilidad. Ferragro necesita digitalizar el "
            "agendamiento de citas de entrega para reducir errores y conflictos de horario."
        ),
        "Este documento especifica los requisitos de software para **Ferragro**": (
            "Este documento especifica los requisitos de software para **Ferragro**, sistema web "
            "de gestión de citas de entrega de materiales para proveedores y personal interno "
            "(Admin, Logística, Proveedor)."
        ),
        "Ferragro es una aplicación web full-stack que permite:": (
            "Ferragro es una aplicación web full-stack que permite:"
        ),
    }
    for p in doc.paragraphs:
        for prefix, new_text in replacements.items():
            if p.text.strip().startswith(prefix.split("**")[0][:30]):
                _set_text(p, new_text)
                break


def _find_heading_index(doc: Document, fragment: str) -> int | None:
    frag = fragment.lower()
    for i, p in enumerate(doc.paragraphs):
        if frag in p.text.lower() and (p.style.name.startswith("Heading") or p.text.strip().startswith("3.")):
            if p.style.name.startswith("Heading") or fragment.lower() in p.text.lower()[:40]:
                return i
    return None


def _find_heading1(doc: Document, fragment: str) -> int | None:
    frag = fragment.lower()
    for i, p in enumerate(doc.paragraphs):
        if frag in p.text.lower() and p.style.name == "Heading 1":
            return i
    return None


def _clear_section(doc: Document, start: int, end: int) -> None:
    """Elimina párrafos entre start (exclusivo) y end (exclusivo)."""
    to_remove = [doc.paragraphs[i] for i in range(start + 1, end)]
    for p in to_remove:
        _delete_paragraph(p)


def _append_requirements(doc: Document, anchor: Paragraph) -> Paragraph:
    """Inserta requisitos Ferragro después del párrafo anchor."""
    current = anchor
    sheets = [
        ("3.1.1 Requisitos funcionales — Backend", "ReqFunBackend"),
        ("3.1.2 Requisitos funcionales — Frontend", "ReqFunFrontend"),
        ("3.1.3 Requisitos funcionales — Base de datos", "ReqFunBD"),
    ]
    rf = 1
    for section_title, sheet in sheets:
        current = _insert_after(current, section_title, "Heading 2")
        for num, desc in _load_req_rows(sheet):
            code = f"RF-{rf:03d}"
            rf += 1
            current = _insert_after(current, f"{code}: Requisito {sheet} #{num}", "normal")
            current = _insert_after(current, f"- Prioridad: {'Alta' if int(num) <= 15 else 'Media'}", "normal")
            current = _insert_after(current, f"- Descripción: {desc}", "normal")
            current = _insert_after(
                current,
                "- Procesamiento: Validación en API/servicios, persistencia PostgreSQL, respuesta JSON estándar.",
                "normal",
            )
            current = _insert_after(current, "", "normal")

    current = _insert_after(current, "3.2 Requisitos No Funcionales", "Heading 2")
    rnfs = [
        ("RNF-001", "Rendimiento API", "Operaciones frecuentes < 500 ms en entorno objetivo."),
        ("RNF-002", "Carga web", "Pantallas principales < 2 s."),
        ("RNF-003", "Seguridad", "bcrypt, JWT, refresh HttpOnly, rate limiting, auditoría de login."),
        ("RNF-004", "Disponibilidad", "Health check /health; objetivo 99 % mensual en producción."),
        ("RNF-005", "Usabilidad", "Interfaz responsiva, mensajes de error claros, tema claro/oscuro."),
        ("RNF-006", "Mantenibilidad", "API /api/v1, OpenAPI, estructura modular backend/frontend."),
    ]
    for code, title, desc in rnfs:
        current = _insert_after(current, f"{code}: {title}", "normal")
        current = _insert_after(current, f"- Descripción: {desc}", "normal")

    for sheet, title in [
        ("ReqNoFunBackend", "3.2.1 No funcionales Backend (matriz req_trabajo)"),
        ("ReqNoFunFrontend", "3.2.2 No funcionales Frontend (matriz req_trabajo)"),
        ("ReqNoFunDB", "3.2.3 No funcionales BD (matriz req_trabajo)"),
    ]:
        rows = _load_req_rows(sheet)
        if not rows:
            continue
        current = _insert_after(current, title, "Heading 2")
        for num, desc in rows:
            current = _insert_after(current, f"- {sheet}-{num}: {desc}", "normal")

    current = _insert_after(current, "3.3 Interfaces del sistema", "Heading 2")
    for line in [
        "3.3.1 UI: aplicación web React (login, panel por rol, calendario de franjas, citas).",
        "3.3.2 Hardware: navegador en PC/móvil; servidor ASGI + PostgreSQL.",
        "3.3.3 Software: API REST JSON, PostgreSQL, SMTP opcional, Cloudinary opcional.",
        "3.3.4 Comunicaciones: HTTPS en producción, CORS, X-Correlation-ID.",
    ]:
        current = _insert_after(current, line, "normal")

    return current


def build_document() -> Path:
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"No se encontró la plantilla: {TEMPLATE}")

    shutil.copy2(TEMPLATE, OUTPUT)
    doc = Document(str(OUTPUT))

    _replace_global(doc)
    _patch_cover(doc)
    _patch_intro_blocks(doc)

    req_idx = _find_heading1(doc, "Requisitos espec")
    test_idx = _find_heading1(doc, "Gesti")
    if req_idx is None or test_idx is None:
        raise RuntimeError("No se encontraron secciones Requisitos específicos / Gestión de pruebas en la plantilla.")

    anchor = doc.paragraphs[req_idx]
    _clear_section(doc, req_idx, test_idx)

    # Re-localizar anchor tras borrados
    for i, p in enumerate(doc.paragraphs):
        if p.style.name == "Heading 1" and "requisitos espec" in p.text.lower():
            anchor = p
            break

    _insert_after(anchor, "3.1 Requisitos Funcionales", "Heading 2")
    _append_requirements(doc, anchor)

    # Actualizar ficha si existe tabla
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if "RESERVIFY" in cell.text or "Reservify" in cell.text:
                    cell.text = cell.text.replace("RESERVIFY", "FERRAGRO").replace("Reservify", "Ferragro")

    doc.save(str(OUTPUT))
    return OUTPUT


if __name__ == "__main__":
    out = build_document()
    print(f"Documento Word generado: {out}")
