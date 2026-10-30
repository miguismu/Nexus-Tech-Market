# -*- coding: utf-8 -*-
"""Genera la imagen de portada de NEXUS (hero keyart morado/dorado con orbe)."""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "images" / "nexus-cover.png"
W, H = 1920, 1080
random.seed(7)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def main() -> None:
    img = Image.new("RGB", (W, H), (12, 7, 20))
    # Fondo: gradiente diagonal morado muy oscuro -> casi negro, con bruma dorada.
    top = (26, 14, 44)
    bottom = (7, 4, 12)
    px = img.load()
    for y in range(H):
        row = lerp(top, bottom, (y / H) ** 1.25)
        for x in range(W):
            px[x, y] = row

    draw = ImageDraw.Draw(img, "RGBA")

    # Nebulosas suaves.
    def glow(cx, cy, radius, color, alpha):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        g = ImageDraw.Draw(layer)
        for step in range(radius, 0, -6):
            a = int(alpha * (1 - step / radius) ** 2)
            g.ellipse([cx - step, cy - step, cx + step, cy + step], fill=color + (a,))
        img.paste(Image.alpha_composite(img.convert("RGBA"), layer.filter(ImageFilter.GaussianBlur(48))).convert("RGB"), (0, 0))

    glow(1450, 300, 520, (120, 66, 150), 120)      # nebulosa morada derecha
    glow(330, 820, 430, (86, 48, 112), 90)         # nebulosa morada inferior izquierda
    glow(1180, 700, 300, (176, 140, 74), 46)       # bruma dorada sutil

    # Estrellas.
    for _ in range(420):
        x, y = random.randint(0, W - 1), random.randint(0, H - 1)
        r = random.choice((1, 1, 1, 2))
        a = random.randint(60, 210)
        tint = random.choice([(230, 224, 255), (255, 244, 214), (212, 200, 255)])
        draw.ellipse([x, y, x + r, y + r], fill=tint + (a,))

    # Grid de perspectiva sutil (piso tecnológico).
    horizon = int(H * 0.78)
    for i in range(-24, 25):
        x0 = W // 2 + i * 90
        draw.line([(W // 2 + i * 22, horizon), (x0, H)], fill=(185, 154, 87, 26), width=1)
    for k in range(1, 16):
        y = horizon + int((H - horizon) * (k / 15) ** 2.2)
        draw.line([(0, y), (W, y)], fill=(185, 154, 87, 18), width=1)

    # Montañas / skyline geométrico morado oscuro.
    ridge = [(0, H)]
    level = horizon - 40
    for x in range(0, W + 80, 80):
        level += random.randint(-46, 46)
        level = max(horizon - 260, min(horizon + 30, level))
        ridge.append((x, level))
    ridge += [(W, H)]
    draw.polygon(ridge, fill=(16, 9, 26, 255))
    ridge2 = [(0, H)]
    level = horizon + 10
    for x in range(0, W + 120, 120):
        level += random.randint(-34, 34)
        level = max(horizon - 90, min(horizon + 120, level))
        ridge2.append((x, level))
    ridge2 += [(W, H)]
    draw.polygon(ridge2, fill=(9, 5, 15, 255))

    # ===== Orbe NEXUS brillante (protagonista, tercio derecho) =====
    ox, oy, R = 1370, 470, 250
    # Halo exterior: corona brillante compacta que decae rápido (fondo oscuro intacto).
    for step in range(R * 2, R, -8):
        t = (step - R) / R
        a = int(150 * (1 - t) ** 3.4)
        hue = lerp((208, 172, 96), (140, 92, 170), t)
        draw.ellipse([ox - step, oy - step, ox + step, oy + step], fill=hue + (a,))

    # Cuerpo del orbe: gradiente radial dorado->morado->oscuro.
    orb = Image.new("RGBA", (R * 2, R * 2), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(orb)
    for step in range(R, 0, -1):
        t = step / R  # 1 = borde exterior, 0 = centro
        if t > 0.86:
            color = (34, 19, 48)                                   # borde oscuro morado
        elif t > 0.66:
            color = lerp((34, 19, 48), (84, 48, 116), (0.86 - t) / 0.2)
        elif t > 0.44:
            color = lerp((84, 48, 116), (168, 108, 196), (0.66 - t) / 0.22)
        elif t > 0.26:
            color = lerp((168, 108, 196), (226, 186, 110), (0.44 - t) / 0.18)
        elif t > 0.12:
            color = lerp((226, 186, 110), (250, 238, 200), (0.26 - t) / 0.14)
        else:
            color = (253, 244, 214)                                # núcleo dorado brillante
        odraw.ellipse([R - step, R - step, R + step, R + step], fill=color + (255,))
    # Highlight especular muy sutil arriba-izquierda (difuminado, no burbuja).
    hl = Image.new("RGBA", (R * 2, R * 2), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse([R * 0.3, R * 0.18, R * 0.62, R * 0.46], fill=(255, 255, 245, 70))
    orb = Image.alpha_composite(orb, hl.filter(ImageFilter.GaussianBlur(18)))
    orb = orb.filter(ImageFilter.GaussianBlur(2))
    img.paste(orb, (ox - R, oy - R), orb)

    # Anillos orbitales dorados.
    for rx, ry, width, alpha, tilt in ((R * 1.42, R * 0.5, 3, 150, -16), (R * 1.7, R * 0.34, 2, 100, 22)):
        ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        rdraw = ImageDraw.Draw(ring)
        rdraw.ellipse([ox - rx, oy - ry, ox + rx, oy + ry], outline=(214, 180, 104, alpha), width=width)
        ring = ring.rotate(tilt, center=(ox, oy), resample=Image.BICUBIC)
        img.paste(Image.alpha_composite(img.convert("RGBA"), ring).convert("RGB"), (0, 0))

    # Partículas doradas ascendiendo alrededor del orbe.
    for _ in range(140):
        ang = random.uniform(0, math.tau)
        dist = random.uniform(R * 0.9, R * 2.6)
        x, y = ox + math.cos(ang) * dist, oy + math.sin(ang) * dist * 0.8
        s = random.choice((1, 1, 2, 2, 3))
        a = random.randint(70, 200)
        draw.ellipse([x, y, x + s, y + s], fill=(232, 200, 128, a))

    # Líneas de conexión tipo red hacia la ciudad.
    nodes = [(random.randint(40, W - 40), random.randint(int(H * 0.62), H - 60)) for _ in range(26)]
    for i, (nx, ny) in enumerate(nodes):
        if i % 3 == 0 and nodes[i] != (ox, oy):
            tx, ty = ox + (nx - ox) * 0.18, oy + (ty_ := ny - oy) * 0.18
            draw.line([(nx, ny), (ox, oy)], fill=(185, 154, 87, 34), width=1)
        draw.ellipse([nx - 2, ny - 2, nx + 2, ny + 2], fill=(226, 190, 120, 130))

    # Friaje/viñeta cinematográfica.
    vignette = Image.new("L", (W, H), 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse([-W * 0.25, -H * 0.3, W * 1.25, H * 1.3], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(220))
    black = Image.new("RGB", (W, H), (4, 2, 8))
    img = Image.composite(img, black, vignette)

    OUT.parent.mkdir(exist_ok=True)
    img.save(OUT, optimize=True)
    print(f"Portada generada: {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
