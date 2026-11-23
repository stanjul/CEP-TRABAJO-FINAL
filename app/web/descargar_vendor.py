"""Descarga (una sola vez) las dependencias del frontend para que la app funcione sin internet.

Uso: .venv\\Scripts\\python.exe -m app.web.descargar_vendor

Descarga a app/web/static/vendor/:
- tailwindcss.js        Tailwind CSS (Play CDN v3), el mismo que usan los HTML de Stitch.
- plotly.min.js         Plotly.js (bundle básico: scatter, bar).
- fuentes/…             League Spartan (títulos), Montserrat (texto y números) y Material Symbols
                        Outlined (woff2) + fuentes.css
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

VENDOR = Path(__file__).resolve().parent / "static" / "vendor"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")  # Google Fonts entrega woff2 solo a navegadores modernos
ARCHIVOS = {
    "tailwindcss.js": "https://cdn.tailwindcss.com/3.4.16",
    "plotly.min.js": "https://cdn.plot.ly/plotly-basic-2.35.2.min.js",
}
FUENTES = [
    "https://fonts.googleapis.com/css2?family=League+Spartan:wght@400;500;600;700&family=Montserrat:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap",
    "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=block",
]
SUBCONJUNTOS = ("latin", "latin-ext", "fallback")  # se omiten cirílico, griego, vietnamita


def bajar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> None:
    VENDOR.mkdir(parents=True, exist_ok=True)
    for nombre, url in ARCHIVOS.items():
        destino = VENDOR / nombre
        if not destino.exists():
            destino.write_bytes(bajar(url))
        print(f"  {nombre:20} {destino.stat().st_size / 1024:8.0f} KB")

    dir_f = VENDOR / "fuentes"
    dir_f.mkdir(exist_ok=True)
    css_final = []
    for url in FUENTES:
        css = bajar(url).decode()
        # Cada bloque viene precedido por un comentario /* latin */, /* cyrillic */, …
        bloques = re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*{[^}]+})", css)
        if not bloques:  # Material Symbols viene en un solo bloque sin comentario
            bloques = [("latin", b) for b in re.findall(r"@font-face\s*{[^}]+}", css)]
        for subconjunto, bloque in bloques:
            if subconjunto not in SUBCONJUNTOS:
                continue
            for fuente in re.findall(r"url\((https://[^)]+)\)", bloque):
                nombre = re.sub(r"[^\w.-]", "_", fuente.split("/s/")[-1])[-90:]
                destino = dir_f / nombre
                if not destino.exists():
                    destino.write_bytes(bajar(fuente))
                bloque = bloque.replace(fuente, f"fuentes/{nombre}")
            css_final.append(bloque)
    css_final.append(".material-symbols-outlined{font-family:'Material Symbols Outlined';font-weight:normal;"
                     "font-style:normal;font-size:24px;line-height:1;letter-spacing:normal;text-transform:none;"
                     "display:inline-block;white-space:nowrap;word-wrap:normal;direction:ltr;"
                     "-webkit-font-feature-settings:'liga';-webkit-font-smoothing:antialiased;"
                     "font-variation-settings:'FILL' 0,'wght' 400;}")
    (VENDOR / "fuentes.css").write_text("\n".join(css_final), encoding="utf-8")
    total = sum(f.stat().st_size for f in dir_f.iterdir()) / 1024
    print(f"  fuentes.css + {len(list(dir_f.iterdir()))} archivos woff2 ({total:.0f} KB)")


if __name__ == "__main__":
    main()
