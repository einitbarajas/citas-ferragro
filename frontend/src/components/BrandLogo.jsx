export default function BrandLogo({
  className = "",
  src = "/ferragro-blan-bord-v2.png",
  alt = "Ferragro",
  protectedArea = true,
  /** Mejora LCP cuando el logo es el elemento principal visible (p. ej. cabecera landing). Valores: `"high"` \| `"low"` \| `"auto"`. */
  fetchPriority,
}) {
  return (
    <div className={protectedArea ? "rounded-lg p-1" : ""} aria-label="Marca corporativa Ferragro">
      <img
        src={src}
        alt={alt}
        width={200}
        height={48}
        decoding="async"
        {...(fetchPriority ? { fetchpriority: fetchPriority } : {})}
        className={`block h-12 w-full object-contain object-left ${className}`.trim()}
      />
    </div>
  );
}

