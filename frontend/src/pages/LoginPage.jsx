import { useEffect, useId, useMemo, useRef, useState } from "react";
import api, { API_PREFIX, getRetryAfterSeconds, parseApiError, parseApiResponse } from "../api/client";
import { useAuth } from "../context/AuthContext";
import BrandLogo from "../components/BrandLogo";
import PasswordVisibilityButton from "../components/PasswordVisibilityButton";
import ThemeToggle from "../components/ThemeToggle";

export default function LoginPage({ initialMode = "login", onBack, showInfoPanel = true, onStartTour } = {}) {
  const modalRef = useRef(null);
  const modalCloseRef = useRef(null);
  const lawTriggerRef = useRef(null);
  const formIdPrefix = useId();
  const { login } = useAuth();
  const [isRegister, setIsRegister] = useState(initialMode === "register");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmittingForgot, setIsSubmittingForgot] = useState(false);
  const [retryAfterSeconds, setRetryAfterSeconds] = useState(0);
  const [forgotCooldownSeconds, setForgotCooldownSeconds] = useState(0);
  const [forgotRequested, setForgotRequested] = useState(false);
  const [mustChangePassword, setMustChangePassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [pendingAccessToken, setPendingAccessToken] = useState("");
  const [pendingRole, setPendingRole] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [acceptedLaw1581, setAcceptedLaw1581] = useState(false);
  const [showLawModal, setShowLawModal] = useState(false);
  const fieldInputClass =
    "w-full rounded-lg border border-slate-400 bg-white px-3 py-2.5 text-slate-900 placeholder:text-slate-500 transition focus:border-[#35783C] focus:outline-none focus:ring-2 focus:ring-[#35783C]/30";
  const fieldClass = `mt-1 ${fieldInputClass}`;
  const errorId = `${formIdPrefix}-form-error`;
  const modalTitleId = `${formIdPrefix}-law-title`;
  const modalDescId = `${formIdPrefix}-law-description`;

  const [form, setForm] = useState({
    nit: "",
    digito_verificacion: "",
    nombre_empresa: "",
    correo_empresa: "",
    nombre_persona_responsable: "",
    documento_persona_responsable: "",
    password: "",
  });

  const onChange = (e) => {
    const { name, value } = e.target;
    if (name === "nit") {
      const onlyDigits = value.replace(/\D/g, "").slice(0, 10);
      setForm((p) => ({ ...p, nit: onlyDigits }));
      return;
    }
    if (name === "digito_verificacion") {
      const onlyDigits = value.replace(/\D/g, "").slice(0, 1);
      setForm((p) => ({ ...p, digito_verificacion: onlyDigits }));
      return;
    }
    if (name === "documento_persona_responsable") {
      const onlyDigits = value.replace(/\D/g, "").slice(0, 10);
      setForm((p) => ({ ...p, documento_persona_responsable: onlyDigits }));
      return;
    }
    setForm((p) => ({ ...p, [name]: value }));
  };
  const togglePasswordVisibility = (setter) => (e) => {
    e.preventDefault();
    setter((v) => !v);
  };
  const passwordChecks = [
    { label: "Mínimo 8 caracteres", valid: form.password.length >= 8 },
    { label: "Al menos una letra mayúscula", valid: /[A-Z]/.test(form.password) },
    { label: "Al menos una letra minúscula", valid: /[a-z]/.test(form.password) },
    { label: "Al menos un número", valid: /\d/.test(form.password) },
    { label: "Al menos un carácter especial (!@#$...)", valid: /[^A-Za-z0-9]/.test(form.password) },
  ];
  const isStrongPassword = passwordChecks.every((rule) => rule.valid);
  const passwordScore = passwordChecks.filter((rule) => rule.valid).length;
  const passwordStrength = useMemo(() => {
    if (passwordScore <= 2) return { label: "Baja", icon: "⚠", className: "text-rose-700", bg: "bg-rose-50 border-rose-300" };
    if (passwordScore <= 4) return { label: "Media", icon: "●", className: "text-amber-700", bg: "bg-amber-50 border-amber-300" };
    return { label: "Alta", icon: "✓", className: "text-[#35783C]", bg: "bg-emerald-50 border-emerald-300" };
  }, [passwordScore]);

  useEffect(() => {
    if (retryAfterSeconds <= 0) return undefined;
    const timer = window.setInterval(() => {
      setRetryAfterSeconds((prev) => (prev > 1 ? prev - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [retryAfterSeconds]);

  useEffect(() => {
    if (forgotCooldownSeconds <= 0) return undefined;
    const timer = window.setInterval(() => {
      setForgotCooldownSeconds((prev) => (prev > 1 ? prev - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [forgotCooldownSeconds]);

  const waitLabel = useMemo(() => {
    if (retryAfterSeconds <= 0) return "";
    const minutes = Math.floor(retryAfterSeconds / 60);
    const seconds = retryAfterSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }, [retryAfterSeconds]);

  const forgotWaitLabel = useMemo(() => {
    if (forgotCooldownSeconds <= 0) return "";
    const minutes = Math.floor(forgotCooldownSeconds / 60);
    const seconds = forgotCooldownSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }, [forgotCooldownSeconds]);

  useEffect(() => {
    if (!showLawModal) return undefined;
    const previous = document.activeElement;
    const modalNode = modalRef.current;
    const focusable = () =>
      modalNode?.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      ) || [];
    modalCloseRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setShowLawModal(false);
        return;
      }
      if (event.key !== "Tab") return;
      const elements = Array.from(focusable());
      if (elements.length === 0) return;
      const first = elements[0];
      const last = elements[elements.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (previous && typeof previous.focus === "function") previous.focus();
      else lawTriggerRef.current?.focus();
    };
  }, [showLawModal]);

  const submit = async (e) => {
    e.preventDefault();
    if (isSubmitting || retryAfterSeconds > 0) return;
    setError("");
    setIsSubmitting(true);
    try {
      if (isRegister) {
        if (!acceptedLaw1581) {
          throw new Error("Debes aceptar la autorización de tratamiento de datos (Ley 1581 de 2012) para registrarte.");
        }
        if (!/^\d{10}$/.test(form.nit)) {
          throw new Error("El NIT debe tener exactamente 10 dígitos numéricos.");
        }
        if (!/^\d$/.test(form.digito_verificacion)) {
          throw new Error("El dígito de verificación (DV) debe tener exactamente 1 dígito numérico.");
        }
        if (!/^\d{7,10}$/.test(form.documento_persona_responsable)) {
          throw new Error(
            "El documento de la persona responsable debe tener solo números y entre 7 y 10 dígitos (se aceptan cédulas antiguas con menos de 10 dígitos)."
          );
        }
        if (!isStrongPassword) {
          throw new Error("La contraseña no cumple con los criterios mínimos de seguridad.");
        }
        if (form.password !== confirmPassword) {
          throw new Error("Las contraseñas no coinciden.");
        }
        const registerResponse = await api.post(`${API_PREFIX}/auth/register`, {
          document_id: form.nit,
          email: form.correo_empresa,
          full_name: form.nombre_empresa,
          password: form.password,
          role_name: "Proveedor",
          digito_verificacion: form.digito_verificacion,
          nombre_persona_responsable: form.nombre_persona_responsable,
          documento_persona_responsable: form.documento_persona_responsable,
        });
        const registerPayload = parseApiResponse(registerResponse);
        if (!registerPayload.success) {
          throw new Error(registerPayload.message);
        }
      }
      const loginResponse = await api.post(`${API_PREFIX}/auth/login`, { email: form.correo_empresa, password: form.password });
      const loginPayload = parseApiResponse(loginResponse);
      if (!loginPayload.success) {
        throw new Error(loginPayload.message);
      }
      if (loginPayload?.data?.must_change_password) {
        setMustChangePassword(true);
        setPendingAccessToken(loginPayload.data.access_token || "");
        setPendingRole(loginPayload.data.role || "");
        setError("Debes actualizar tu contraseña temporal antes de continuar.");
        return;
      }
      login({
        token: loginPayload.data.access_token,
        role: loginPayload.data.role,
        email: form.correo_empresa?.trim() || undefined,
      });
    } catch (err) {
      const waitSeconds = getRetryAfterSeconds(err);
      if (err?.response?.status === 429 && waitSeconds > 0) {
        setRetryAfterSeconds(waitSeconds);
        setError(`Demasiados intentos. Espera ${Math.ceil(waitSeconds / 60)} minuto(s) antes de intentar de nuevo.`);
      } else {
        setError(parseApiError(err) || err.message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitForgotPassword = async () => {
    const email = String(form.correo_empresa || "").trim();
    if (isSubmittingForgot || forgotCooldownSeconds > 0) return;
    if (!email) {
      setError("Ingresa tu correo para recuperar la contraseña.");
      return;
    }
    setError("");
    setForgotRequested(false);
    setIsSubmittingForgot(true);
    try {
      const response = await api.post(`${API_PREFIX}/auth/forgot-password`, { email });
      const payload = parseApiResponse(response);
      if (!payload.success) throw new Error(payload.message);
      setForgotRequested(true);
      setForgotCooldownSeconds(60);
    } catch (err) {
      const waitSeconds = getRetryAfterSeconds(err);
      if (err?.response?.status === 429 && waitSeconds > 0) {
        setForgotCooldownSeconds(waitSeconds);
        setError(`Ya solicitaste una contraseña temporal. Espera ${waitSeconds} segundos para volver a intentar.`);
      } else {
        setError(parseApiError(err));
      }
    } finally {
      setIsSubmittingForgot(false);
    }
  };

  const submitChangePassword = async (e) => {
    e.preventDefault();
    if (!pendingAccessToken) {
      setError("No hay sesión temporal activa. Inicia sesión de nuevo.");
      return;
    }
    if (newPassword.length < 8) {
      setError("La nueva contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (newPassword !== newPasswordConfirm) {
      setError("Las contraseñas nuevas no coinciden.");
      return;
    }
    setError("");
    setIsSubmitting(true);
    try {
      const response = await api.post(
        `${API_PREFIX}/auth/change-password`,
        { current_password: form.password, new_password: newPassword },
        { headers: { Authorization: `Bearer ${pendingAccessToken}` } }
      );
      const payload = parseApiResponse(response);
      if (!payload.success) throw new Error(payload.message);
      login({
        token: pendingAccessToken,
        role: pendingRole || "Proveedor",
        email: form.correo_empresa?.trim() || undefined,
      });
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-emerald-50 px-4 py-10">
      <div className={`mx-auto grid w-full min-w-0 items-stretch gap-6 ${showInfoPanel ? "max-w-5xl lg:grid-cols-2" : "max-w-xl"}`}>
        {showInfoPanel && <div className="rounded-2xl border border-emerald-100 bg-white/70 p-7 shadow-lg backdrop-blur">
          <div className="mb-5">
            <BrandLogo className="h-20 w-auto max-w-full sm:h-28 md:h-32" />
            <p className="mt-1 text-sm text-slate-700">Gestión de citas de entrega para proveedores.</p>
          </div>

          <div className="space-y-4">
            <div className="rounded-xl border border-emerald-100 bg-white/80 p-4">
              <h3 className="text-sm font-semibold text-emerald-900">¿De qué trata?</h3>
              <p className="mt-1 text-sm text-slate-700">
                Esta plataforma te permite <span className="font-medium">registrarte como proveedor</span>, iniciar sesión y
                <span className="font-medium"> solicitar citas de entrega</span>. Tambien puedes consultar estados, tiempos e
                historial de cambios de tus operaciones.
              </p>
            </div>

            <div className="rounded-xl border border-emerald-100 bg-white/80 p-4">
              <h3 className="text-sm font-semibold text-emerald-900">Información de contacto</h3>
              <p className="mt-1 text-sm text-slate-700">¿Necesitas ayuda con el acceso o el registro?</p>
              <div className="mt-3 flex flex-col gap-2 text-sm">
                <a className="font-medium text-emerald-800 hover:text-emerald-950" href="https://wa.me/573142254819">
                  WhatsApp: +57 3142254819
                </a>
                <a className="font-medium text-emerald-800 hover:text-emerald-950" href="mailto:ecommerce@ferragro.com">
                  Correo: ecommerce@ferragro.com
                </a>
              </div>
            </div>

            <div className="rounded-xl border border-emerald-100 bg-white/80 p-4">
              <h3 className="text-sm font-semibold text-emerald-900">Privacidad y tratamiento de datos</h3>
              <p className="mt-1 text-sm text-slate-700">
                En el registro solicitamos tu autorización para tratamiento de datos personales conforme a la{" "}
                <span className="font-medium">Ley 1581 de 2012</span>.
              </p>
            </div>
          </div>
        </div>}

        <div className="w-full min-w-0 rounded-2xl border border-emerald-100 bg-white/95 p-5 shadow-xl backdrop-blur sm:p-7">
          {typeof onBack === "function" && (
            <button
              type="button"
              onClick={() => {
                setError("");
                setShowPassword(false);
                setConfirmPassword("");
                setAcceptedLaw1581(false);
                onBack();
              }}
              className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-emerald-800 transition hover:text-emerald-950"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="2" aria-hidden="true">
                <path d="M15 18l-6-6 6-6" />
              </svg>
              Volver
            </button>
          )}
          <header className="mb-5">
            <div className="mb-2 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => (typeof onStartTour === "function" ? onStartTour() : null)}
                data-tour="login-manual-btn"
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-600 transition hover:bg-slate-100"
              >
                Manual
              </button>
              <ThemeToggle variant="inline" />
            </div>
            <div className="inline-flex rounded-xl border border-emerald-100 bg-emerald-50/50 p-1" data-tour="login-tabs">
              <button
                type="button"
                onClick={() => {
                  setIsRegister(false);
                  setConfirmPassword("");
                  setError("");
                  setShowPassword(false);
                  setAcceptedLaw1581(false);
                }}
                className={[
                  "rounded-lg px-3 py-2 text-sm font-medium transition",
                  !isRegister ? "bg-white text-emerald-900 shadow-sm" : "text-emerald-800 hover:text-emerald-950",
                ].join(" ")}
                aria-pressed={!isRegister}
              >
                Iniciar sesión
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsRegister(true);
                  setConfirmPassword("");
                  setError("");
                  setShowPassword(false);
                  setAcceptedLaw1581(false);
                }}
                className={[
                  "rounded-lg px-3 py-2 text-sm font-medium transition",
                  isRegister ? "bg-white text-emerald-900 shadow-sm" : "text-emerald-800 hover:text-emerald-950",
                ].join(" ")}
                aria-pressed={isRegister}
              >
                Registrarme
              </button>
            </div>

            <h1 className="mb-1 mt-4 text-2xl font-bold text-[#121212]">{isRegister ? "Registro" : "Iniciar sesión"}</h1>
            <p className="text-sm text-slate-700">
              {isRegister ? "Registra los datos de tu empresa proveedora." : "Ingresa con tus credenciales para continuar."}
            </p>
          </header>

          {mustChangePassword && (
            <form onSubmit={submitChangePassword} className="space-y-3" noValidate>
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
                Iniciaste con una contraseña temporal. Debes crear una nueva para continuar.
              </div>
              <div>
                <label htmlFor={`${formIdPrefix}-new-password`} className="text-sm font-medium text-[#121212]">
                  Nueva contraseña
                </label>
                <div className="relative">
                  <input
                    id={`${formIdPrefix}-new-password`}
                    className={fieldClass + " pr-10"}
                    type={showNewPassword ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={togglePasswordVisibility(setShowNewPassword)}
                    className="absolute inset-y-0 right-0 mt-1 flex min-h-11 w-11 touch-manipulation items-center justify-center rounded-md text-[#35783C] transition hover:text-[#121212] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40"
                    aria-label={showNewPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                    aria-pressed={showNewPassword}
                  >
                    {showNewPassword ? (
                      <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2" aria-hidden="true">
                        <path d="M3 3l18 18" />
                        <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                        <path d="M9.9 5.1A10.9 10.9 0 0 1 12 5c5.1 0 9.3 3.2 10.8 7-1 2.4-3 4.4-5.6 5.7" />
                        <path d="M6.2 6.2C3.7 7.6 1.9 9.7 1.2 12c1.5 3.8 5.7 7 10.8 7 1.1 0 2.2-.2 3.2-.5" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2" aria-hidden="true">
                        <path d="M1.2 12C2.7 8.2 6.9 5 12 5s9.3 3.2 10.8 7c-1.5 3.8-5.7 7-10.8 7S2.7 15.8 1.2 12z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
              <div>
                <label htmlFor={`${formIdPrefix}-new-password-confirm`} className="text-sm font-medium text-[#121212]">
                  Confirmar nueva contraseña
                </label>
                <div className="relative">
                  <input
                    id={`${formIdPrefix}-new-password-confirm`}
                    className={fieldClass + " pr-10"}
                    type={showNewPassword ? "text" : "password"}
                    value={newPasswordConfirm}
                    onChange={(e) => setNewPasswordConfirm(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={togglePasswordVisibility(setShowNewPassword)}
                    className="absolute inset-y-0 right-0 mt-1 flex min-h-11 w-11 touch-manipulation items-center justify-center rounded-md text-[#35783C] transition hover:text-[#121212] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40"
                    aria-label={showNewPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                    aria-pressed={showNewPassword}
                  >
                    {showNewPassword ? (
                      <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2" aria-hidden="true">
                        <path d="M3 3l18 18" />
                        <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                        <path d="M9.9 5.1A10.9 10.9 0 0 1 12 5c5.1 0 9.3 3.2 10.8 7-1 2.4-3 4.4-5.6 5.7" />
                        <path d="M6.2 6.2C3.7 7.6 1.9 9.7 1.2 12c1.5 3.8 5.7 7 10.8 7 1.1 0 2.2-.2 3.2-.5" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2" aria-hidden="true">
                        <path d="M1.2 12C2.7 8.2 6.9 5 12 5s9.3 3.2 10.8 7c-1.5 3.8-5.7 7-10.8 7S2.7 15.8 1.2 12z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
              {error && (
                <p id={errorId} className="text-sm font-medium text-rose-700" role="alert" aria-live="assertive">
                  {`⚠ ${error}`}
                </p>
              )}
              <button
                type="submit"
                disabled={isSubmitting}
                className="min-h-11 w-full rounded-lg bg-[#35783C] p-2.5 font-medium text-white shadow-md shadow-emerald-900/20 transition hover:bg-[#2d6532] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "Actualizando..." : "Actualizar contraseña"}
              </button>
            </form>
          )}
          {!mustChangePassword && (
          <form onSubmit={submit} className="space-y-3" noValidate>
        {isRegister && (
          <div>
            <label htmlFor={`${formIdPrefix}-nit`} className="text-sm font-medium text-[#121212]">
              NIT (10 dígitos)
            </label>
            <input
            data-tour="register-nit"
            id={`${formIdPrefix}-nit`}
            className={fieldClass}
            type="text"
            inputMode="numeric"
            name="nit"
            placeholder="Ej: 9001234567"
            value={form.nit}
            maxLength={10}
            onChange={onChange}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : undefined}
            required
          />
          </div>
        )}
        {isRegister && (
          <div>
            <label htmlFor={`${formIdPrefix}-dv`} className="text-sm font-medium text-[#121212]">
              Dígito de verificación
            </label>
            <input
            id={`${formIdPrefix}-dv`}
            className={fieldClass}
            type="text"
            inputMode="numeric"
            name="digito_verificacion"
            placeholder="Ej: 1"
            value={form.digito_verificacion}
            maxLength={1}
            onChange={onChange}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : undefined}
            required
          />
          </div>
        )}
        {isRegister && (
          <div>
            <label htmlFor={`${formIdPrefix}-company-name`} className="text-sm font-medium text-[#121212]">
              Nombre corporativo
            </label>
            <input
            data-tour="register-company"
            id={`${formIdPrefix}-company-name`}
            className={fieldClass}
            name="nombre_empresa"
            placeholder="Ej: Aceros Industriales S.A.S."
            onChange={onChange}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : undefined}
            required
          />
          </div>
        )}
        <div>
          <label htmlFor={`${formIdPrefix}-correo_empresa`} className="text-sm font-medium text-[#121212]">
            {isRegister ? "Correo corporativo" : "Correo electrónico"}
          </label>
          <input
          data-tour="login-email"
          className={fieldClass}
          type="email"
          id={`${formIdPrefix}-correo_empresa`}
          name="correo_empresa"
          placeholder={isRegister ? "Correo corporativo" : "Correo electrónico"}
          onChange={onChange}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : undefined}
          required
        />
        {!isRegister && (
          <div className="mt-2 text-right">
            <button
              type="button"
              onClick={submitForgotPassword}
              disabled={isSubmittingForgot || forgotCooldownSeconds > 0}
              data-tour="login-forgot-password"
              className="text-xs font-medium text-emerald-700 transition hover:text-emerald-900 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {forgotCooldownSeconds > 0
                ? `Reenviar en ${forgotWaitLabel}`
                : isSubmittingForgot
                  ? "Enviando..."
                  : "Olvidé mi contraseña"}
            </button>
          </div>
        )}
        {forgotRequested && !isRegister && (
          <p className="mt-2 text-xs text-emerald-700">
            Si el correo existe, te enviamos una contraseña temporal.
          </p>
        )}
        </div>
        {isRegister && (
          <div>
            <label htmlFor={`${formIdPrefix}-responsable-nombre`} className="text-sm font-medium text-[#121212]">
              Nombre persona responsable
            </label>
            <input
            id={`${formIdPrefix}-responsable-nombre`}
            className={fieldClass}
            name="nombre_persona_responsable"
            placeholder="Nombre persona responsable"
            onChange={onChange}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : undefined}
            required
          />
          </div>
        )}
        {isRegister && (
          <div>
            <label htmlFor={`${formIdPrefix}-responsable-doc`} className="text-sm font-medium text-[#121212]">
              Documento persona responsable
            </label>
            <input
            id={`${formIdPrefix}-responsable-doc`}
            className={fieldClass}
            type="text"
            inputMode="numeric"
            name="documento_persona_responsable"
            placeholder="Documento persona responsable (7 a 10 dígitos)"
            value={form.documento_persona_responsable}
            minLength={7}
            maxLength={10}
            onChange={onChange}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : undefined}
            required
          />
          </div>
        )}
        <div data-tour="login-password">
          <label htmlFor={`${formIdPrefix}-password`} className="text-sm font-medium text-[#121212]">
            Contraseña
          </label>
          <div className="relative mt-1 overflow-hidden rounded-lg">
          <input
            className={fieldInputClass + " pr-11"}
            type={showPassword ? "text" : "password"}
            id={`${formIdPrefix}-password`}
            name="password"
            placeholder="Contraseña"
            onChange={onChange}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? `${errorId} ${formIdPrefix}-password-rules` : `${formIdPrefix}-password-rules`}
            required
          />
            <PasswordVisibilityButton
              visible={showPassword}
              onToggle={() => setShowPassword((v) => !v)}
              label="contraseña"
            />
          </div>
        </div>
        {isRegister && (
          <div id={`${formIdPrefix}-password-rules`} className={`rounded-lg border p-3 ${passwordStrength.bg}`}>
            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-2">
              <p className="text-sm font-semibold text-[#121212]">Criterios de contraseña segura</p>
              <p className={`text-sm font-semibold ${passwordStrength.className}`}>
                {passwordStrength.icon} Seguridad: {passwordStrength.label}
              </p>
            </div>
            <ul className="mt-2 space-y-1 text-sm">
              {passwordChecks.map((rule) => (
                <li key={rule.label} className={rule.valid ? "text-emerald-800" : "text-slate-600"}>
                  {rule.valid ? "✓" : "•"} {rule.label}
                </li>
              ))}
            </ul>
          </div>
        )}
        {isRegister && (
          <div>
            <label htmlFor={`${formIdPrefix}-confirm_password`} className="text-sm font-medium text-[#121212]">
              Confirmar contraseña
            </label>
            <div className="relative mt-1 overflow-hidden rounded-lg">
            <input
              className={fieldInputClass + " pr-11"}
              type={showConfirmPassword ? "text" : "password"}
              id={`${formIdPrefix}-confirm_password`}
              name="confirm_password"
              placeholder="Confirmar contraseña"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? errorId : undefined}
              required
            />
            <PasswordVisibilityButton
              visible={showConfirmPassword}
              onToggle={() => setShowConfirmPassword((v) => !v)}
              label="confirmar contraseña"
            />
          </div>
          </div>
        )}
        {isRegister && (
          <div className="rounded-lg border border-emerald-100 bg-emerald-50/40 p-3 text-sm text-slate-700">
            <p className="leading-relaxed">
              Para completar el registro debes leer y aceptar las políticas de tratamiento de datos personales conforme a la{" "}
              <span className="font-medium">Ley 1581 de 2012</span>.
            </p>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                ref={lawTriggerRef}
                data-tour="register-privacy"
                className="min-h-11 w-full rounded-lg border border-[#35783C] bg-white px-3 py-2 text-left font-medium text-[#121212] transition hover:bg-emerald-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 sm:w-auto"
                onClick={() => setShowLawModal(true)}
              >
                Leer políticas (Ley 1581 de 2012)
              </button>
              <span className={`text-sm font-semibold ${acceptedLaw1581 ? "text-emerald-700" : "text-slate-500"}`}>
                {acceptedLaw1581 ? "Políticas aceptadas" : "Pendiente de aceptación"}
              </span>
            </div>
          </div>
        )}
        {error && <p id={errorId} className="text-sm font-medium text-rose-700" role="alert" aria-live="assertive">{`⚠ ${error}`}</p>}
        <button
          type="submit"
          disabled={isSubmitting || retryAfterSeconds > 0}
          data-tour="login-submit"
          className="min-h-11 w-full rounded-lg bg-[#35783C] p-2.5 font-medium text-white shadow-md shadow-emerald-900/20 transition hover:bg-[#2d6532] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {retryAfterSeconds > 0 ? `Espera ${waitLabel}` : isSubmitting ? "Validando..." : "Continuar"}
        </button>
        <p className="mt-4 text-center text-sm text-slate-600">
          {isRegister ? (
            <>
              ¿Ya tienes cuenta?{" "}
              <button
                type="button"
                className="font-medium text-emerald-700 transition hover:text-emerald-900"
                onClick={() => {
                  setIsRegister(false);
                  setConfirmPassword("");
                  setError("");
                  setShowPassword(false);
                  setAcceptedLaw1581(false);
                }}
              >
                Inicia sesión
              </button>
            </>
          ) : (
            <>
              ¿No tienes cuenta?{" "}
              <button
                type="button"
                className="font-medium text-emerald-700 transition hover:text-emerald-900"
                onClick={() => {
                  setIsRegister(true);
                  setConfirmPassword("");
                  setError("");
                  setShowPassword(false);
                  setAcceptedLaw1581(false);
                }}
              >
                Regístrate
              </button>
            </>
          )}
        </p>
        </form>
        )}
        </div>
      </div>
      {isRegister && showLawModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4" role="presentation">
          <div
            ref={modalRef}
            className="w-full max-w-2xl rounded-2xl border border-emerald-100 bg-white p-5 shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby={modalTitleId}
            aria-describedby={modalDescId}
          >
            <div className="flex items-start justify-between gap-3">
              <h2 id={modalTitleId} className="text-lg font-bold text-[#121212]">Políticas de tratamiento de datos (Ley 1581 de 2012)</h2>
              <button
                ref={modalCloseRef}
                type="button"
                className="min-h-11 min-w-11 rounded-md px-2 py-1 text-slate-600 transition hover:bg-slate-100 hover:text-[#121212] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40"
                onClick={() => setShowLawModal(false)}
                aria-label="Cerrar modal"
              >
                ✕
              </button>
            </div>
            <div id={modalDescId} className="mt-3 max-h-[55vh] overflow-y-auto rounded-lg border border-emerald-100 bg-emerald-50/30 p-4 text-sm leading-relaxed text-slate-700">
              <p>
                La Ley 1581 de 2012 es la norma de protección de datos personales en Colombia. Esta ley define cómo se debe
                recolectar, usar, almacenar y proteger la información personal de los titulares.
              </p>
              <p className="mt-2">
                En este portal, los datos se usan para gestionar el registro de proveedores, autenticación de acceso y
                operación de citas de entrega.
              </p>
              <p className="mt-2">
                Como titular de datos, puedes ejercer tus derechos de conocer, actualizar, rectificar o solicitar la
                supresión de tu información, así como revocar la autorización cuando sea procedente.
              </p>
              <p className="mt-2">
                La información se trata con medidas de seguridad administrativas, técnicas y organizativas para evitar el
                acceso no autorizado, pérdida o uso indebido.
              </p>
            </div>
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="min-h-11 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40"
                onClick={() => setShowLawModal(false)}
              >
                Cerrar
              </button>
              <button
                type="button"
                className="min-h-11 rounded-lg bg-[#35783C] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#2d6532] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40"
                onClick={() => {
                  setAcceptedLaw1581(true);
                  setShowLawModal(false);
                }}
              >
                He leído y acepto
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
