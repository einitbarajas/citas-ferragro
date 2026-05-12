# REQUERIMIENTOS ADICIONALES DEL SISTEMA

Documento complementario a `documentacion/req_trabajo.xlsx`.  
Los requerimientos de este archivo se proponen como **nuevos** y se mantienen divididos con la misma estructura del documento base.

---

## ReqFunBackend

### REQUISITOS FUNCIONALES BACKEND (ADICIONALES)

15. Invalidar refresh tokens al cerrar sesion en todos los dispositivos del usuario.  
16. Bloquear temporalmente el acceso despues de multiples intentos fallidos de autenticacion.  
17. Registrar en auditoria los eventos de login exitoso y login fallido.  
18. Permitir filtrado de citas por estado y por proveedor en endpoints de consulta.  
19. Permitir exportar listado de citas en formato CSV para roles internos autorizados.  
20. Incluir paginacion y ordenamiento en consultas de citas y logs.  
21. Enviar recordatorios de cita programada mediante tarea automatizada (scheduler).  
22. Implementar endpoint de salud (`/health`) para monitoreo del servicio.  
23. Versionar API (`/api/v1/...`) para compatibilidad futura.  
24. Agregar trazabilidad de cambios de campos criticos (estado, fecha, hora, duracion) con valor anterior y nuevo valor.

---

## ReqNoFunBackend

### REQUISITOS NO FUNCIONALES BACKEND (ADICIONALES)

10. Cobertura minima de pruebas automatizadas para modulos criticos de negocio.  
11. Tolerancia a fallos con respuestas controladas ante caida de servicios dependientes.  
12. Configuracion centralizada por ambiente (dev, test, prod) sin cambios de codigo.  
13. Estandar de logs con identificador de correlacion por request.  
14. Limite de tasa (rate limiting) en endpoints de autenticacion y operaciones sensibles.  
15. Tiempo maximo de recuperacion del servicio definido para incidentes criticos.  
16. Validacion estricta de payloads con esquemas y mensajes de error consistentes.  
17. Compatibilidad con despliegue en contenedores para portabilidad operacional.

---

## ReqFunFrontend

### REQUISITOS FUNCIONALES FRONTEND (ADICIONALES)

16. Cerrar sesion automaticamente cuando el refresh token expire y redirigir a login.  
17. Mostrar historial de cambios de una cita desde el detalle de la misma (segun rol).  
18. Permitir filtros combinados en el tablero (rango de fechas, estado, proveedor).  
19. Incluir busqueda rapida de citas por texto (material o identificador).  
20. Confirmar acciones criticas (cambio de estado, extension, eliminacion) con dialogo modal.  
21. Permitir duplicar una cita existente para acelerar nuevos registros similares.  
22. Mostrar indicador visual de conflicto potencial al editar fecha/hora antes de guardar.  
23. Incorporar vista de resumen con metricas basicas (citas por estado y por periodo).  
24. Permitir descarga local de resultados filtrados en CSV desde la interfaz.  
25. Soportar cambio de contrasena desde perfil de usuario autenticado.

---

## ReqNoFunFrontend

### REQUISITOS NO FUNCIONALES FRONTEND (ADICIONALES)

9. Mantener consistencia visual con un sistema de diseno (colores, tipografias y componentes).  
10. Cumplir criterios basicos de accesibilidad WCAG (etiquetas, foco visible y navegacion teclado).  
11. Reducir peso inicial del bundle mediante carga diferida de modulos no criticos.  
12. Soportar modo de red lenta con mensajes de estado claros y reintento de peticiones.  
13. Evitar perdida de datos en formularios con guardado temporal local.  
14. Garantizar compatibilidad responsive en resoluciones comunes del entorno operativo.  
15. Manejar errores globales de red con una capa unificada de notificaciones.  
16. Internacionalizacion preparada para textos de interfaz (estructura i18n).

---

## ReqFunBD

### REQUISITOS FUNCIONALES BASE DE DATOS (ADICIONALES)

9. Almacenar refresh tokens y sesiones activas por usuario para permitir invalidacion selectiva o global.  
10. Registrar en tabla de auditoria los cambios de estado de citas con usuario, fecha/hora y valores anterior/nuevo.  
11. Soportar consulta eficiente de citas por estado, proveedor y rango de fechas mediante estructuras de datos adecuadas.  
12. Mantener historial de reprogramaciones de citas (fecha/hora previa y nueva) con motivo del cambio.  
13. Almacenar eventos de autenticacion (exitoso/fallido) con metadatos basicos para analisis posterior.  
14. Persistir configuraciones operativas del sistema (parametros de negocio) en tablas administrables.  
15. Registrar ejecuciones de tareas programadas (recordatorios) con estado, fecha de envio y resultado.  
16. Versionar cambios de esquema y datos maestros mediante migraciones trazables en base de datos.

---

## ReqNoFunDB

### REQUISITOS NO FUNCIONALES BASE DE DATOS (ADICIONALES)

10. Politica de retencion de auditoria con archivado historico por periodos.  
11. Estrategia de particionamiento para tablas de alto crecimiento (citas y logs).  
12. Cifrado de respaldos y control de acceso al almacenamiento de copias.  
13. Monitoreo de rendimiento con metricas de consultas lentas y uso de indices.  
14. Definicion de objetivos RPO/RTO para continuidad del servicio.  
15. Ejecucion periodica de mantenimiento (vacuum/analyze o equivalente).  
16. Versionado de scripts SQL y trazabilidad de migraciones aplicadas.  
17. Politica de minimo privilegio para usuarios tecnicos y de aplicacion.

---

## Nota de uso sugerida

Si quieres pasarlo luego a tu formato de checklist (SI / Parcial / NO / ADI), puedes copiar cada bloque por hoja del Excel:

- `ReqFunBackend`
- `ReqNoFunBackend`
- `ReqFunFrontend`
- `ReqNoFunFrontend`
- `ReqFunBD`
- `ReqNoFunDB`

