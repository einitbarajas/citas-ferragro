#!/usr/bin/env python3
"""Genera logos: portal (transparente), correo claro (fondo blanco) y oscuro (fondo gris Gmail)."""
from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "backend" / "static"
PUBLIC = ROOT / "frontend" / "public"
# Gris cercano al fondo de Gmail en modo oscuro (evita caja blanca).
GMAIL_DARK_BG = (45, 45, 45)
EMAIL_LIGHT_BG = (255, 255, 255)

SOURCE_CANDIDATES = (
    STATIC / "ferragro-logo-source.png",
    STATIC / "ferragro-blan-bord.png",
    STATIC / "ferragro-logo.png",
    PUBLIC / "ferragro-logo.png",
)


def _is_background_pixel(r: int, g: int, b: int, a: int) -> bool:
    if a < 10:
        return True
    if g > 65 and g >= r + 8 and g >= b + 8:
        return False
    if r > 175 and g > 175 and b > 175:
        return False
    return max(r, g, b) < 95


def remove_outer_background(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    seen = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque()

    for x in range(w):
        for y in (0, h - 1):
            if _is_background_pixel(*px[x, y]) and not seen[y][x]:
                seen[y][x] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not seen[y][x] and _is_background_pixel(*px[x, y]):
                seen[y][x] = True
                q.append((x, y))

    while q:
        x, y = q.popleft()
        r, g, b, _a = px[x, y]
        px[x, y] = (r, g, b, 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx]:
                if _is_background_pixel(*px[nx, ny]):
                    seen[ny][nx] = True
                    q.append((nx, ny))

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a and max(r, g, b) < 30 and g < 50:
                px[x, y] = (0, 0, 0, 0)

    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def flatten_on_color(img: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    base = Image.new("RGBA", img.size, (*rgb, 255))
    base.paste(img, mask=img.split()[3])
    return base.convert("RGB")


def main() -> None:
    src = next((p for p in SOURCE_CANDIDATES if p.is_file()), None)
    if src is None:
        raise SystemExit("No hay PNG fuente en static/ ni frontend/public/")

    transparent = remove_outer_background(Image.open(src))
    light_rgb = flatten_on_color(transparent, EMAIL_LIGHT_BG)
    dark_rgb = flatten_on_color(transparent, GMAIL_DARK_BG)

    transparent.save(STATIC / "ferragro-logo-transparent.png", "PNG", optimize=True)
    transparent.save(STATIC / "ferragro-logo.png", "PNG", optimize=True)
    light_rgb.save(STATIC / "ferragro-logo-email-light.png", "PNG", optimize=True)
    dark_rgb.save(STATIC / "ferragro-logo-email-dark.png", "PNG", optimize=True)
    transparent.save(PUBLIC / "ferragro-logo.png", "PNG", optimize=True)
    light_rgb.save(PUBLIC / "ferragro-logo-email-light.png", "PNG", optimize=True)
    dark_rgb.save(PUBLIC / "ferragro-logo-email-dark.png", "PNG", optimize=True)

    print(f"source={src.name} size={transparent.size}")
    print(f"light -> ferragro-logo-email-light.png")
    print(f"dark  -> ferragro-logo-email-dark.png (bg={GMAIL_DARK_BG})")


if __name__ == "__main__":
    main()
