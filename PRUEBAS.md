# Ferragro — Pruebas de caja negra, gris y blanca

**Nota:** La plantilla que compartiste corresponde a otro producto (**Reservify**). Este documento está adaptado al **Portal de citas de entrega Ferragro** (React + FastAPI + PostgreSQL).

## Cómo se aplican los tres enfoques aquí

| Enfoque | Qué conoces | Ejemplos en este proyecto |
|--------|-------------|---------------------------|
| **Caja negra** | Solo requisitos y comportamiento observable (UI o API sin mirar código). | Login con credenciales incorrectas; landing sin sesión; listado de citas tras autenticarse. |
| **Caja gris** | Contrato parcial: endpoints, JSON `{ success, data, message }`, roles, `.env` de prueba; **no** revisas cada rama interna. | `POST /api/v1/auth/login` con cuerpo válido vs token JWT en `GET /appointments`; códigos HTTP esperados. |
| **Caja blanca** | Código y ramas: condiciones, middleware, límites, SQL. | Middleware de consultas sospechosas en `main.py`; `rate_limit_enabled`; filtros por rol en `appointments.py`; validación de NIT en registro. |

Rellena **Project Name**, **Release Version**, **Tester Name** y **Testing Date(s)** en cada bloque según tu entrega.

---

## Encabezado común (copiar y completar)

| Campo | Valor |
|-------|--------|
| **Project Name** | Ferragro — Portal citas de entrega |
| **Release Version** | *(ej. 1.0.0-rc1)* |
| **Tester Name** | *(tu nombre)* |
| **Testing Date(s)** | *(ej. 12/05/2026)* |

**Pre-condición general:** Backend y base de datos en ejecución; frontend accesible (Vite o build). Datos de prueba coherentes con tu `.env` y seed (si aplica).

**Post-condición general:** Sin datos de producción modificados si usas entorno aislado; cerrar sesión o revocar tokens de prueba si procede.

**Status (regla):** en la fila **Status** de cada caso escribe **una sola palabra**: **`Pass`** si el resultado real cumple lo esperado, o **`Fail`** si no. No uses `Pass/Fail`, listas ni texto mixto en esa celda. Los casos incluyen **Pass** como valor inicial; **cámbialo a Fail** si la ejecución demuestra que no se cumple lo esperado.

---

# CAJA NEGRA

*El tester **no** usa el código fuente como referencia; solo la interfaz y/o el comportamiento acordado.*

---

## Test case NB-1: Landing (página pública inicial)

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | NB-1 |
| **Test Priority** | Media |
| **Test Title/Name** | Landing — navegación pública y enlaces de contacto |
| **Test Summary** | Validar que un usuario sin sesión ve la portada, puede ir a Iniciar sesión / Registrarme, y que los enlaces de contacto abren el destino correcto (WhatsApp / correo). |
| **Test Steps** | 1) Abrir la URL raíz del frontend. 2) Comprobar título/hero (“Portal de proveedores…” o similar). 3) Pulsar **Iniciar sesión** y ver formulario de login. 4) Volver atrás si existe y pulsar **Registrarme**. 5) En landing, pulsar enlace **WhatsApp** y **Correo** en “Información de contacto”. |
| **Test Data** | URL front: `http://localhost:2711` (o la que uses). WhatsApp esperado: enlace `https://wa.me/573142254819`. Correo: `mailto:ecommerce@ferragro.com`. |
| **Expected Result** | Landing carga sin errores visibles; botones llevan a login/registro; enlaces externos/mailto son los indicados (no redirigen a búsqueda genérica). |
| **Actual Result** | *(rellenar al ejecutar)* |
| **Pre-condition** | Sin cookie de sesión activa (navegador limpio o ventana privada). |
| **Post-condition** | Usuario sigue sin sesión o en pantalla login/registro según última acción. |
| **Status** | Pass |
| **Notes/Comments** | Caja negra: no se inspecciona `LandingPage.jsx`; solo comportamiento observable. |

---

## Test case NB-2: Login — credenciales inválidas

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | NB-2 |
| **Test Priority** | Alta |
| **Test Title/Name** | Login — rechazo con email o contraseña incorrectos |
| **Test Summary** | Verificar que el sistema no otorga acceso y muestra mensaje comprensible ante credenciales erróneas. |
| **Test Steps** | 1) Ir a login. 2) Introducir email no registrado y contraseña cualquiera; enviar. 3) Introducir email válido de prueba y contraseña incorrecta; enviar. |
| **Test Data** | Email inexistente: `noexiste@test.local`. Email válido de tu BD de prueba + contraseña errónea: `MalPass#123`. |
| **Expected Result** | No acceso al dashboard; mensaje de error coherente (no stack trace); no filtrar si el email existe o no de forma agresiva en UI. |
| **Actual Result** | *(rellenar)* |
| **Pre-condition** | API disponible; usuario de prueba opcional para el paso 3. |
| **Post-condition** | Sin token válido en cliente. |
| **Status** | Pass |
| **Notes/Comments** | No mirar implementación de `verify_password`; solo resultado observable. |

---

## Test case NB-3: Dashboard — proveedor ve solo sus citas

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | NB-3 |
| **Test Priority** | Alta |
| **Test Title/Name** | Listado de citas — aislamiento por proveedor |
| **Test Summary** | Con sesión de **Proveedor**, el listado no debe mostrar citas de otros NITs (validación funcional desde la UI). |
| **Test Steps** | 1) Login como proveedor A. 2) Abrir listado/calendario de citas. 3) Anotar cantidad y NIT/nombre mostrados. 4) Cerrar sesión y repetir con proveedor B si existe en datos de prueba. |
| **Test Data** | Cuentas proveedor A y B de tu entorno de prueba (emails/NIT según seed o datos creados manualmente). |
| **Expected Result** | Cada proveedor solo ve información asociada a su empresa; no aparecen citas “cruzadas”. |
| **Actual Result** | *(rellenar)* |
| **Pre-condition** | Citas de prueba creadas para al menos dos proveedores (o documentar “N/A” si solo hay uno). |
| **Post-condition** | Sesión del último usuario probado. |
| **Status** | Pass |
| **Notes/Comments** | Caja negra: no se revisa la cláusula SQL en el backend. |

---

## Test case NB-4: Registro proveedor — validación de formulario

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | NB-4 |
| **Test Priority** | Media |
| **Test Title/Name** | Registro — NIT y dígito de verificación |
| **Test Summary** | Intentar registrar con NIT incompleto o dígito inválido y comprobar mensajes en pantalla. |
| **Test Steps** | 1) Ir a Registrarme. 2) NIT con 9 dígitos; enviar o avanzar. 3) NIT con 10 dígitos pero dígito de verificación con 2 dígitos. 4) Corregir según mensajes hasta formato aceptado (sin completar registro real si no deseas datos nuevos). |
| **Test Data** | NIT corto: `90012345`. DV inválido: `12`. NIT válido de prueba no duplicado en BD: *(definir según tu rango libre)*. |
| **Expected Result** | La interfaz impide o advierte formatos inválidos antes de crear cuenta; no “cuelgue” sin mensaje. |
| **Actual Result** | *(rellenar)* |
| **Pre-condition** | Modo registro proveedor disponible. |
| **Post-condition** | Opcional: eliminar usuario de prueba si se creó. |
| **Status** | Pass |
| **Notes/Comments** | |

---

# CAJA GRIS

*Conoces **contrato** de API (rutas, JSON, roles) y/o configuración de entorno, pero no diseñas casos a partir de cada `if` del código.*

---

## Test case CG-1: Contrato `POST /auth/login`

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | CG-1 |
| **Test Priority** | Alta |
| **Test Title/Name** | Login API — estructura `success` / `data.access_token` |
| **Test Summary** | Llamar al login con JSON válido y comprobar cuerpo estándar del proyecto. |
| **Test Steps** | 1) `POST {BASE}/api/v1/auth/login` con `Content-Type: application/json`. 2) Cuerpo `{"email":"...","password":"..."}`. 3) Parsear JSON y validar presencia de `success`, `data.access_token`, `message`. |
| **Test Data** | `BASE`: `http://127.0.0.1:8000`. Credenciales válidas de prueba. |
| **Expected Result** | HTTP 200; `success === true`; `data.access_token` string no vacío; `message` descriptivo. |
| **Actual Result** | *(rellenar)* |
| **Pre-condition** | Misma versión de prefijo que el front (`/api/v1` por defecto en cliente). |
| **Post-condition** | *(n/a o revocar refresh si pruebas de seguridad)* |
| **Status** | Pass |
| **Notes/Comments** | No hace falta abrir `auth.py`; basta OpenAPI `/docs` o README. |

---

## Test case CG-2: `GET /appointments` sin token

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | CG-2 |
| **Test Priority** | Alta |
| **Test Title/Name** | Citas — acceso no autenticado |
| **Test Summary** | Verificar que el endpoint protegido responde 401/403 sin `Authorization`. |
| **Test Steps** | 1) `GET {BASE}/api/v1/appointments?mode=list` sin cabecera Bearer. 2) Opcional: con Bearer malformado `Bearer xxx`. |
| **Test Data** | Sin cuerpo; query mínima `mode=list`. |
| **Expected Result** | No 200 con lista de citas; código de error apropiado y cuerpo `success: false` o esquema de error del proyecto. |
| **Actual Result** | *(rellenar)* |
| **Pre-condition** | API levantada. |
| **Post-condition** | — |
| **Status** | Pass |
| **Notes/Comments** | Caja gris: sabes el contrato de seguridad, no la implementación del dependency `require_roles`. |

---

## Test case CG-3: Rate limit en rutas de auth

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | CG-3 |
| **Test Priority** | Media |
| **Test Title/Name** | Auth — muchos intentos de login |
| **Test Summary** | Sabes que existe límite por minuto en auth (`rate_limit_per_minute_auth` en configuración); validar 429 tras superar umbral **sin** leer código de SlowAPI. |
| **Test Steps** | 1) Enviar más de N peticiones `POST .../auth/login` en menos de 1 minuto (N según `.env`, típ. 20). 2) Observar si aparece HTTP 429. |
| **Test Data** | Mismo cuerpo de login inválido para no bloquear cuenta real por contraseñas erróneas alternadas; o usar herramienta de carga con email ficticio. |
| **Expected Result** | Tras el umbral, respuestas 429 o mensaje de rate limit; servidor estable. |
| **Actual Result** | *(rellenar)* |
| **Pre-condition** | `RATE_LIMIT_ENABLED=true` en entorno donde pruebas. |
| **Post-condition** | Esperar ventana de minuto o reiniciar proceso si necesitas limpiar estado en memoria. |
| **Status** | Pass |
| **Notes/Comments** | Conoces el **parámetro** de negocio, no cada línea del limiter. |

---

## Test case CG-4: Refresh con cookie HttpOnly

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | CG-4 |
| **Test Priority** | Media |
| **Test Title/Name** | Sesión — refresh según contrato front |
| **Test Summary** | Tras login desde navegador, comprobar que existe cookie de refresh y que `POST .../auth/refresh` puede devolver nuevo access token (desde DevTools o script con cookie jar). |
| **Test Steps** | 1) Login válido en UI. 2) En aplicación de API (Postman/curl con `-c`/`-b`), repetir flujo login y refresh. 3) Verificar JSON de refresh. |
| **Test Data** | Nombre cookie por defecto: `refresh_token` (según configuración). |
| **Expected Result** | Refresh coherente con documentación; access token renovado cuando refresh válido. |
| **Actual Result** | *(rellenar)* |
| **Pre-condition** | CORS y cookies acordes a tu origen (localhost). |
| **Post-condition** | Logout si aplica. |
| **Status** | Pass |
| **Notes/Comments** | |

---

# CAJA BLANCA

*Casos derivados del **código** o esquema: ramas, middleware, regex, índices SQL.*

---

## Test case CB-1: Middleware — parámetro de query con patrón sospechoso

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | CB-1 |
| **Test Priority** | Alta |
| **Test Title/Name** | `SUSPICIOUS_QUERY_PATTERNS` — rechazo de patrones tipo SQLi |
| **Test Summary** | El middleware en `app/main.py` inspecciona query strings; debe bloquear valores que coincidan con patrones definidos (p. ej. `UNION SELECT`). |
| **Test Steps** | 1) Revisar en código las regex `SUSPICIOUS_QUERY_PATTERNS`. 2) `GET /health?test=union%20select` o variante que dispare el patrón. 3) Confirmar respuesta de error del middleware (p. ej. 400) sin ejecutar SQL del atacante. |
| **Test Data** | Valores acordes a cada regex del archivo (documentar cuál patrón se probó). |
| **Expected Result** | Petición rechazada; no propagación del valor a lógica de negocio; log/respuesta acorde a implementación. |
| **Actual Result** | *(rellenar)* |
| **Pre-condition** | Rama de código con middleware activo. |
| **Post-condition** | — |
| **Status** | Pass |
| **Notes/Comments** | **Caja blanca pura:** requiere leer `main.py`. |

---

## Test case CB-2: `rate_limit_enabled` desactivado

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | CB-2 |
| **Test Priority** | Baja (solo entornos de prueba) |
| **Test Title/Name** | SlowAPI — `enabled=False` |
| **Test Summary** | Con `RATE_LIMIT_ENABLED=false`, el `Limiter` no debe aplicar límites (comprobar ausencia de 429 por rate limit bajo burst controlado). |
| **Test Steps** | 1) Arrancar API con variable de entorno. 2) Verificar en `app/core/rate_limit.py` que `enabled=settings.rate_limit_enabled`. 3) Ejecutar ráfaga de `GET /health` y contrastar con `true`. |
| **Test Data** | `RATE_LIMIT_ENABLED=false` / `true`. |
| **Expected Result** | Con `false`, sin 429 por SlowAPI bajo la misma carga; con `true`, límites activos. |
| **Actual Result** | *(rellenar)* |
| **Pre-condition** | No usar en producción. |
| **Post-condition** | Restaurar `true`. |
| **Status** | Pass |
| **Notes/Comments** | |

---

## Test case CB-3: Listado de citas — rama `principal.role_name == Proveedor`

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | CB-3 |
| **Test Priority** | Alta |
| **Test Title/Name** | `list_appointments` — filtro `provider_id` forzado por sujeto JWT |
| **Test Summary** | En código (`appointments.py`), si el rol es Proveedor, el `stmt` incluye `where(Appointment.provider_id == int(principal.subject))`. Probar con token cuyo `sub` sea NIT conocido y verificar solo filas de ese NIT en respuesta. |
| **Test Steps** | 1) Leer la rama en `list_appointments`. 2) Insertar o usar citas con dos `provider_id` distintos en BD. 3) JWT de proveedor A; inspeccionar JSON `data.items`. |
| **Test Data** | NIT A y B; token decodificado (sin verificar firma en test manual) para confirmar `sub`. |
| **Expected Result** | Ningún `item` con `provider_id` distinto del NIT del token. |
| **Actual Result** | *(rellenar)* |
| **Pre-condition** | Datos en BD alineados con el escenario. |
| **Post-condition** | — |
| **Status** | Pass |
| **Notes/Comments** | Combinación blanca + verificación objetiva en JSON. |

---

## Test case CB-4: Registro proveedor — validación NIT 10 dígitos en backend

| Campo | Contenido |
|-------|-----------|
| **Test Case #** | CB-4 |
| **Test Priority** | Media |
| **Test Title/Name** | `register` — ramas `len(payload.document_id) != 10` |
| **Test Summary** | En `auth.py` registro proveedor: documento debe ser 10 dígitos. Probar con API directa `POST .../auth/register` y cuerpos inválidos/válidos. |
| **Test Steps** | 1) Localizar validaciones en código. 2) Enviar `document_id` con 9 dígitos → 400. 3) Enviar 10 dígitos + resto de campos válidos (o esperar 400 por duplicado si ya existe). |
| **Test Data** | NIT 9 dígitos: `900123456`; NIT 10: definir no duplicado. |
| **Expected Result** | Mensajes `detail` / `error_response` acordes a las ramas leídas. |
| **Actual Result** | *(rellenar)* |
| **Pre-condition** | Roles `Proveedor` existentes en BD. |
| **Post-condition** | Limpiar registro de prueba si se creó. |
| **Status** | Pass |
| **Notes/Comments** | |

---

## Resumen rápido

- **Caja negra:** NB-1 a NB-4 (UI y comportamiento sin código).
- **Caja gris:** CG-1 a CG-4 (contrato API / config).
- **Caja blanca:** CB-1 a CB-4 (middleware, flags, ramas en `appointments` / `auth`).

Puedes duplicar filas en tu hoja de cálculo y añadir IDs **NB-5**, **CG-5**, etc., para flujos que te falten (cambio de estado de cita, extend, admin logs).
