"""Construye el manual de usuario a partir de docs/manual/manual.html.

Salidas:
  docs/MANUAL_USUARIO.html  un solo archivo (fuentes e imágenes incrustadas): se abre sin internet.
  docs/MANUAL_USUARIO.pdf   el mismo manual impreso con Microsoft Edge (estilos de impresión).

Uso (desde la raíz del proyecto):
  .venv\\Scripts\\python.exe docs\\manual\\construir_manual.py [--sin-pdf]
Requiere Microsoft Edge (para el PDF) y el paquete websockets.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
FUENTES = RAIZ / "app" / "web" / "static" / "vendor" / "fuentes"
SALIDA_HTML = RAIZ / "docs" / "MANUAL_USUARIO.html"
SALIDA_PDF = RAIZ / "docs" / "MANUAL_USUARIO.pdf"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
PUERTO = 9361


def datos_uri(ruta: Path, tipo: str) -> str:
    return f"data:{tipo};base64," + base64.b64encode(ruta.read_bytes()).decode("ascii")


def construir_html() -> str:
    html = (AQUI / "manual.html").read_text(encoding="utf-8")
    html = re.sub(r"url\(fuentes/([^)]+)\)", lambda m: f"url({datos_uri(FUENTES / m.group(1), 'font/woff2')})", html)
    html = re.sub(r'src="img/([^"]+)"', lambda m: f'src="{datos_uri(AQUI / "img" / m.group(1), "image/png")}"', html)
    faltan = re.findall(r'(?:src="img/|url\(fuentes/)', html)
    if faltan:
        raise SystemExit(f"Quedaron recursos sin incrustar: {len(faltan)}")
    SALIDA_HTML.write_text(html, encoding="utf-8")
    return html


async def imprimir_pdf() -> None:
    import websockets

    perfil = tempfile.mkdtemp(prefix="cep-manual-")
    proc = subprocess.Popen([str(EDGE), "--headless=new", "--disable-gpu", f"--remote-debugging-port={PUERTO}",
                             f"--user-data-dir={perfil}", "about:blank"])
    try:
        for _ in range(60):
            try:
                objetivos = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}/json"))
                pagina = next(o for o in objetivos if o["type"] == "page")
                break
            except Exception:
                time.sleep(0.25)
        async with websockets.connect(pagina["webSocketDebuggerUrl"], max_size=500_000_000, ping_interval=None) as ws:
            n = 0

            async def cdp(metodo, **params):
                nonlocal n
                n += 1
                await ws.send(json.dumps({"id": n, "method": metodo, "params": params}))
                while True:
                    r = json.loads(await ws.recv())
                    if r.get("id") == n:
                        if "error" in r:
                            raise RuntimeError(r["error"])
                        return r["result"]

            await cdp("Page.enable")
            await cdp("Page.navigate", url=SALIDA_HTML.as_uri())
            await asyncio.sleep(4)
            # Todo visible para imprimir: preguntas abiertas y todos los capítulos.
            await cdp("Runtime.evaluate", expression=(
                "document.querySelectorAll('details').forEach(d => d.open = true);"
                "document.querySelectorAll('.capitulo').forEach(c => c.classList.remove('oculto-perfil'));"
                "document.fonts.ready.then(() => true)"), awaitPromise=True)
            pie = ('<div style="width:100%;font-size:8px;font-family:Montserrat,sans-serif;color:#70787c;'
                   'padding:0 14mm;display:flex;justify-content:space-between">'
                   '<span>CEP — Manual de usuario</span><span class="pageNumber"></span></div>')
            r = await cdp("Page.printToPDF", printBackground=True, preferCSSPageSize=True,
                          displayHeaderFooter=True, headerTemplate="<span></span>", footerTemplate=pie)
            SALIDA_PDF.write_bytes(base64.b64decode(r["data"]))
    finally:
        proc.terminate()


if __name__ == "__main__":
    html = construir_html()
    print(f"HTML: {SALIDA_HTML} ({len(html) / 1e6:.1f} MB)")
    if "--sin-pdf" not in sys.argv:
        asyncio.run(imprimir_pdf())
        print(f"PDF:  {SALIDA_PDF} ({SALIDA_PDF.stat().st_size / 1e6:.1f} MB)")
