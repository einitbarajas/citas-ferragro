#!/usr/bin/env python3
"""Genera logos transparentes (correo modo claro/oscuro y portal)."""
from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "backend" / "static"
PUBLIC = ROOT / "frontend" / "public"
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


def main() -> None:
    src = next((p for p in SOURCE_CANDIDATES if p.is_file()), None)
    if src is None:
        raise SystemExit("No hay PNG fuente en static/ ni frontend/public/")

    transparent = remove_outer_background(Image.open(src))

    for name in ("ferragro-logo.png", "ferragro-logo-email.png"):
        transparent.save(STATIC / name, "PNG", optimize=True)
        transparent.save(PUBLIC / name, "PNG", optimize=True)
    transparent.save(STATIC / "ferragro-logo-transparent.png", "PNG", optimize=True)

    print(f"source={src.name}")
    print(f"transparent logo -> {STATIC / 'ferragro-logo-email.png'} ({transparent.size}, mode=RGBA)")


if __name__ == "__main__":
    main()
