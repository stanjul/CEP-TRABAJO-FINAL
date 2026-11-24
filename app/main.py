"""Aplicación FastAPI: API REST en /api, documentación en /docs y la interfaz web (Fase 3).

Arranque: `run.bat` / `run.sh`, o bien
    .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import router as api_router
from app.api.util import JSONSeguro
from app.db import sesion
from app.db.semilla import sembrar
from app.web.rutas import router as web_router

WEB = Path(__file__).resolve().parent / "web"


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    """Al iniciar: crea las tablas y carga los datos de demostración si la base está vacía.

    En el programa de escritorio (CEP_SIN_DEMO=1) la base arranca vacía: la demostración se carga
    a pedido desde la interfaz (POST /api/sistema/demo).
    """
    sesion.crear_tablas()
    if os.environ.get("CEP_SIN_DEMO") != "1":
        with sesion.SesionLocal() as db:
            sembrar(db)
    yield


app = FastAPI(
    title="CEP — Control Estadístico de Procesos",
    description="API del trabajo final de CEP: cartas de control, supuestos, capacidad, diseño ARL, "
                "muestreo de aceptación y reportes.",
    version="1.0.1",
    default_response_class=JSONSeguro,
    lifespan=ciclo_de_vida,
)
app.include_router(api_router)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")


@app.middleware("http")
async def revalidar_estaticos(request, call_next):
    """Los JS/CSS propios se revalidan en cada carga (ETag → 304 si no cambiaron) para que una
    actualización de la app no quede oculta por la caché del navegador. vendor/ se cachea normal."""
    respuesta = await call_next(request)
    ruta = request.url.path
    if ruta.startswith(("/static/js/", "/static/css/")):
        respuesta.headers["Cache-Control"] = "no-cache"
    return respuesta


@app.get("/api/salud", tags=["Sistema"], summary="Estado del servidor")
def salud():
    return {"estado": "ok", "base_de_datos": sesion.engine.url.database, "app": "CEP",
            "modo": os.environ.get("CEP_MODO", "servidor")}
