const PNG_LOGO = "/ferragro-logo.png";

export default function BrandLogo({
  className = "",
  src = PNG_LOGO,
  alt = "Ferragro",
  protectedArea = true,
  fetchPriority,
}) {
  return (
    <div className={protectedArea ? "rounded-lg p-1" : ""}>
      <img
        src={src}
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
