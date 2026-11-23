"""Configuración por variable (especificaciones, n, frecuencia, reglas…) con historial de cambios."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.modelos import CambioConfiguracion, LimitesCarta
from app.db.sesion import obtener_sesion

from . import servicios as sv
from .esquemas import ModoDemo, PlanMuestreo, Turno, VariableActualizar

router = APIRouter(tags=["Configuración"])


@router.patch("/variables/{variable_id}", summary="Modificar la configuración (queda en el historial)")
def actualizar(variable_id: int, datos: VariableActualizar, db: Session = Depends(obtener_sesion)):
    v = sv.obtener_variable(db, variable_id)
    cambios = datos.model_dump(exclude_unset=True, exclude={"usuario", "justificacion", "borrar"})
    return sv.actualizar_configuracion(db, v, cambios, datos.borrar, datos.usuario, datos.justificacion)


@router.get("/variables/{variable_id}/plan", summary="Plan de muestreo: vigente vs. propuesto, con ARL/ATS y carga")
def ver_plan(variable_id: int, n: int | None = Query(None, ge=1, le=10_000),
             frecuencia_min: float | None = Query(None, gt=0, le=24 * 60), k: float | None = Query(None, ge=1, le=6),
             delta: float = Query(1.0, ge=0, le=6, description="Corrimiento a detectar (en σ), cartas por variables"),
             sigma: float | None = Query(None, gt=0, description="σ propuesta por el ingeniero"),
             centro: float | None = Query(None, gt=0, description="Nivel de defectos esperado (atributos sin datos)"),
             centro_1: float | None = Query(None, gt=0, description="Nivel de defectos a detectar (atributos)"),
             db: Session = Depends(obtener_sesion)):
    v = sv.obtener_variable(db, variable_id)
    try:
        return sv.plan_muestreo(db, v, n, frecuencia_min, k, delta, centro_1, sigma, centro)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/variables/{variable_id}/plan", summary="Guardar el plan de muestreo (queda en el historial)")
def guardar_plan(variable_id: int, datos: PlanMuestreo, db: Session = Depends(obtener_sesion)):
    v = sv.obtener_variable(db, variable_id)
    return sv.aplicar_plan(db, v, datos.n, datos.frecuencia_min, datos.k_sigma, datos.sigma_monitoreo,
                           datos.borrar_sigma, datos.usuario, datos.justificacion, datos.reiniciar_fase_i)


@router.get("/variables/{variable_id}/historial", summary="Historial de cambios (auditoría)")
def historial(variable_id: int, parametro: str | None = Query(None, description="Filtra por parámetro (contiene)"),
              texto: str | None = Query(None, description="Busca en usuario, justificación o valores"),
              db: Session = Depends(obtener_sesion)):
    sv.obtener_variable(db, variable_id)
    q = select(CambioConfiguracion).where(CambioConfiguracion.variable_id == variable_id)
    if parametro:
        q = q.where(CambioConfiguracion.parametro.contains(parametro))
    cambios = [sv.cambio_a_dict(c) for c in db.scalars(q.order_by(CambioConfiguracion.id.desc()))]
    if texto:
        t = texto.lower()
        cambios = [c for c in cambios if any(t in str(c[k] or "").lower()
                                             for k in ("usuario", "justificacion", "valor_anterior", "valor_nuevo", "hash"))]
    return cambios


@router.get("/variables/{variable_id}/limites", summary="Historial de límites congelados")
def historial_limites(variable_id: int, db: Session = Depends(obtener_sesion)):
    sv.obtener_variable(db, variable_id)
    q = select(LimitesCarta).where(LimitesCarta.variable_id == variable_id).order_by(LimitesCarta.id.desc())
    return [sv._limites_a_dict(l) for l in db.scalars(q)]


@router.get("/ajustes/modo-demo", summary="¿Está activo el modo demostración?")
def ver_modo_demo(db: Session = Depends(obtener_sesion)):
    return {"activo": sv.modo_demo(db)}


@router.put("/ajustes/modo-demo", summary="Activar o desactivar el modo demostración (valores simulados)")
def poner_modo_demo(datos: ModoDemo, db: Session = Depends(obtener_sesion)):
    return {"activo": sv.guardar_modo_demo(db, datos.activo)}


@router.get("/ajustes/turnos", summary="Turnos de trabajo")
def ver_turnos(db: Session = Depends(obtener_sesion)):
    return sv.obtener_turnos(db)


@router.put("/ajustes/turnos", summary="Reemplazar los turnos de trabajo")
def guardar_turnos(turnos: list[Turno], db: Session = Depends(obtener_sesion)):
    return sv.guardar_turnos(db, [t.model_dump() for t in turnos])
