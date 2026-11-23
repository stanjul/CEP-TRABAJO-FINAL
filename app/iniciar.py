"""Arranque con un solo comando: levanta el servidor y abre el navegador cuando está listo.

Uso: python -m app.iniciar [--puerto 8000] [--sin-navegador] [--reiniciar]
(run.bat / run.sh lo llaman después de preparar el entorno virtual).
"""

from __future__ import annotations

import argparse
import socket
import threading
import time
import webbrowser


def _puerto_libre(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", puerto)) != 0


def _abrir_cuando_listo(url: str, puerto: int, espera_max: float = 30.0) -> None:
    inicio = time.time()
    while time.time() - inicio < espera_max:
        if not _puerto_libre(puerto):
            webbrowser.open(url)
            return
        time.sleep(0.3)


def main() -> None:
    import uvicorn

    p = argparse.ArgumentParser(description="Servidor CEP")
    p.add_argument("--puerto", type=int, default=8000)
    p.add_argument("--sin-navegador", action="store_true")
    p.add_argument("--reiniciar", action="store_true",
                   help="Borra data/cep.db y vuelve a cargar los datos de demostración")
    args = p.parse_args()

    if args.reiniciar:
        from app.db.sesion import DIR_DATOS

        bd = DIR_DATOS / "cep.db"
        if bd.exists():
            bd.unlink()
            print("  Base de datos reiniciada: se cargarán los datos de demostración.")

    puerto = args.puerto
    while not _puerto_libre(puerto):  # si 8000 está ocupado se prueba el siguiente
        puerto += 1
    url = f"http://127.0.0.1:{puerto}/"
    print(f"\n  CEP — servidor en {url}  (Ctrl+C para detener)\n")
    if not args.sin_navegador:
        threading.Thread(target=_abrir_cuando_listo, args=(url, puerto), daemon=True).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=puerto, log_level="warning")


if __name__ == "__main__":
    main()
