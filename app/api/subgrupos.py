"""Registro y consulta de subgrupos (mediciones o conteos con timestamp)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.modelos import Alarma, Subgrupo
from app.db.sesion import obtener_sesion

from . import servicios as sv
from .esquemas import DeshacerRegistro, SubgrupoCrear, SubgrupoExclusion

router = APIRouter(tags=["Subgrupos"])


@router.get("/variables/{variable_id}/subgrupos", summary="Historial de muestreo")
def listar(variable_id: int, fase: str | None = Query(None, description="I, II, archivo o anulado; vacío = todas"),
           limite: int | None = Query(None, ge=1), db: Session = Depends(obtener_sesion)):
    v = sv.obtener_variable(db, variable_id)
    fases = [fase] if fase else ["I", "II", "archivo", "anulado"]
    sgs = sv.subgrupos_de(db, v, fases, limite)
    alarmas = {}
    for a in db.scalars(select(Alarma).where(Alarma.variable_id == v.id, Alarma.subgrupo_id.is_not(None))):
        alarmas.setdefault(a.subgrupo_id, []).append(a.regla)
    return [{**sv.subgrupo_a_dict(sg, v), "reglas_violadas": alarmas.get(sg.id, [])} for sg in sgs]


@router.post("/variables/{variable_id}/subgrupos", status_code=201,
             summary="Registrar un subgrupo y evaluar las reglas (genera alarmas)")
def registrar(variable_id: int, datos: SubgrupoCrear, db: Session = Depends(obtener_sesion)):
    v = sv.obtener_variable(db, variable_id)
    sg, alarmas = sv.registrar_subgrupo(db, v, datos.valores, datos.conteo, datos.tamano, datos.timestamp,
                                        datos.operario or datos.usuario, datos.lote, datos.comentario)
    return {"subgrupo": sv.subgrupo_a_dict(sg, v), "alarmas_nuevas": [sv.alarma_a_dict(a) for a in alarmas]}


@router.post("/variables/{variable_id}/deshacer-ultimo",
             summary="Anular el último registro (error de carga) dentro de los primeros minutos")
def deshacer_ultimo(variable_id: int, datos: DeshacerRegistro, db: Session = Depends(obtener_sesion)):
    return sv.anular_ultimo_subgrupo(db, sv.obtener_variable(db, variable_id), datos.usuario, datos.motivo)


@router.patch("/subgrupos/{subgrupo_id}", summary="Excluir / reincorporar un subgrupo de la Fase I")
def excluir(subgrupo_id: int, datos: SubgrupoExclusion, db: Session = Depends(obtener_sesion)):
    sg = db.get(Subgrupo, subgrupo_id)
    if sg is None:
        raise HTTPException(404, "Subgrupo no encontrado.")
    sg = sv.excluir_subgrupo(db, sg, datos.excluido, datos.causa, datos.accion, datos.usuario)
    return sv.subgrupo_a_dict(sg, sg.variable)


@router.get("/variables/{variable_id}/simular-valores",
            summary="Valores de prueba para la captura (demostración)")
def simular(variable_id: int, delta: float = Query(0.0, description="Corrimiento en σ (variables) o fracción (atributos)"),
            semilla: int | None = None, db: Session = Depends(obtener_sesion)):
    return sv.simular_valores(db, sv.obtener_variable(db, variable_id), delta, semilla)
