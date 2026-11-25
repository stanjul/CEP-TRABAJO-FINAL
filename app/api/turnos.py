"""Turnos reales: estado actual, inicio y fin a mano, historial.

Los turnos programados (nombre, horas, días, arranque) se configuran en /ajustes/turnos. Los turnos
reales se abren y cierran solos según esa programación cada vez que se consulta o se registra una
muestra; estos endpoints permiten además iniciarlos o terminarlos a mano.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.sesion import obtener_sesion

from . import servicios as sv
from .esquemas import AccionTurno

router = APIRouter(prefix="/turnos", tags=["Turnos"])


@router.get("/estado", summary="Turno abierto, próximo turno y programación")
def estado(db: Session = Depends(obtener_sesion)):
    return sv.estado_turno(db)


@router.post("/iniciar", summary="Iniciar un turno a mano")
def iniciar(datos: AccionTurno, db: Session = Depends(obtener_sesion)):
    return sv.iniciar_turno(db, datos.nombre, datos.usuario)


@router.post("/terminar", summary="Terminar a mano el turno abierto")
def terminar(datos: AccionTurno, db: Session = Depends(obtener_sesion)):
    return sv.terminar_turno(db, datos.usuario)


@router.get("", summary="Historial de turnos (los más recientes primero)")
def historial(limite: int = Query(30, ge=1, le=500), db: Session = Depends(obtener_sesion)):
    return sv.historial_turnos(db, limite)
