# Operación y continuidad — Ferragro Citas

Guía de respaldo, recuperación y disponibilidad del entorno **Vercel + Render**.

---

## 1. Componentes y criticidad

| Componente | Servicio | Si falla |
|------------|----------|----------|
| Frontend | Vercel | No hay portal; API y BD pueden seguir |
| API | Render `ferragro-api` | No hay login ni citas; front muestra error de conexión |
| Base de datos | Render `ferragro-db` | Pérdida de datos operativos; crítico |

La BD **no se “duerme”** como el API en plan Free; el API sí puede tardar **30–90 s** en la primera petición tras ~15 min sin uso.

---

## 2. Objetivos orientativos (RPO / RTO)

| Métrica | Objetivo práctico (plan actual) |
|---------|----------------------------------|
| **RPO** (pérdida máxima de datos) | 24 h si solo hay backup diario; **1 h** si se automatiza backup más frecuente |
| **RTO** (tiempo para volver a operar) | 2–4 h (recrear servicio Render + restaurar dump + redeploy front) |

---

## 3. Backups de PostgreSQL

### 3.1 Backup manual (recomendado antes de cambios SQL en producción)

Con la **External Database URL** de Render (`ferragro-db` → Connections):

```powershell
$env:PGPASSWORD = "..."   # solo en sesión local, no guardar en repo
pg_dump "postgresql://ferragro:...@....render.com:5432/ferragro" `
  -Fc -f "ferragro-backup-$(Get-Date -Format yyyyMMdd-HHmm).dump"
```

Formato `-Fc` (custom) permite restaurar con `pg_restore`.

### 3.2 Frecuencia sugerida

| Entorno | Frecuencia |
|---------|------------|
| Producción | Diario (automatizar con tarea programada o GitHub Actions con secreto `DATABASE_URL`) |
| Antes de `db/init/*.sql` nuevo | Siempre |
| Desarrollo local | Opcional |

### 3.3 Restauración (escenario desastre)

1. Crear BD nueva o vaciar esquema `public` (con extremo cuidado).
2. `pg_restore -d "postgresql://..." -c backup.dump` (probar primero en staging).
3. Ejecutar `db/run-database-all.ps1` **sin** `-Seed` si el dump ya trae datos.
4. Si solo faltan funciones CRUD: `db/run-database-crud.ps1`.
5. Redeploy API y comprobar `GET /health`.

---

## 4. Migraciones de esquema

Orden en producción:

1. Backup (`pg_dump`).
2. Scripts `db/init/00X_*.sql` pendientes (hasta `015` en el repo actual).
3. `db/run-database-crud.ps1` si cambió algún `.sql` en `database-crud/`.
4. Deploy del API en Render.

No usar `-Seed` en producción.

---

## 5. Monitoreo mínimo

| Control | Acción |
|---------|--------|
| API vivo | `GET https://ferragro-api.onrender.com/health` → `success: true`, `build_id` actual |
| Correo | `email_enabled: true` en `/health` |
| Deploy | Render/Vercel → estado **Live** / **Ready** tras push a `main` |

Opcional: UptimeRobot cada 5–15 min en `/health` (mantiene el API despierto en plan Free; consume cuota).

---

## 6. Plan Free de Render

- API: cold start tras inactividad.
- BD gratuita: revisar avisos de expiración en el dashboard.
- Mitigación: plan de pago en el web service o aceptar latencia en la primera visita del día.

---

## 7. Documentos relacionados

- [GUIA_OPERACION_PRODUCCION.md](GUIA_OPERACION_PRODUCCION.md) — operación día a día
- [ESCALABILIDAD.md](ESCALABILIDAD.md) — rendimiento y carga
- [PRUEBAS.md](PRUEBAS.md) — validación antes de releases

---

*Última actualización: mayo 2026.*
