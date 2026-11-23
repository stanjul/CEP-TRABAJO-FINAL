"""Routers de la API REST (prefijo /api)."""

from fastapi import APIRouter

from . import (alarmas, atributos, capacidad, configuracion, datos, diseno, muestreo, operario, plantillas, procesos,
               reportes, subgrupos, supuestos, variables)

router = APIRouter(prefix="/api")
for modulo in (procesos, configuracion, subgrupos, operario, alarmas, datos, plantillas, variables, atributos, supuestos,
               capacidad, diseno, muestreo, reportes):
    router.include_router(modulo.router)
