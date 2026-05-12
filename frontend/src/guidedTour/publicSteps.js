const landingSteps = [
  {
    selector: '[data-tour="landing-manual-btn"]',
    title: "Manual paso a paso",
    subtitle: "Primero lo más importante",
    description: "Esta ventana te guía por la página sin tocar tus datos.",
    bullets: [
      "Puedes cerrarla cuando quieras (X o tocando fuera).",
      "Si te pierdes, vuelve al botón Manual de la página.",
    ],
    tip: "Nada de lo que leas aquí se guarda en el servidor por solo abrir la guía.",
  },
  {
    selector: '[data-tour="landing-login-btn"]',
    title: "Entrar si ya tienes cuenta",
    subtitle: "Solo si ya estás registrado",
    description: "Usa Iniciar sesión cuando la empresa ya te dio de alta y tienes correo y contraseña.",
    bullets: ["Después de pulsar, escribirás correo y clave en el formulario.", "Si aún no tienes cuenta, no uses este botón: usa Registrarme."],
  },
  {
    selector: '[data-tour="landing-register-btn"]',
    title: "Crear cuenta nueva",
    subtitle: "Primera vez en el portal",
    description: "Registrarme es solo para empresas o responsables que aún no tienen usuario.",
    bullets: ["Te pedirán datos de empresa y del responsable.", "Lee con calma cada campo antes de enviar."],
  },
  {
    selector: '[data-tour="landing-intro"]',
    title: "Qué hace esta página",
    description: "Aquí entiendes en qué consiste el portal antes de entrar.",
    bullets: ["Citas de entrega y franjas horarias.", "Notificaciones e historial según tu rol."],
  },
  {
    selector: '[data-tour="landing-modules"]',
    title: "Funciones principales",
    description: "Las tarjetas resumen lo que podrás hacer dentro del panel.",
    bullets: ["Son un mapa rápido: no hace falta memorizarlo todo.", "El detalle lo verás cuando inicies sesión."],
  },
  {
    selector: '[data-tour="landing-contact"]',
    title: "Soporte humano",
    description: "Si algo falla (acceso, correo, contraseña), escribe o llama por estos canales.",
    bullets: ["WhatsApp y correo de soporte están en la página.", "Ten a mano tu correo de registro y el nombre de la empresa."],
  },
];

const loginSteps = [
  {
    selector: '[data-tour="login-manual-btn"]',
    title: "Guía de acceso",
    subtitle: "Te decimos dónde hacer clic",
    description: "Vamos paso a paso por el formulario para que no te falte ningún dato.",
    bullets: ["Sigue el orden de los pasos: es el mismo orden del formulario.", "Puedes volver atrás con el botón Paso anterior."],
  },
  {
    selector: '[data-tour="login-tabs"]',
    title: "Paso 1: elegir modo",
    description: "Arriba del formulario eliges si entras o si te registras.",
    bullets: ["Iniciar sesión = ya tengo usuario y contraseña.", "Registrarme = primera vez, crear empresa/usuario."],
    tip: "Si pulsas el modo equivocado, cambia de pestaña antes de escribir mucho.",
  },
  {
    selector: '[data-tour="register-nit"]',
    title: "Registro: NIT",
    description: "Solo si estás en Registrarme.",
    bullets: ["10 dígitos, sin puntos ni guiones.", "Debe coincidir con el NIT real de la empresa."],
  },
  {
    selector: '[data-tour="register-company"]',
    title: "Registro: empresa",
    description: "Nombre tal como sale en cámara de comercio o factura.",
    bullets: ["Evita abreviaturas raras que luego no reconozcan otros usuarios."],
  },
  {
    selector: '[data-tour="register-privacy"]',
    title: "Registro: política de datos",
    description: "Es obligatorio para cumplir la Ley 1581 de protección de datos.",
    bullets: ["Léela con calma y marca aceptar solo si estás de acuerdo."],
  },
  {
    selector: '[data-tour="login-email"]',
    title: "Paso 2: escribir correo",
    description: "El correo es tu usuario para volver a entrar.",
    bullets: ["Formato típico: nombre@empresa.com.", "Sin espacios al inicio ni al final."],
    tip: "Si el sistema dice que no existe, revisa mayúsculas y el dominio (@…).",
  },
  {
    selector: '[data-tour="login-password"]',
    title: "Paso 3: contraseña",
    description: "Escribe la clave que te dieron o la que configuraste.",
    bullets: ["El ícono del ojo suele mostrar u ocultar la contraseña.", "Bloqueo temporal: espera el tiempo que indique el mensaje y reintenta."],
  },
  {
    selector: '[data-tour="login-forgot-password"]',
    title: "Si olvidaste la clave",
    description: "Recibirás una contraseña temporal por correo.",
    bullets: ["Revisa también la carpeta de spam.", "Al entrar, cambia la clave temporal por una definitiva."],
  },
  {
    selector: '[data-tour="login-submit"]',
    title: "Paso 4: entrar",
    subtitle: "Último clic en esta pantalla",
    description: "Continuar envía correo y contraseña al servidor.",
    bullets: ["Si los datos son correctos, entras al panel según tu rol.", "Si hay error, lee el mensaje en rojo: suele decir qué corregir."],
    tip: "No cierres la ventana mientras carga: a veces tarda unos segundos.",
  },
];

/**
 * @param {"landing" | "login" | "register"} view
 */
export function getPublicGuidedStepDefinitions(view) {
  return view === "landing" ? landingSteps : loginSteps;
}

export function filterAndStripPublicSteps(view) {
  const raw = getPublicGuidedStepDefinitions(view);
  return raw
    .filter((s) => !s.selector || document.querySelector(s.selector))
    .map(({ title, description, bullets, subtitle, tip, ahora, selector }) => ({
      title,
      description,
      targetSelector: selector || null,
      ...(Array.isArray(bullets) && bullets.length ? { bullets } : {}),
      ...(subtitle ? { subtitle } : {}),
      ...(tip ? { tip } : {}),
      ...(ahora ? { ahora } : {}),
    }));
}
