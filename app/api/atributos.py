"""Módulo 3 — Atributos: asistente de selección y cálculo directo de cartas p, np, c, u.

Las cartas de variables de la BD con tipo p/np/c/u se obtienen con /variables/{id}/carta.
"""

from fastapi import APIRouter, HTTPException, Query

from app.core import graficos_atributos as ga
from app.core.reglas import PRESETS

from .esquemas import CartaAtributosAdHoc

router = APIRouter(prefix="/atributos", tags=["Atributos"])


@router.get("/recomendar", summary="Asistente: qué carta de atributos usar")
def recomendar(tipo_dato: str = Query(..., pattern="^(defectuosos|defectos)$"),
               tamano_constante: bool = True, interes: str = Query("proporcion", pattern="^(proporcion|conteo)$")):
    return ga.recomendar_grafico(tipo_dato, tamano_constante, interes)


@router.post("/calcular", summary="Calcular una carta de atributos con datos enviados (sin guardar)")
def calcular(datos: CartaAtributosAdHoc):
    try:
        return ga.calcular_carta_atributos(datos.tipo, datos.conteos, datos.tamanos, excluidos=datos.excluidos,
                                           k=datos.k, reglas=datos.reglas or PRESETS["nelson"])
    except (ValueError, IndexError) as e:
        raise HTTPException(422, str(e))
