import { useState } from "react";

const PNG_LOGO = "/ferragro-logo.png";
const WEBP_288 = "/ferragro-logo-288.webp";
const WEBP_576 = "/ferragro-logo-576.webp";

export default function BrandLogo({
  className = "",
  src = WEBP_288,
  srcSet = `${WEBP_288} 288w, ${WEBP_576} 576w`,
  sizes = "(max-width: 640px) 200px, 288px",
  alt = "Ferragro",
  protectedArea = true,
  fetchPriority,
}) {
  const [usePng, setUsePng] = useState(false);

  return (
    <div className={protectedArea ? "rounded-lg p-1" : ""}>
      <img
        src={usePng ? PNG_LOGO : src}
        srcSet={usePng ? undefined : srcSet}
        sizes={usePng ? undefined : sizes}
        alt={alt}
        width={288}
        height={60}
        decoding="async"
        onError={() => {
          if (!usePng) setUsePng(true);
        }}
        {...(fetchPriority ? { fetchpriority: fetchPriority } : {})}
        className={`block h-12 w-full object-contain object-left ${className}`.trim()}
      />
    </div>
  );
}
