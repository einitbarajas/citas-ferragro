const PANEL_TOUR_LG_PX = 1024;

export const TOUR_DASHBOARD_SIDEBAR_SELECTOR = '[data-tour="dashboard-sidebar"]';

export function isNarrowPanelTourViewport() {
  return typeof window !== "undefined" && window.innerWidth < PANEL_TOUR_LG_PX;
}

export function manualTourBootDelayMs() {
  return isNarrowPanelTourViewport() ? 64 : 160;
}

/** `data-tour` del botón de menú asociado a cada `moduleTarget` del panel. */
export const MODULE_TO_NAV_TOUR_ID = {
  inicio: "nav-inicio",
  mis_citas: "nav-mis_citas",
  historial: "nav-historial",
  configuraciones: "nav-configuraciones",
  citas: "nav-citas",
  buscar_citas: "nav-buscar_citas",
  revision_citas: "nav-revision_citas",
  analitica: "nav-analitica",
  horarios: "nav-horarios",
  equipo: "nav-equipo",
  auditoria: "nav-auditoria",
};

export function scrollDashboardSidebarNavItemIntoView(navEl, itemEl) {
  if (!navEl || !itemEl) return;
  const pad = 10;
  const navRect = navEl.getBoundingClientRect();
  const itemRect = itemEl.getBoundingClientRect();
  if (itemRect.top >= navRect.top + pad && itemRect.bottom <= navRect.bottom - pad) return;
  const targetTop =
    navEl.scrollTop +
    (itemRect.top - navRect.top) -
    (navRect.height / 2 - itemRect.height / 2);
  navEl.scrollTo({ top: Math.max(0, targetTop), behavior: "auto" });
}
