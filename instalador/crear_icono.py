"""Genera instalador/cep.ico (16–256 px) con el dibujo del logo: una mini carta de control.

Uso: .venv\\Scripts\\python.exe instalador\\crear_icono.py   (lo llama construir.bat)
Colores del diseño: fondo petróleo #003441, límites #FFDAD6, centro #87BBCE, datos #A1F2E2.
"""

from pathlib import Path

from PIL import Image, ImageDraw

SALIDA = Path(__file__).resolve().parent / "cep.ico"


def dibujar(lado: int = 256) -> Image.Image:
    s = lado / 32  # el logo está dibujado en una grilla de 32 × 32
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1 * s, 1 * s, 31 * s, 31 * s], radius=5 * s, fill="#003441", outline="#87BBCE", width=max(1, round(1.2 * s)))
    grosor = max(1, round(1.4 * s))
    for y, color, punteada in ((9, "#FFDAD6", True), (16, "#87BBCE", False), (23, "#FFDAD6", True)):
        if punteada:
            x = 5.0
            while x < 27:
                d.line([(x * s, y * s), (min(x + 2, 27) * s, y * s)], fill=color, width=grosor)
                x += 3.5
        else:
            d.line([(5 * s, y * s), (27 * s, y * s)], fill=color, width=grosor)
    puntos = [(6, 17), (10, 12.5), (14, 18.5), (18, 13.5), (22, 19.5), (26, 10.5)]
    d.line([(x * s, y * s) for x, y in puntos], fill="#A1F2E2", width=max(2, round(2.4 * s)), joint="curve")
    r = 1.6 * s
    for x, y in puntos:
        d.ellipse([x * s - r, y * s - r, x * s + r, y * s + r], fill="#A1F2E2")
    return img


if __name__ == "__main__":
    dibujar(256).save(SALIDA, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Ícono: {SALIDA}")
