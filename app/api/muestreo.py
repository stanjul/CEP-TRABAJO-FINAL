"""Módulo 7 — Muestreo de aceptación: curvas OC/AOQ/ATI, diseño del plan y registro de lotes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import muestreo_aceptacion as ma
from app.core.reportes import conclusiones_muestreo
from app.db.modelos import LoteInspeccion
from app.db.sesion import obtener_sesion

from .esquemas import DisenoPlan, LoteCrear
from .util import usuario_o_anonimo

router = APIRouter(prefix="/muestreo", tags=["Muestreo de aceptación"])


@router.get("/curvas", summary="Curvas OC (binomial / hipergeométrica / Poisson), AOQ, ATI y AOQL")
def curvas(n: int = Query(..., ge=1), c: int = Query(..., ge=0), N: int | None = Query(None, ge=2),
           aql: float | None = Query(None, gt=0, lt=1), ltpd: float | None = Query(None, gt=0, lt=1),
           p_max: float | None = Query(None, gt=0, le=1), puntos: int = Query(101, ge=11, le=501)):
    if N is not None and N < n:
        raise HTTPException(422, "N debe ser mayor o igual que n.")
    if c >= n:
        raise HTTPException(422, "c debe ser menor que n.")
    r = ma.curvas(n, c, N, p_max, puntos, aql, ltpd)
    r["conclusiones"] = conclusiones_muestreo(r)
    return r


@router.post("/disenar", summary="Plan simple (n, c) a partir de AQL, LTPD, α y β")
def disenar(datos: DisenoPlan):
    try:
        return ma.disenar_plan(datos.aql, datos.ltpd, datos.alfa, datos.beta, datos.modelo, datos.N)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/decidir", summary="Dictamen de un lote (d ≤ c) con IC de Wilson, sin guardar")
def decidir(d: int = Query(..., ge=0), n: int = Query(..., ge=1), c: int = Query(..., ge=0)):
    try:
        return ma.decidir_lote(d, n, c)
    except ValueError as e:
        raise HTTPException(422, str(e))


def _lote_dict(l: LoteInspeccion) -> dict:
    return {"id": l.id, "codigo": l.codigo, "descripcion": l.descripcion, "fecha": l.fecha, "N": l.N, "n": l.n,
            "c": l.c, "defectos": l.defectos, "p_hat": l.p_hat, "dictamen": l.dictamen, "usuario": l.usuario}


@router.get("/lotes", summary="Historial de lotes inspeccionados")
def lotes(db: Session = Depends(obtener_sesion)):
    filas = [_lote_dict(l) for l in db.scalars(select(LoteInspeccion).order_by(LoteInspeccion.id.desc()))]
    aceptados = sum(f["dictamen"] == "ACEPTADO" for f in filas)
    return {"lotes": filas, "tasa_aceptacion": aceptados / len(filas) if filas else None}


@router.post("/lotes", status_code=201, summary="Registrar la inspección de un lote")
def registrar_lote(datos: LoteCrear, db: Session = Depends(obtener_sesion)):
    if datos.n > datos.N or datos.defectos > datos.n:
        raise HTTPException(422, "Debe cumplirse d ≤ n ≤ N.")
    dec = ma.decidir_lote(datos.defectos, datos.n, datos.c)
    l = LoteInspeccion(codigo=datos.codigo, descripcion=datos.descripcion, N=datos.N, n=datos.n, c=datos.c,
                       defectos=datos.defectos, p_hat=dec["p_hat"], dictamen=dec["dictamen"],
                       usuario=usuario_o_anonimo(datos.usuario))
    db.add(l)
    db.commit()
    return {**_lote_dict(l), "ic95": dec["ic95"], "condicion": dec["condicion"]}
