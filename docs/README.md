# Documentación Ferragro Citas

Índice de la carpeta `docs/`. Los archivos **Markdown (`.md`)** son la fuente editable; los **Word/Excel** se regeneran con los scripts indicados.

## Documentos operativos (mantener en Markdown)

| Archivo | Contenido | Regenerar Word |
|---------|-----------|----------------|
| [GUIA_OPERACION_PRODUCCION.md](GUIA_OPERACION_PRODUCCION.md) | URLs, variables, Render/Vercel, SMTP, arranque, diagnóstico | `python docs/scripts/md_to_docx_guia.py` |
| [ESCALABILIDAD.md](ESCALABILIDAD.md) | Rendimiento, bodegas, índices, buenas prácticas de uso | — |
| [operacion_continuidad.md](operacion_continuidad.md) | Backups, RPO/RTO, recuperación | `python docs/scripts/md_to_docx_operacion.py` |
| [PRUEBAS.md](PRUEBAS.md) | Plan de pruebas (pytest, Locust, manual) | `python scripts/pruebas_md_to_docx.py` |

## Especificación y datos

| Archivo | Contenido | Regenerar |
|---------|-----------|-----------|
| [generate_ieee830.py](generate_ieee830.py) | Generador IEEE 830 (requisitos RF/RNF) | `python docs/generate_ieee830.py` → `ESPECIFICACION_REQUISITOS_IEEE830_FERRAGRO.docx` |
| [DICCIONARIO_DATOS_FERRAGRO.md](DICCIONARIO_DATOS_FERRAGRO.md) | Tablas, columnas, bodegas, citas | Revisar manualmente `DICCIONARIO_DATOS_FERRAGRO.docx` |
| [CUMPLIMIENTO_REQ.md](CUMPLIMIENTO_REQ.md) | Resumen de cumplimiento vs requisitos | Revisar `CUMPLIMIENTO_REQ.docx` |
| [MANUAL_USUARIO_PORTAL.md](MANUAL_USUARIO_PORTAL.md) | Uso del portal por rol | Revisar `MANUAL_USUARIO_Y_DOCUMENTACION.docx` |

## Hojas de cálculo (actualización manual)

| Archivo | Uso |
|---------|-----|
| `req_trabajo.xlsx` | Matriz de requisitos por capa (backend, front, BD) |
| `MATRIZ_TRAZABILIDAD_FERRAGRO.xlsx` | Trazabilidad RF ↔ pruebas |
| [DICCIONARIO_TRANSACCIONES.md](DICCIONARIO_TRANSACCIONES.md) | Resumen API / endpoints |
| `DICCIONARIO_TRANSACCIONES_FERRAGRO.xlsx` | Matriz detallada (actualizar manualmente) |

Herramienta auxiliar: `python docs/_extract_req.py` (vuelca `req_trabajo.xlsx` a `_req_dump.json`).

## Regenerar todos los Word desde Markdown

```powershell
cd "c:\dev\trabajo ferragro"
.\.venv\Scripts\python.exe -m pip install python-docx openpyxl  # si falta
.\docs\scripts\regenerate_docx.ps1
```

## Cambios recientes (mayo 2026)

- **Bodegas** (`014`): toda cita exige `IdBodega`; franjas por bodega.
- **Índices** (`015`): incluidos en `run-database-all`.
- **`citas_create`**: parámetro `p_id_bodega` opcional en `database-crud/citas/create.sql`.
- **Pruebas**: `backend/tests/test_db_crud_functions.py` (12 tests) y `test_logistics_business_rules.py`.

---

*Actualizar este README cuando se añadan nuevos documentos o scripts.*
