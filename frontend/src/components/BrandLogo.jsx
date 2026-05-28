export default function BrandLogo({
  className = "",
  src = "/ferragro-logo-288.webp",
  srcSet = "/ferragro-logo-288.webp 288w, /ferragro-logo-576.webp 576w",
  sizes = "(max-width: 640px) 200px, 288px",
  alt = "Ferragro",
  protectedArea = true,
  /** Mejora LCP cuando el logo es el elemento principal visible (p. ej. cabecera landing). Valores: `"high"` \| `"low"` \| `"auto"`. */
  fetchPriority,
}) {
  return (
    <div className={protectedArea ? "rounded-lg p-1" : ""}>
      <img
        src={src}
        srcSet={srcSet}
        sizes={sizes}
        alt={alt}
        width={288}
        height={60}
        decoding="async"
        {...(fetchPriority ? { fetchpriority: fetchPriority } : {})}
        className={`block h-12 w-full object-contain object-left ${className}`.trim()}
      />
    </div>
  );
}

