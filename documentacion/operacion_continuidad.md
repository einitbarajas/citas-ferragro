# Operación, continuidad y seguridad (referencia)

Este documento cumple la parte **documental / operativa** de requisitos no funcionales que dependen del entorno de despliegue (backups cifrados, RPO/RTO, HA, monitoreo de BD).

## Objetivos acordados (ajustar por proyecto)

| Métrica | Objetivo sugerido | Verificación |
|--------|-------------------|--------------|
| **RPO** (pérdida máxima de datos aceptable) | ≤ 24 h | Último backup restaurable |
| **RTO** (tiempo máximo para volver a operar) | ≤ 4 h | Ejercicio anual de restauración |
| **Disponibilidad** | ≥ 99 % mensual | SLI/uptime monitor |

## Backups PostgreSQL

1. **Copia lógica diaria** con `pg_dump` / `pg_dumpall` hacia almacenamiento separado del servidor de BD.
2. **Cifrado en reposo**: usar disco/S3 con SSE-KMS o empaquetar el `.dump` con herramientas que soporten AES (p. ej. `age`, `gpg`) antes de subirlo.
3. **Retención**: conservar al menos 7 copias diarias + 4 semanales (ajustar compliance interno).
4. **Prueba de restauración**: trimestral en entorno de staging.

### Ejemplo (referencia, no ejecutar en producción sin revisar rutas)

```bash
pg_dump -Fc "$DATABASE_URL" > backup.dump
age -r "$AGE_PUBLIC_KEY" -o backup.dump.age backup.dump
```

## Monitoreo

- **Aplicación**: endpoint `/health` detrás del balanceador; alertas si código ≠ 200.
- **PostgreSQL**: integrar `pg_stat_statements` y alertas de conexiones/lento en la plataforma elegida (Datadog, Prometheus postgres_exporter, etc.).
- **Logs**: cabecera `X-Correlation-ID` propagada por el middleware HTTP para trazar peticiones.

## Roles de base de datos (mínimo privilegio)

Ejecutar en PostgreSQL cuentas separadas: `app_readwrite`, `app_readonly`, `migration_admin`. Los grants exactos dependen del esquema; usar `db/init` como fuente de verdad y documentar grants en un script revisado por DBA.

## Mantenimiento PostgreSQL

Programar **VACUUM / ANALYZE** vía `autovacuum` (por defecto activo) y revisar tablas de alto crecimiento (`Citas`, `HistorialCambios`, `AuditoriaLogin`, `SesionesRefresh`).

## Archivo histórico / particionamiento

Para tablas muy grandes, valorar particionamiento por rango de fechas y políticas de archivo en tablas históricas; implementación específica debe validarse con volumetría real.
