# PROYECTO FERRAGRO
## LEVANTAMIENTO DE REQUERIMIENTOS

**Version:** 1.0  
**Autor(es):** Equipo de desarrollo Ferragro  
**Entidad:** Ferragro  
**Ciudad y fecha:** Bucaramanga, 2026

---

## LISTA DE CAMBIOS

| Num. | Fecha | Descripcion | Autor |
|---|---|---|---|
| 0 | 2026-05-06 | Version inicial del informe en Markdown | Equipo Ferragro |

---

## CONTENIDO

1. Empresa (Mision, Vision e Historia)  
2. Politicas de la empresa  
3. Software a desarrollar  
4. Planteamiento del problema y alcance  
5. Mapa de proceso (entradas, procesos y salidas)  
6. Mapa de caso de uso (resumen funcional)  
7. Arbol de objetivos  
8. Arbol de problemas  
9. Diseno funcional de la aplicacion  
10. Modelo de datos (MR/MER)  
11. Premoldeado de la base de datos  
12. Consultas de prueba y validaciones de seguridad  
13. Objetivo general  
14. Objetivos especificos  
15. Tecnicas de recoleccion de datos  
16. Conclusiones  
17. Glosario  

---

## 1) EMPRESA FERRAGRO (MISION, VISION E HISTORIA)

### Mision
Facilitar la gestion de citas de entrega entre proveedores y personal interno de Ferragro, asegurando procesos logistico-operativos mas ordenados, trazables y eficientes.

### Vision
Consolidar una plataforma digital confiable para la planeacion de entregas y control de cambios operativos, mejorando la toma de decisiones en logistica y administracion.

### Historia (resumen del proyecto)
El proyecto surge de la necesidad de reducir conflictos de horario, reprocesos y falta de trazabilidad en la gestion de entregas.  
Se implementa una solucion web full-stack con backend en FastAPI, frontend en React y base de datos PostgreSQL para centralizar autenticacion, citas y auditoria de cambios.

---

## 2) POLITICAS DE LA EMPRESA

1. **Politica de calidad:** mantener disponibilidad, estabilidad y exactitud en la gestion de citas.  
2. **Politica de seguridad:** proteger credenciales, sesiones y trazabilidad con JWT, refresh token y controles por rol.  
3. **Politica de mejora continua:** evolucionar validaciones y flujos segun retroalimentacion operativa.  
4. **Politica de servicio interno y externo:** ofrecer una experiencia clara para proveedores, logistica y administradores.  
5. **Politica de cumplimiento de datos:** resguardar informacion operativa y registros de auditoria.

---

## 3) SOFTWARE A DESARROLLAR

Se desarrolla un sistema web de gestion de citas de entrega para Ferragro con:

- Registro e inicio de sesion de usuarios.
- Gestion de citas por proveedor.
- Validaciones de negocio (anticipacion minima y conflictos de horario).
- Cambio de estado y extension de citas por roles internos.
- Panel de auditoria para seguimiento de cambios.
- Integracion frontend-backend mediante contrato API estandar.

---

## 4) PLANTEAMIENTO DEL PROBLEMA Y ALCANCE

### Problema
- Las citas pueden presentar solapamientos si no se validan de forma centralizada.
- La coordinacion manual dificulta el seguimiento del estado de cada entrega.
- Sin auditoria, es complejo identificar quien modifica estados o duraciones.
- El control por roles no siempre es consistente en procesos no digitalizados.

### Alcance
La solucion cubre autenticacion, registro de citas, consulta por vistas (`list`, `day`, `month`), cambio de estado, extension de duracion y consulta de auditoria.  
Incluye backend, frontend y scripts de base de datos para despliegue local de desarrollo.

---

## 5) MAPA DE PROCESO (DATOS DE ENTRADA, PROCESOS Y SALIDAS)

### Entradas
- Datos de autenticacion (correo, contrasena).
- Datos de cita (material, fecha/hora, duracion, proveedor).
- Acciones de gestion (cambio de estado, extension).

### Procesos
- Validacion de credenciales y emision/renovacion de tokens.
- Validacion de reglas de negocio para cita.
- Persistencia en PostgreSQL y registro en historial de cambios.
- Exposicion de informacion al frontend por endpoints REST.

### Salidas
- Confirmacion o rechazo de operaciones.
- Listados y vistas de citas por rango temporal.
- Bitacora de auditoria para administracion.

---

## 6) MAPA DE CASO DE USO (RESUMEN FUNCIONAL)

### Actor: Proveedor
- Registrarse e iniciar sesion.
- Crear cita de entrega.
- Consultar sus citas.

### Actor: Logistica
- Consultar citas programadas.
- Actualizar estado de cita.
- Extender duracion si no hay conflicto.

### Actor: Administrador
- Gestionar/consultar operaciones criticas.
- Revisar historial de cambios en auditoria.
- Realizar trazabilidad completa de citas (trazos y seguimiento de cambios).
- Editar y modificar citas cuando el proceso operativo lo requiera.
- Crear perfiles de usuario para roles de administrador y logistica.

---

## 7) ARBOL DE OBJETIVOS

### Objetivo central
Optimizar la gestion de citas de entrega en Ferragro con control, seguridad y trazabilidad.

### Medios
- Digitalizar el flujo de citas.
- Aplicar reglas de validacion automaticas.
- Implementar autenticacion robusta y autorizacion por rol.
- Mantener historial de cambios auditable.

### Fines
- Reducir reprocesos y conflictos de horario.
- Mejorar la coordinacion entre proveedores y personal interno.
- Incrementar confiabilidad operativa y capacidad de supervision.

---

## 8) ARBOL DE PROBLEMAS

### Problema central
Ineficiencia en la programacion y seguimiento de entregas.

### Causas
- Gestion manual y descentralizada.
- Falta de control de permisos por tipo de usuario.
- Ausencia de bitacora estructurada de cambios.

### Efectos
- Demoras operativas.
- Errores de coordinacion.
- Dificultad para auditar decisiones y acciones.

---

## 9) DISENO FUNCIONAL DE LA APLICACION

- **Frontend:** React + Vite, contexto de autenticacion y componentes para formulario/listado de citas.
- **Backend:** FastAPI, modulos de autenticacion, citas y administracion.
- **Persistencia:** PostgreSQL con esquema, triggers y funciones CRUD complementarias.
- **Seguridad:** Access token en cliente, refresh token en cookie HttpOnly, rutas protegidas por rol.

---

## 10) MODELO DE DATOS (MR/MER)

Entidades principales:

- `Credenciales`
- `Usuarios`
- `Proveedores`
- `Citas`
- `HistorialCambios`

Relaciones clave:

- `Usuarios` y `Proveedores` referencian `Credenciales`.
- `Citas` se relaciona con el proveedor que agenda.
- `HistorialCambios` registra acciones sobre citas y otros eventos administrativos.

---

## 11) PREMOLDEADO DE LA BASE DE DATOS

Base de datos PostgreSQL con scripts en `db/`:

- `001_schema.sql`
- `002_audit_triggers.sql`
- `003_historial_id_actor_drop_fk.sql`
- script de orquestacion `run-database-all.ps1`

Este premoldeado define estructura, reglas de auditoria y soporte para operaciones CRUD.

---

## 12) CONSULTAS DE PRUEBA Y VALIDACIONES DE SEGURIDAD

### Pruebas funcionales
- Insercion y consulta de citas.
- Cambios de estado y extension de duracion.
- Consulta de historial de cambios.

### Validaciones de seguridad
- Uso de JWT para autorizacion en rutas protegidas.
- Rotacion de refresh token mediante cookie HttpOnly.
- Recomendacion de HTTPS y cookie segura en produccion.

---

## 13) OBJETIVO GENERAL

Implementar un sistema web integral para la gestion de citas de entrega en Ferragro, que mejore el control logístico, reduzca conflictos de horario y garantice trazabilidad de cambios.

---

## 14) OBJETIVOS ESPECIFICOS

1. Diseñar un flujo de autenticacion seguro para diferentes roles.
2. Permitir el agendamiento de citas con reglas de validacion de negocio.
3. Facilitar la administracion y seguimiento de estados de cita.
4. Registrar auditoria de cambios para supervision administrativa.
5. Integrar frontend y backend con un contrato API consistente.

---

## 15) TECNICAS DE RECOLECCION DE DATOS

- Levantamiento de requerimientos con actores del proceso (proveedor, logistica, administrador).
- Analisis de flujo actual de entregas y puntos de fallo.
- Pruebas iterativas del sistema en ambiente local.
- Retroalimentacion de usuarios internos para ajustar reglas de negocio.

---

## 16) CONCLUSIONES

- La centralizacion de citas reduce errores por solapamiento y mejora la coordinacion.
- El control por roles mejora la seguridad y la responsabilidad operativa.
- La auditoria aporta trazabilidad para seguimiento y mejora continua.
- La arquitectura actual permite escalar nuevas funcionalidades del proceso logistico.

---

## 17) GLOSARIO

- **JWT:** token firmado para autenticacion/autorizacion.
- **Refresh token:** token de larga duracion para renovar sesiones.
- **CRUD:** operaciones crear, leer, actualizar y eliminar.
- **API REST:** interfaz para comunicacion entre frontend y backend.
- **Auditoria:** registro historico de acciones realizadas en el sistema.

