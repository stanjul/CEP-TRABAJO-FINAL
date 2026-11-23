"""Módulo 2 — Cartas de control (variables y atributos sobre una variable de la BD), Fase I y II."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.constantes import constantes
from app.db.sesion import obtener_sesion

from . import servicios as sv
from .esquemas import AccionFase, SimularExclusion

router = APIRouter(tags=["Cartas de control"])


@router.get("/variables/{variable_id}/carta", summary="Carta de control de la fase actual o la indicada")
def carta(variable_id: int, fase: str | None = Query(None, pattern="^(I|II)$"),
          ultimos: int | None = Query(None, ge=1), db: Session = Depends(obtener_sesion)):
    v = sv.obtener_variable(db, variable_id)
    res = sv.carta_variable(db, v, fase, ultimos)
    if v.tipo_carta in ("xbar_r", "xbar_s") and 2 <= v.n <= 25:
        res.setdefault("constantes", constantes(v.n).a_dict())
    return res


@router.post("/variables/{variable_id}/simular-exclusion",
             summary="Impacto de excluir subgrupos (Δ límites, Cpk antes/después) sin guardar")
def simular_exclusion(variable_id: int, datos: SimularExclusion, db: Session = Depends(obtener_sesion)):
    return sv.simular_exclusion(db, sv.obtener_variable(db, variable_id), datos.excluidos)


@router.post("/variables/{variable_id}/congelar", summary="Congelar los límites de la Fase I y pasar a Fase II")
def congelar(variable_id: int, datos: AccionFase, db: Session = Depends(obtener_sesion)):
    return sv.congelar_limites(db, sv.obtener_variable(db, variable_id), datos.usuario, datos.motivo)


@router.post("/variables/{variable_id}/volver-fase-i", summary="Archivar límites y volver a la Fase I")
def volver(variable_id: int, datos: AccionFase, db: Session = Depends(obtener_sesion)):
    return sv.volver_fase_i(db, sv.obtener_variable(db, variable_id), datos.usuario, datos.motivo,
                            datos.usar_fase_ii_como_base)
