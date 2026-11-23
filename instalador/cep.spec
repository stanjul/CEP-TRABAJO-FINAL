# -*- mode: python ; coding: utf-8 -*-
"""Receta de PyInstaller para CEP.exe (programa de escritorio). La usa construir.bat.

Empaqueta Python, las librerías y la app en una carpeta (modo «onedir»: abre en pocos segundos;
el instalador de Inno Setup la oculta al usuario). Los archivos que la app lee de disco se copian
con la misma estructura de carpetas, así funcionan las rutas relativas a __file__.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

RAIZ = Path(SPECPATH).parent

datas = [
    (str(RAIZ / "app" / "web" / "templates"), "app/web/templates"),
    (str(RAIZ / "app" / "web" / "static"), "app/web/static"),
    (str(RAIZ / "app" / "core" / "plantillas"), "app/core/plantillas"),
    (str(RAIZ / "datos_prueba" / "proceso_simulado.csv"), "datos_prueba"),  # datos de demostración
]

hiddenimports = collect_submodules("app") + collect_submodules("uvicorn")

a = Analysis(
    [str(RAIZ / "app" / "escritorio.py")],
    pathex=[str(RAIZ)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "_pytest", "tkinter", "IPython", "jupyter", "notebook", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CEP",
    console=False,  # sin ventana de consola
    icon=str(RAIZ / "instalador" / "cep.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="CEP")
