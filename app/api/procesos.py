"""Procesos y variables (alta y consulta) + catálogos de referencia."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import graficos_atributos as ga
from app.core import graficos_variables as gv
from app.core.constantes import tabla_completa
from app.core.reglas import PRESETS, catalogo
from app.db.modelos import Proceso, Variable
from app.db.sesion import obtener_sesion

from . import servicios as sv
from .esquemas import ProcesoCrear, VariableCrear

router = APIRouter(tags=["Procesos y variables"])


@router.get("/procesos", summary="Lista de procesos con sus variables")
def listar_procesos(db: Session = Depends(obtener_sesion)):
    return [sv.proceso_a_dict(p) for p in db.scalars(select(Proceso).order_by(Proceso.id))]


@router.post("/procesos", status_code=201, summary="Crear proceso")
def crear_proceso(datos: ProcesoCrear, db: Session = Depends(obtener_sesion)):
    d = datos.model_dump()
    d["nombre"] = d["nombre"].strip()
    if not d["nombre"]:
        raise HTTPException(422, "Escriba un nombre para el proceso.")
    p = Proceso(**d)
    db.add(p)
    db.commit()
    return sv.proceso_a_dict(p)


@router.get("/procesos/{proceso_id}", summary="Detalle de un proceso")
def ver_proceso(proceso_id: int, db: Session = Depends(obtener_sesion)):
    return sv.proceso_a_dict(sv.obtener_proceso(db, proceso_id))


@router.post("/procesos/{proceso_id}/variables", status_code=201, summary="Agregar variable a un proceso")
def crear_variable(proceso_id: int, datos: VariableCrear, db: Session = Depends(obtener_sesion)):
    sv.obtener_proceso(db, proceso_id)
    d = datos.model_dump()
    usuario = d.pop("usuario", None)
    v = sv.crear_variable(db, proceso_id, d, usuario)
    db.commit()
    return sv.variable_a_dict(v)


@router.delete("/variables/{variable_id}", summary="Eliminar una variable sin datos (corrige un alta equivocada)")
def eliminar_variable(variable_id: int, db: Session = Depends(obtener_sesion)):
    v = sv.obtener_variable(db, variable_id)
    if v.subgrupos:
        raise HTTPException(409, f"«{v.nombre}» ya tiene {len(v.subgrupos)} muestra(s) registradas: no se puede "
                                 "eliminar para no perder la trazabilidad.")
    db.delete(v)
    db.commit()
    return {"eliminada": variable_id}


@router.get("/asistente/carta", summary="Asistente: qué carta usar según lo que se registra")
def asistente_carta(que: str = Query(..., pattern="^(medida|defectuosos|defectos)$"),
                    n: int = Query(5, ge=1, le=10_000), tamano_constante: bool = True):
    """`medida` = se mide una característica continua; `defectuosos` = se cuentan unidades malas;
    `defectos` = se cuentan fallas (una unidad puede tener varias)."""
    if que == "medida":
        return gv.recomendar_carta_variables(n, tamano_constante)
    return ga.recomendar_grafico(que, tamano_constante, "proporcion")


@router.get("/variables/{variable_id}", summary="Configuración de una variable")
def ver_variable(variable_id: int, db: Session = Depends(obtener_sesion)):
    v = sv.obtener_variable(db, variable_id)
    activo = sv.limites_activos(db, v)
    return {**sv.variable_a_dict(v), "proceso": sv.proceso_a_dict(v.proceso, False),
            "limites_congelados": sv._limites_a_dict(activo) if activo else None,
            "hash": sv.hash_config(v)}


@router.get("/reglas", summary="Catálogo de reglas Nelson / Western Electric y presets")
def reglas():
    return {"catalogo": catalogo(), "presets": PRESETS}


@router.get("/constantes", summary="Tabla de constantes A2, A3, B3, B4, D3, D4, d2, d3, c4 (n = 2…25)")
def constantes():
    return tabla_completa()
