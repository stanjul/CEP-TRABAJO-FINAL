"""Módulo 6 — Diseño de la carta X̄: ARL0, ARL1, ATS, curva ARL y Monte Carlo."""

from fastapi import APIRouter, Query

from app.core import diseno_arl as d
from app.core.reportes import conclusiones_arl

from .esquemas import SimulacionARL

router = APIRouter(prefix="/diseno", tags=["Diseño ARL / ATS"])


@router.get("/arl", summary="β, ARL0, ARL1 y ATS para (k, n, h, δ)")
def arl(k: float = Query(3.0, gt=0), n: int = Query(5, ge=1, le=100), h: float = Query(1.0, gt=0),
        delta: float = Query(1.0, ge=0)):
    r = d.diseno(k, n, h, delta)
    r["conclusiones"] = conclusiones_arl(r)
    return r


@router.get("/curva", summary="Curva ARL1 / ATS1 vs δ")
def curva(k: float = Query(3.0, gt=0), n: int = Query(5, ge=1, le=100), h: float = Query(1.0, gt=0),
          delta_max: float = Query(3.0, gt=0, le=6), puntos: int = Query(31, ge=5, le=301),
          comparar: str | None = Query(None, description="Otros n separados por coma, p. ej. 3,10")):
    deltas = [round(delta_max * i / (puntos - 1), 4) for i in range(puntos)]
    otros = [int(x) for x in comparar.split(",") if x.strip().isdigit()] if comparar else []
    return d.curva_arl(k, n, deltas, h, otros)


@router.post("/simular", summary="Simulación Monte Carlo del ARL")
def simular(datos: SimulacionARL):
    return d.simular_arl(datos.k, datos.n, datos.delta, datos.replicas, datos.semilla)
