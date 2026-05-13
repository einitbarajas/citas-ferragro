export function unwrapProviderDayAvailability(response) {
  const payload = response?.data;
  if (!payload || typeof payload !== "object") {
    throw new Error("Respuesta inválida del servidor");
  }

  const candidates = [];
  if (payload.data && typeof payload.data === "object" && !Array.isArray(payload.data)) {
    candidates.push(payload.data);
    if (
      payload.data.data &&
      typeof payload.data.data === "object" &&
      !Array.isArray(payload.data.data)
    ) {
      candidates.push(payload.data.data);
    }
  }
  candidates.push(payload);

  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) continue;
    if (
      Array.isArray(candidate.available_times) ||
      typeof candidate.unavailable_reason === "string" ||
      candidate.slot_minutes != null
    ) {
      return candidate;
    }
  }

  if (payload.success === false) {
    throw new Error(payload.message || "No se pudo cargar la disponibilidad.");
  }
  throw new Error("No se pudo cargar la disponibilidad.");
}

export function describeProviderSlotAvailability({
  loading,
  loadError,
  hasExistingAppointment,
  reason,
  message,
  minimumNoticeHours,
  selectedDayOpen,
}) {
  if (loading) {
    return {
      optionLabel: "Consultando disponibilidad...",
      title: "",
      detail: "",
      tone: "info",
    };
  }
  if (loadError) {
    return {
      optionLabel: "No se pudo consultar",
      title: "No se pudo consultar la disponibilidad",
      detail: loadError,
      tone: "error",
    };
  }
  if (hasExistingAppointment || reason === "provider_has_appointment") {
    return {
      optionLabel: "Ya tienes cita este día",
      title: "Ya tienes una cita este día",
      detail:
        message ||
        "Solo se permite una cita por día. Elige otro día en el calendario.",
      tone: "warning",
    };
  }
  if (reason === "minimum_notice") {
    const hours = Number(minimumNoticeHours) || 24;
    return {
      optionLabel: `Anticipación mínima de ${hours} horas`,
      title: "No puedes agendar por anticipación",
      detail:
        message ||
        `Debes solicitar la cita con al menos ${hours} horas de anticipación. Para esta fecha ya no queda ningún horario válido; elige otro día u horario más adelante.`,
      tone: "warning",
    };
  }
  if (reason === "fully_booked") {
    return {
      optionLabel: "Disponibilidad llena",
      title: "Disponibilidad llena",
      detail:
        message ||
        "La empresa abrió franja este día, pero todos los horarios ya fueron tomados. Busca otro día en el calendario.",
      tone: "warning",
    };
  }
  if (reason === "no_windows") {
    return {
      optionLabel: "Franja cerrada",
      title: "Día sin franja habilitada",
      detail:
        message ||
        "La empresa no abrió horarios de cita para esta fecha. Elige un día marcado en verde claro.",
      tone: "warning",
    };
  }
  if (reason === "no_valid_slots") {
    return {
      optionLabel: "Sin horarios en la franja",
      title: "Sin horarios válidos",
      detail:
        message ||
        "Hay franja publicada, pero no se generaron horarios válidos para este día. Elige otro día.",
      tone: "warning",
    };
  }
  if (selectedDayOpen) {
    const hours = Number(minimumNoticeHours) || 24;
    return {
      optionLabel: `Anticipación mínima de ${hours} horas`,
      title: "Sin horarios disponibles ahora",
      detail: `La empresa abrió este día, pero ningún horario está disponible en este momento. Suele deberse a la anticipación mínima de ${hours} horas o a que ya no quedan cupos. Elige otro día.`,
      tone: "warning",
    };
  }
  return {
    optionLabel: "Sin horarios para agendar",
    title: "Sin horarios para agendar",
    detail:
      message ||
      "No hay horarios disponibles para esta fecha. Elige otro día en el calendario.",
    tone: "warning",
  };
}
