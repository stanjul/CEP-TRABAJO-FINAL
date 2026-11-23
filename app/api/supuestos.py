"""Módulo 4 — Supuestos: normalidad, independencia y rachas de una variable."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.sesion import obtener_sesion

from . import servicios as sv

router = APIRouter(tags=["Supuestos"])


@router.get("/variables/{variable_id}/supuestos",
            summary="Shapiro-Wilk, Anderson-Darling, Lilliefors, Q-Q, ACF, Ljung-Box, Durbin-Watson, rachas, Box-Cox")
def supuestos(variable_id: int, fase: str | None = Query(None, pattern="^(I|II)$"),
              alfa: float = Query(0.05, gt=0, lt=0.5), rezagos: int = Query(20, ge=1, le=60),
              db: Session = Depends(obtener_sesion)):
    return sv.supuestos_variable(db, sv.obtener_variable(db, variable_id), fase, alfa, rezagos)
