"""Vista de operario: estado en vivo de la variable activa."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.sesion import obtener_sesion

from . import servicios as sv

router = APIRouter(tags=["Operario"])


@router.get("/variables/{variable_id}/operario",
            summary="Semáforo, carta en vivo (25 subgrupos), cuenta regresiva y resumen del turno")
def resumen(variable_id: int, db: Session = Depends(obtener_sesion)):
    return sv.resumen_operario(db, sv.obtener_variable(db, variable_id))
