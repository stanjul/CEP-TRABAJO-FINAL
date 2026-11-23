"""Módulo 5 — Capacidad del proceso de una variable."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.sesion import obtener_sesion

from . import servicios as sv

router = APIRouter(tags=["Capacidad"])


@router.get("/variables/{variable_id}/capacidad",
            summary="Cp, Cpk, Cpu, Cpl, fracción no conforme (ppm), histograma y veredicto")
def capacidad(variable_id: int, fase: str | None = Query(None, pattern="^(I|II)$"),
              metodo: str | None = Query(None, pattern="^(rbar|sbar|mr)$", description="Estimador de σ dentro"),
              db: Session = Depends(obtener_sesion)):
    return sv.capacidad_variable(db, sv.obtener_variable(db, variable_id), fase, metodo)
