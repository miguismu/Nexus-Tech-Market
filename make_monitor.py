# -*- coding: utf-8 -*-
"""Genera una imagen limpias del monitor LG UltraGear (placeholder propio, sin marcas)."""
from PIL import Image, ImageDraw

W, H = 640, 520
img = Image.new("RGB", (W, H), (16, 12, 24))
d = ImageDraw.Draw(img)
# Monitor
d.rounded_rectangle([60, 60, 580, 380], radius=18, fill=(24, 18, 36), outline=(185, 154, 87), width=3)
d.rounded_rectangle([78, 78, 562, 362], radius=10, fill=(10, 8, 16))
# Pantalla con brillo morado
for y in range(78, 362):
    t = (y - 78) / 284
    d.line([(78, y), (562, y)], fill=(int(60 + 40 * (1 - t)), int(30 + 24 * (1 - t)), int(90 + 70 * (1 - t))))
# Brillo UltraGear
d.ellipse([180, 120, 300, 220], fill=(120, 84, 150))
d.text((200, 200), "UltraGear", fill=(233, 214, 160))
# Base
d.rectangle([280, 380, 360, 420], fill=(30, 22, 44))
d.rounded_rectangle([200, 420, 440, 442], radius=10, fill=(34, 26, 50), outline=(185, 154, 87), width=2)
img.save("images/lg-ultragear-27.png")
print("ok")
