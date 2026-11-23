"""Programa de escritorio (Windows): servidor local + ventana propia, sin navegador ni consola.

Es el punto de entrada de CEP.exe (PyInstaller). Al abrirse:
  1. Usa la carpeta de datos `Documentos\\CEP` (o `CEP_DATOS`): base `cep.db`, `reportes\\`,
     `respaldos\\` y `registro.log`.
  2. Evita una segunda instancia (mutex de Windows): si ya está abierto, lo avisa y sale.
  3. Hace un respaldo de la base al iniciar (se guardan los últimos 20).
  4. Levanta FastAPI en 127.0.0.1 en un puerto libre (solo este equipo) y abre una ventana con
     WebView2 (pywebview). Al cerrar la ventana se apaga el servidor.

Opciones (para pruebas): `--sin-ventana` (solo el servidor) y `--puerto N`.
La base arranca vacía (CEP_SIN_DEMO=1); los datos de demostración se cargan desde la interfaz.
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
from logging.handlers import RotatingFileHandler
from pathlib import Path

TITULO = "CEP — Control Estadístico de Procesos"
MUTEX = "Local\\CEP_Control_Estadistico_de_Procesos"
FOLDERID_DOCUMENTOS = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"
registro = logging.getLogger("cep")


# ---------------------------------------------------------------------------
# Carpeta de datos y entorno
# ---------------------------------------------------------------------------

def carpeta_documentos() -> Path:
    """Carpeta «Documentos» real del usuario (respeta la redirección de OneDrive)."""
    if sys.platform == "win32":
        try:
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]

            guid = GUID()
            ctypes.oledll.ole32.CLSIDFromString(FOLDERID_DOCUMENTOS, ctypes.byref(guid))
            ruta = ctypes.c_wchar_p()
            ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(ruta))
            valor = ruta.value
            ctypes.windll.ole32.CoTaskMemFree(ruta)
            if valor:
                return Path(valor)
        except (OSError, AttributeError):
            pass
    return Path.home() / "Documents"


def carpeta_datos() -> Path:
    return Path(os.environ["CEP_DATOS"]) if os.environ.get("CEP_DATOS") else carpeta_documentos() / "CEP"


def preparar_entorno(datos: Path) -> None:
    """Variables de entorno que lee la app al importarse (base, modo y sin demostración automática)."""
    datos.mkdir(parents=True, exist_ok=True)
    os.environ["CEP_DATOS"] = str(datos)
    os.environ["CEP_DB_URL"] = f"sqlite:///{(datos / 'cep.db').as_posix()}"
    os.environ["CEP_MODO"] = "escritorio"
    os.environ["CEP_SIN_DEMO"] = "1"


def configurar_registro(datos: Path) -> None:
    """Errores y avisos a `registro.log` (1 MB, 3 archivos). En el .exe no hay consola."""
    manejador = RotatingFileHandler(datos / "registro.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(manejador)
    for nombre in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(nombre).setLevel(logging.WARNING)
    if sys.stdout is None:  # .exe sin consola: algunas librerías escriben en stdout/stderr
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")


# ---------------------------------------------------------------------------
# Utilidades de Windows
# ---------------------------------------------------------------------------

def mensaje(texto: str, error: bool = False) -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, texto, TITULO, 0x10 if error else 0x40)
    else:
        print(texto)


def tomar_instancia_unica():
    """Crea el mutex de la app. Devuelve el identificador o None si ya hay otra instancia abierta."""
    if sys.platform != "win32":
        return True
    h = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return None
    return h


def puerto_libre(preferido: int = 8000) -> int:
    for puerto in range(preferido, preferido + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", puerto)) != 0:
                return puerto
    raise RuntimeError("No hay puertos libres entre 8000 y 8099.")


def esperar_servidor(url: str, segundos: float = 90) -> bool:
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            with urllib.request.urlopen(url + "api/salud", timeout=2) as r:
                if r.status == 200:
                    return True
        except OSError:
            time.sleep(0.3)
    return False


# ---------------------------------------------------------------------------
# Arranque
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=TITULO)
    p.add_argument("--sin-ventana", action="store_true", help="Solo el servidor (pruebas)")
    p.add_argument("--puerto", type=int, default=8000)
    args = p.parse_args(argv)

    datos = carpeta_datos()
    preparar_entorno(datos)
    configurar_registro(datos)
    candado = tomar_instancia_unica()
    if candado is None:
        mensaje("CEP ya está abierto en este equipo. Busca su ventana en la barra de tareas.")
        return 0
    registro.info("Inicio de CEP. Datos en %s", datos)

    try:
        from app.db import respaldos

        if (datos / "cep.db").exists():
            respaldos.crear("inicio")
    except Exception:  # un respaldo fallido no impide abrir la app
        registro.exception("No se pudo hacer el respaldo de inicio")

    puerto = puerto_libre(args.puerto)
    url = f"http://127.0.0.1:{puerto}/"
    estado: dict = {}

    def correr_servidor() -> None:
        # La importación de la app (scipy, pandas, statsmodels…) es lo que más tarda: se hace en
        # este hilo para que la ventana aparezca de inmediato con la pantalla de carga.
        try:
            import uvicorn

            from app.main import app

            estado["servidor"] = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_config=None,
                                                               access_log=False))
            estado["servidor"].run()
        except Exception:
            registro.exception("El servidor se detuvo por un error")

    hilo = threading.Thread(target=correr_servidor, name="servidor", daemon=True)
    hilo.start()

    if args.sin_ventana:
        if not esperar_servidor(url):
            registro.error("El servidor no respondió a tiempo")
            return 1
        registro.info("Servidor listo en %s", url)
        try:
            while hilo.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
    else:
        import webview

        webview.settings["ALLOW_DOWNLOADS"] = True  # PDF, Excel, plantillas y copias de la base
        ventana = webview.create_window(TITULO, html=PANTALLA_CARGA, width=1440, height=900, min_size=(1024, 680),
                                        background_color="#F8F9FF")

        def cuando_abre() -> None:
            if esperar_servidor(url):
                registro.info("Servidor listo en %s", url)
                ventana.load_url(url)
            else:
                registro.error("El servidor no respondió a tiempo")
                ventana.load_html(PANTALLA_ERROR.replace("{registro}", str(datos / "registro.log")))

        # private_mode=False: conserva localStorage (usuario, variable activa) entre sesiones.
        webview.start(cuando_abre, private_mode=False, storage_path=str(datos / ".ventana"))
    if estado.get("servidor"):
        estado["servidor"].should_exit = True
    hilo.join(timeout=10)
    registro.info("CEP cerrado")
    return 0


# Pantallas mientras arranca el servidor (sin fuentes externas: todavía no hay servidor).
_ESTILO = """<style>
  html,body{margin:0;height:100%;background:#F8F9FF;font-family:'Segoe UI',system-ui,sans-serif;color:#0B1C30}
  .caja{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;text-align:center}
  h1{margin:0;font-size:26px;color:#0F4C5C;font-weight:700}
  p{margin:0;color:#40484B;font-size:15px;max-width:520px;line-height:1.5}
  .barra{width:220px;height:4px;border-radius:2px;background:#DCE9FF;overflow:hidden}
  .barra i{display:block;width:40%;height:100%;background:#0F4C5C;border-radius:2px;animation:ir 1.2s ease-in-out infinite}
  @keyframes ir{0%{transform:translateX(-100%)}100%{transform:translateX(250%)}}
  @media (prefers-reduced-motion:reduce){.barra i{animation:none;width:100%}}
</style>"""
_LOGO = """<svg width="72" height="72" viewBox="0 0 32 32" aria-hidden="true">
  <rect x="1" y="1" width="30" height="30" rx="5" fill="#003441" stroke="#87bbce" stroke-width="1.2"/>
  <line x1="5" y1="9" x2="27" y2="9" stroke="#ffdad6" stroke-width="1.2" stroke-dasharray="2 1.5"/>
  <line x1="5" y1="16" x2="27" y2="16" stroke="#87bbce" stroke-width="1.2"/>
  <line x1="5" y1="23" x2="27" y2="23" stroke="#ffdad6" stroke-width="1.2" stroke-dasharray="2 1.5"/>
  <polyline points="6,17 10,13 14,18 18,14 22,19 26,11" stroke="#a1f2e2" stroke-width="2" fill="none" stroke-linejoin="round"/>
</svg>"""
PANTALLA_CARGA = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">{_ESTILO}</head><body><div class="caja">
  {_LOGO}<h1>Control Estadístico de Procesos</h1><div class="barra"><i></i></div>
  <p>Abriendo CEP… La primera vez puede tardar un poco más.</p></div></body></html>"""
PANTALLA_ERROR = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">{_ESTILO}</head><body><div class="caja">
  {_LOGO}<h1>No se pudo abrir CEP</h1>
  <p>Cierra esta ventana y vuelve a abrir el programa. Si el problema sigue, envía el archivo
  <b>{{registro}}</b> a quien te dio el programa.</p></div></body></html>"""


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # cualquier error inesperado queda en el registro y se avisa
        registro.exception("Error al iniciar CEP")
        mensaje("CEP encontró un error al iniciar. Revisa registro.log en Documentos\\CEP.", error=True)
        sys.exit(1)
