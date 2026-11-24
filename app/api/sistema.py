"""Sistema: ubicación de la base, respaldos, restauración, copia descargable y datos de demostración."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import reporte_latex
from app.db import respaldos
from app.db.modelos import Proceso, Subgrupo, Variable
from app.db.semilla import sembrar
from app.db.sesion import obtener_sesion

router = APIRouter(prefix="/sistema", tags=["Sistema y respaldos"])
VERSION = "1.0.1"


class PedidoRespaldo(BaseModel):
    motivo: str = "manual"


def modo() -> str:
    """«escritorio» cuando corre como programa instalado (CEP.exe); «servidor» con run.bat."""
    return os.environ.get("CEP_MODO", "servidor")


@router.get("/info", summary="Ubicación y tamaño de la base, conteos y respaldos")
def info(db: Session = Depends(obtener_sesion)):
    try:
        base = respaldos.ruta_base()
    except respaldos.ErrorRespaldo:
        base = None
    contar = lambda m: db.scalar(select(func.count()).select_from(m)) or 0  # noqa: E731
    return {
        "version": VERSION, "modo": modo(), "carpeta_datos": str(base.parent) if base else None,
        "base": str(base) if base else None, "tamano_bytes": base.stat().st_size if base and base.exists() else 0,
        "procesos": contar(Proceso), "variables": contar(Variable), "muestras": contar(Subgrupo),
        "respaldos": respaldos.listar() if base else [], "latex": bool(reporte_latex.disponible()["pdflatex"]),
        "puede_abrir_carpeta": sys.platform == "win32" and modo() == "escritorio",
    }


@router.post("/respaldos", status_code=201, summary="Hacer un respaldo ahora")
def crear_respaldo(pedido: PedidoRespaldo | None = None):
    try:
        return respaldos.crear((pedido.motivo if pedido else None) or "manual")
    except respaldos.ErrorRespaldo as e:
        raise HTTPException(409, str(e))


@router.get("/respaldos/{nombre}/descargar", summary="Descargar un respaldo")
def descargar_respaldo(nombre: str):
    try:
        ruta = respaldos.ruta_respaldo(nombre)
    except respaldos.ErrorRespaldo as e:
        raise HTTPException(404, str(e))
    return FileResponse(ruta, media_type="application/octet-stream", filename=nombre)


@router.post("/respaldos/{nombre}/restaurar", summary="Volver la base al estado de un respaldo")
def restaurar_respaldo(nombre: str):
    try:
        return respaldos.restaurar(respaldos.ruta_respaldo(nombre))
    except respaldos.ErrorRespaldo as e:
        raise HTTPException(422, str(e))


@router.get("/base/descargar", summary="Descargar una copia de la base completa (para compartir o guardar)")
def descargar_base(tareas: BackgroundTasks):
    try:
        base = respaldos.ruta_base()
    except respaldos.ErrorRespaldo as e:
        raise HTTPException(409, str(e))
    tmp = Path(tempfile.mkdtemp(prefix="cep_copia_")) / "copia.db"
    respaldos._copiar(base, tmp)
    tareas.add_task(lambda: (tmp.unlink(missing_ok=True), tmp.parent.rmdir()))
    return FileResponse(tmp, media_type="application/octet-stream", filename=f"CEP_base_{datetime.now():%Y%m%d_%H%M}.db")


@router.post("/base/restaurar", summary="Reemplazar la base por un archivo .db (se respalda la actual antes)")
async def restaurar_desde_archivo(archivo: UploadFile = File(...)):
    datos = await archivo.read()
    with tempfile.TemporaryDirectory(prefix="cep_rest_") as d:
        tmp = Path(d) / "subida.db"
        tmp.write_bytes(datos)
        try:
            return respaldos.restaurar(tmp) | {"restaurado": archivo.filename}
        except respaldos.ErrorRespaldo as e:
            raise HTTPException(422, str(e))


@router.post("/demo", status_code=201, summary="Cargar los datos de demostración (solo con la base vacía)")
def cargar_demo(db: Session = Depends(obtener_sesion)):
    if db.scalar(select(Proceso.id).limit(1)) is not None:
        raise HTTPException(409, "La base ya tiene datos: la demostración solo se carga en una base vacía.")
    sembrar(db)
    return {"cargado": True}


@router.post("/abrir-carpeta", summary="Abrir la carpeta de datos en el Explorador (solo programa de escritorio)")
def abrir_carpeta():
    if sys.platform != "win32" or modo() != "escritorio":
        raise HTTPException(409, "Solo disponible en el programa de escritorio.")
    os.startfile(respaldos.ruta_base().parent)  # noqa: S606 (carpeta propia de la app)
    return {"abierta": True}
