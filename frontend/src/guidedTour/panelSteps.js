/**
 * Pasos del manual guiado del panel (`GuidedTourDialog`).
 * Opcionales por paso: `subtitle`, `bullets` (lista corta), `tip`, `ahora` (el diálogo también infiere ayudas según el título).
 * `moduleTarget`: cambia pestaña y resalta el ítem del menú.
 * `sidebarMobile`: en viewport estrecho (menos de lg), abre o cierra el drawer del menú.
 * `scrollMainTop`: desplaza el área principal arriba al explicar el contenido.
 */

const adminSteps = [
  {
    title: "Inicio del manual (Admin)",
    subtitle: "Tranquilo: es solo lectura",
    description: "Te explicamos el menú y el panel central sin cambiar datos por ti.",
    bullets: [
      "Puedes cerrar cuando quieras (X o fuera de la ventana).",
      "Vuelve aquí con el botón «Manual guiado» del panel cuando lo necesites.",
    ],
    sidebarMobile: "close",
  },
  {
    title: "Cómo usar el menú",
    subtitle: "Tres ideas nada más",
    description: "Así se usa el panel en el día a día.",
    bullets: [
      "Primero eliges el módulo en la columna izquierda (en el móvil: botón «Menú»).",
      "Después trabajas en el centro: formularios, tablas, filtros.",
      "Para cambiar de tema, otra vez al menú y eliges otra sección.",
    ],
    sidebarMobile: "open",
  },
  {
    title: "Centro de notificaciones",
    subtitle: "Campana arriba a la derecha",
    description: "Avisos en el panel y copia por correo cuando una cita requiere atención del equipo.",
    bullets: [
      "El número ámbar indica no leídas; se actualiza al abrir la bandeja.",
      "Te avisa de citas nuevas o cambiadas pendientes de revisión.",
      "Pulsa un aviso para ir a Revisión de citas; «Marcar todas leídas» limpia la bandeja.",
    ],
    sidebarMobile: "close",
    ahora: "Mira arriba a la derecha del panel central: icono de campana junto a «Manual guiado».",
  },
  { title: "Marca del panel", description: "Cabecera del menú: logotipo FERRAGRO y tipo de panel (administrador).", sidebarMobile: "open" },
  { title: "Sección del menú: Principal", description: "Agrupa Citas, Buscar citas y Revisión de citas: el flujo diario de operación.", sidebarMobile: "open" },
  { title: "Ítem: Citas", description: "Botón del menú que abre el módulo Citas (resumen e indicadores).", moduleTarget: "citas", sidebarMobile: "open" },
  { title: "Contenido: Citas", description: "Aquí ves resumen operativo e indicadores rápidos del módulo Citas.", moduleTarget: "citas", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Ítem: Buscar citas", description: "Botón del menú para buscar y filtrar citas por rango.", moduleTarget: "buscar_citas", sidebarMobile: "open" },
  { title: "Contenido: Buscar citas", description: "En esta vista filtras por rango y revisas detalle de citas.", moduleTarget: "buscar_citas", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Ítem: Revisión de citas", description: "Botón del menú para gestionar estados de citas.", moduleTarget: "revision_citas", sidebarMobile: "open" },
  { title: "Contenido: Revisión de citas", description: "Aquí cambias estado (revisada/finalizada/no presentada/cancelada).", moduleTarget: "revision_citas", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Sección del menú: Informes", description: "Agrupa la analítica: métricas y lectura de desempeño.", sidebarMobile: "open" },
  { title: "Ítem: Analítica", description: "Botón del menú para métricas y gráficos.", moduleTarget: "analitica", sidebarMobile: "open" },
  { title: "Contenido: Analítica", description: "Aquí interpretas indicadores para decisiones operativas.", moduleTarget: "analitica", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Sección del menú: Operación", description: "Configuración de franjas horarias en las que se permite agendar.", sidebarMobile: "open" },
  { title: "Ítem: Franjas horarias", description: "Botón del menú para ventanas de agendamiento.", moduleTarget: "horarios", sidebarMobile: "open" },
  { title: "Contenido: Franjas horarias", description: "Aquí defines cuándo se permite agendar citas.", moduleTarget: "horarios", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Sección del menú: Administración", description: "Equipo interno, auditoría de cambios y ajustes de tu cuenta.", sidebarMobile: "open" },
  { title: "Ítem: Equipo (Admin / Logística)", description: "Botón del menú para usuarios internos y roles.", moduleTarget: "equipo", sidebarMobile: "open" },
  { title: "Contenido: Equipo", description: "Aquí creas, editas y gestionas roles de Admin/Logística.", moduleTarget: "equipo", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Ítem: Auditoría", description: "Botón del menú para trazabilidad de cambios.", moduleTarget: "auditoria", sidebarMobile: "open" },
  { title: "Contenido: Auditoría", description: "Aquí revisas quién cambió qué, cuándo y sobre qué cita.", moduleTarget: "auditoria", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Ítem: Configuraciones", description: "Botón del menú para ajustes de cuenta.", moduleTarget: "configuraciones", sidebarMobile: "open" },
  { title: "Contenido: Configuraciones", description: "Aquí actualizas contraseña, perfil y foto.", moduleTarget: "configuraciones", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Pie del menú: tu perfil", description: "Nombre visible, rol y foto; se usa en auditoría y comunicación interna.", sidebarMobile: "open" },
  { title: "Pie del menú: Cerrar sesión", description: "Salida segura del panel. Vuelve a iniciar sesión cuando lo necesites.", sidebarMobile: "open" },
];

const logisticaSteps = [
  {
    title: "Inicio del manual (Logística)",
    subtitle: "Sin apuros",
    description: "Recorrido por los módulos que usas cada día en operación.",
    bullets: ["Nada se guarda solo por leer esta guía.", "Cierra con la X o tocando fuera si necesitas ver la pantalla."],
    sidebarMobile: "close",
  },
  {
    title: "Área de navegación",
    subtitle: "La lista de la izquierda",
    description: "Ahí saltas entre citas, búsqueda, revisión, historial y ajustes.",
    bullets: ["En el móvil, abre primero el botón «Menú».", "Cada fila abre una vista distinta al centro."],
    sidebarMobile: "open",
  },
  {
    title: "Centro de notificaciones",
    subtitle: "Campana arriba a la derecha",
    description: "Avisos en el panel y copia por correo cuando una cita entra o vuelve a revisión.",
    bullets: [
      "El número ámbar indica no leídas; se actualiza al abrir la bandeja.",
      "Te avisa de citas nuevas o cambiadas que debes revisar en operación.",
      "Pulsa un aviso para ir a Revisión de citas; «Marcar todas leídas» limpia la bandeja.",
    ],
    sidebarMobile: "close",
    ahora: "Mira arriba a la derecha del panel central: icono de campana junto a «Manual guiado».",
  },
  { title: "Marca del panel", description: "Cabecera del menú: logotipo FERRAGRO y panel de logística.", sidebarMobile: "open" },
  { title: "Sección del menú: Principal", description: "Agrupa las acciones diarias: citas, búsqueda, revisión, historial y configuración.", sidebarMobile: "open" },
  { title: "Ítem: Citas", description: "Botón del menú para el resumen operativo del periodo.", moduleTarget: "citas", sidebarMobile: "open" },
  { title: "Contenido: Citas", description: "Resumen operativo del periodo actual.", moduleTarget: "citas", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Ítem: Buscar citas", description: "Botón del menú para consultas y filtros.", moduleTarget: "buscar_citas", sidebarMobile: "open" },
  { title: "Contenido: Buscar citas", description: "Aquí filtras y ubicas citas exactas.", moduleTarget: "buscar_citas", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Ítem: Revisión de citas", description: "Botón del menú para gestionar estados de citas.", moduleTarget: "revision_citas", sidebarMobile: "open" },
  { title: "Contenido: Revisión de citas", description: "Aquí aplicas revisión, finalización o no presentada.", moduleTarget: "revision_citas", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Ítem: Historial", description: "Botón del menú para trazabilidad histórica.", moduleTarget: "historial", sidebarMobile: "open" },
  { title: "Contenido: Historial", description: "Revisión de registros y acciones históricas.", moduleTarget: "historial", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Ítem: Configuraciones", description: "Botón del menú para ajustes de cuenta.", moduleTarget: "configuraciones", sidebarMobile: "open" },
  { title: "Contenido: Configuraciones", description: "Ajustes de perfil y contraseña logística.", moduleTarget: "configuraciones", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Pie del menú: tu perfil", description: "Nombre, rol y foto asociados a tu sesión de logística.", sidebarMobile: "open" },
  { title: "Pie del menú: Cerrar sesión", description: "Salida segura del panel.", sidebarMobile: "open" },
];

const proveedorSteps = [
  {
    title: "Inicio del manual (Proveedor)",
    subtitle: "Pasos cortos",
    description: "Te mostramos dónde ver tus citas, historial y datos de cuenta.",
    bullets: ["La guía no envía ni borra información.", "Puedes cerrarla en cualquier momento."],
    sidebarMobile: "close",
  },
  {
    title: "Área de navegación",
    subtitle: "Menú simple",
    description: "Desde aquí vas a Inicio, Mis citas, Historial y Configuraciones.",
    bullets: ["En el celular, usa el botón «Menú» arriba para ver la lista.", "El centro de la pantalla muestra el detalle de cada opción."],
    sidebarMobile: "open",
  },
  {
    title: "Centro de notificaciones",
    subtitle: "Campana arriba a la derecha",
    description: "Avisos en el panel y copia por correo cuando admin o logística actualizan una cita tuya.",
    bullets: [
      "El número ámbar indica no leídas; se actualiza al abrir la bandeja.",
      "Te avisa de cambios de fecha, hora o datos en citas vigentes.",
      "Pulsa un aviso para ir a Mis citas; «Marcar todas leídas» limpia la bandeja.",
    ],
    sidebarMobile: "close",
    ahora: "Mira arriba a la derecha del panel central: icono de campana junto a «Manual guiado».",
  },
  { title: "Marca del panel", description: "Cabecera del menú: logotipo FERRAGRO y panel de proveedor.", sidebarMobile: "open" },
  { title: "Sección del menú: Principal", description: "Accesos a inicio, citas vigentes, historial y configuración de cuenta.", sidebarMobile: "open" },
  { title: "Ítem: Inicio", description: "Botón del menú para el panel principal del proveedor.", moduleTarget: "inicio", sidebarMobile: "open" },
  { title: "Contenido: Inicio", description: "Estado general y disponibilidad.", moduleTarget: "inicio", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Ítem: Ver mis citas", description: "Botón del menú para consultar citas vigentes.", moduleTarget: "mis_citas", sidebarMobile: "open" },
  { title: "Contenido: Mis citas", description: "Aquí ves fecha, hora y estado de tus citas activas.", moduleTarget: "mis_citas", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Ítem: Historial", description: "Botón del menú para revisar citas cerradas.", moduleTarget: "historial", sidebarMobile: "open" },
  { title: "Contenido: Historial", description: "Citas finalizadas, canceladas o no presentadas.", moduleTarget: "historial", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Ítem: Configuraciones", description: "Botón del menú para ajustes de cuenta.", moduleTarget: "configuraciones", sidebarMobile: "open" },
  { title: "Contenido: Configuraciones", description: "Cambio de contraseña, foto y datos de perfil.", moduleTarget: "configuraciones", scrollMainTop: true, sidebarMobile: "close" },
  { title: "Pie del menú: tu perfil", description: "Nombre, rol y foto de tu cuenta proveedor.", sidebarMobile: "open" },
  { title: "Pie del menú: Cerrar sesión", description: "Salida segura del panel.", sidebarMobile: "open" },
];

import { ADMIN_PANEL_TARGETS, LOGISTICA_PANEL_TARGETS, PROVEEDOR_PANEL_TARGETS } from "./panelTargets";

export function getPanelGuidedSteps(isAdmin, isLogistica, isProveedor) {
  const steps = isAdmin ? adminSteps : isLogistica ? logisticaSteps : proveedorSteps;
  const targets = isAdmin ? ADMIN_PANEL_TARGETS : isLogistica ? LOGISTICA_PANEL_TARGETS : PROVEEDOR_PANEL_TARGETS;
  return steps.map((s, i) => ({ ...s, targetSelector: targets[i] || null }));
}
