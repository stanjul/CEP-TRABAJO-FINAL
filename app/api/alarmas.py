"""Alarmas: violaciones de reglas y eventos manuales, con causa/acción trazadas."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.modelos import Alarma
from app.db.sesion import obtener_sesion

from . import servicios as sv
from .esquemas import AlarmaActualizar, EventoManual
from .util import usuario_o_anonimo

router = APIRouter(tags=["Alarmas"])


@router.get("/alarmas", summary="Listar alarmas")
def listar(variable_id: int | None = None,
           estado: str | None = Query(None, description="abierta | en_investigacion | resuelta | pendientes"),
           limite: int = Query(200, ge=1, le=2000), db: Session = Depends(obtener_sesion)):
    q = select(Alarma)
    if variable_id:
        q = q.where(Alarma.variable_id == variable_id)
    if estado == "pendientes":
        q = q.where(Alarma.estado != "resuelta")
    elif estado:
        q = q.where(Alarma.estado == estado)
    return [sv.alarma_a_dict(a) for a in db.scalars(q.order_by(Alarma.creada.desc(), Alarma.id.desc()).limit(limite))]


@router.get("/alarmas/contador", summary="Cantidad de alarmas pendientes (para la campana)")
def contador(variable_id: int | None = None, db: Session = Depends(obtener_sesion)):
    q = select(Alarma).where(Alarma.estado != "resuelta")
    if variable_id:
        q = q.where(Alarma.variable_id == variable_id)
    alarmas = list(db.scalars(q))
    return {"pendientes": len(alarmas), "criticas": sum(a.severidad == "critica" for a in alarmas)}


@router.patch("/alarmas/{alarma_id}", summary="Registrar causa y acción / cambiar estado")
def actualizar(alarma_id: int, datos: AlarmaActualizar, db: Session = Depends(obtener_sesion)):
    a = db.get(Alarma, alarma_id)
    if a is None:
        raise HTTPException(404, "Alarma no encontrada.")
    return sv.alarma_a_dict(sv.actualizar_alarma(db, a, datos.estado, datos.causa, datos.accion, datos.usuario))


@router.post("/variables/{variable_id}/eventos", status_code=201,
             summary="Evento manual del operario: parada, retención de lote o anomalía")
def evento(variable_id: int, datos: EventoManual, db: Session = Depends(obtener_sesion)):
    v = sv.obtener_variable(db, variable_id)
    titulos = {"parada": "Parada de proceso", "retencion": "Retención de lote", "anomalia": "Anomalía reportada"}
    a = Alarma(variable_id=v.id, tipo=datos.tipo, regla="MANUAL", carta="",
               descripcion=f"{titulos[datos.tipo]}: {datos.descripcion}",
               severidad="critica" if datos.tipo in ("parada", "retencion") else "advertencia",
               usuario=usuario_o_anonimo(datos.usuario))
    db.add(a)
    db.commit()
    return sv.alarma_a_dict(a)
