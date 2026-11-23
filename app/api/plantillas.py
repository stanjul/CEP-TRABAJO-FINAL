"""Plantilla de carga: generar el Excel paramétrico, revisarlo y cargarlo (sin mapeos ni errores).

Flujo: GET /plantillas/sugerencia → POST /plantillas/generar (descarga .xlsx) → el usuario la
llena → POST /plantillas/revisar (informe, no guarda nada) → POST /plantillas/importar.

Reglas de carga:
- El número de muestra de la plantilla es el número real: subir el mismo archivo otra vez no
  duplica (las muestras que ya existen se saltan).
- Cada muestra entra en su fase: con la variable en Fase I solo se cargan las del bloque «para
  establecer los límites»; con límites fijados (Fase II), solo las de monitoreo. Las demás se
  informan y quedan para una carga posterior.
- Las variables nuevas de la plantilla se crean al cargar (si el usuario lo confirma); su id se
  recuerda en el ajuste `plantilla:<id>` para que las cargas siguientes las encuentren.
"""

from __future__ import annotations

import hashlib
import unicodedata
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import graficos_atributos as ga
from app.core import graficos_variables as gv
from app.core import plantilla as pl
from app.db.modelos import Ajuste, Proceso, Subgrupo, ahora
from app.db.sesion import obtener_sesion

from . import servicios as sv

router = APIRouter(prefix="/plantillas", tags=["Plantilla de carga"])
MUESTRAS_BASE = 25  # muestras recomendadas para establecer los límites (Montgomery: 20–25)


class VariablePlantilla(BaseModel):
    """Una variable existente (`id`) o una nueva (nombre, tipo…), con cuántas muestras incluir."""

    id: int | None = None
    nombre: str | None = None
    unidad: str = ""
    que: str | None = Field(None, pattern="^(medida|defectuosos|defectos)$")
    n: int = Field(5, ge=1, le=10_000)
    tamano_constante: bool = True
    decimales: int = Field(2, ge=0, le=6)
    lei: float | None = None
    objetivo: float | None = None
    les: float | None = None
    frecuencia_min: int = Field(60, ge=1, le=7 * 24 * 60)
    fase_i: int = Field(MUESTRAS_BASE, ge=0, le=500)
    fase_ii: int = Field(0, ge=0, le=2000)


class PedidoPlantilla(BaseModel):
    proceso_id: int | None = None
    proceso_nombre: str | None = None
    proceso_linea: str | None = None
    variables: list[VariablePlantilla] = Field(min_length=1)
    lote: bool = True
    operario: bool = True
    observaciones: bool = True
    fecha_inicio: datetime | None = None


# ---------------------------------------------------------------------------
# Sugerencias y generación
# ---------------------------------------------------------------------------

def _siguiente(db: Session, v) -> tuple[int, datetime | None]:
    """Próximo número de muestra y momento sugerido (último registro + frecuencia)."""
    maximo = db.scalar(select(func.max(Subgrupo.numero)).where(Subgrupo.variable_id == v.id)) or 0
    ultimo = sv.ultimo_subgrupo(db, v)
    return maximo + 1, (ultimo.timestamp + timedelta(minutes=v.frecuencia_min)) if ultimo else None


@router.get("/sugerencia", summary="Variables del proceso con la cantidad de muestras sugerida")
def sugerencia(proceso_id: int, db: Session = Depends(obtener_sesion)):
    p = sv.obtener_proceso(db, proceso_id)
    salida = []
    for v in p.variables:
        en_i = len(sv.subgrupos_de(db, v, ("I",)))
        en_ii = len(sv.subgrupos_de(db, v, ("II",)))
        siguiente, _ = _siguiente(db, v)
        salida.append({**sv.variable_a_dict(v), "muestras_fase_i": en_i, "muestras_fase_ii": en_ii,
                       "siguiente_numero": siguiente,
                       "fase_i_sugerida": max(0, MUESTRAS_BASE - en_i) if v.fase == "I" else 0,
                       "fase_ii_sugerida": 0 if v.fase == "I" else MUESTRAS_BASE})
    return {"proceso": sv.proceso_a_dict(p, False), "variables": salida, "muestras_base": MUESTRAS_BASE}


def _tipo_carta(que: str, n: int, constante: bool) -> str:
    if que == "medida":
        return gv.recomendar_carta_variables(n, constante)["carta"]
    return ga.recomendar_grafico(que, constante, "proporcion")["carta"]


def armar_spec(db: Session, pedido: PedidoPlantilla) -> dict:
    """Traduce el pedido a la especificación del core (variables existentes leídas de la BD)."""
    if pedido.proceso_id:
        p = sv.obtener_proceso(db, pedido.proceso_id)
        proceso = {"id": p.id, "nombre": p.nombre, "linea": p.linea}
    else:
        nombre = (pedido.proceso_nombre or "").strip()
        if not nombre:
            raise HTTPException(422, "Elige un proceso o escribe el nombre del proceso nuevo.")
        proceso = {"id": None, "nombre": nombre, "linea": (pedido.proceso_linea or "").strip() or None}
    inicio_defecto = (pedido.fecha_inicio or ahora()).replace(second=0, microsecond=0)
    variables, nombres = [], set()
    for i, x in enumerate(pedido.variables):
        if x.fase_i + x.fase_ii == 0:
            continue
        if x.id is not None:
            v = sv.obtener_variable(db, x.id)
            if proceso["id"] is not None and v.proceso_id != proceso["id"]:
                raise HTTPException(422, f"«{v.nombre}» no pertenece al proceso elegido.")
            siguiente, momento = _siguiente(db, v)
            d = sv.variable_a_dict(v)
            item = {**{k: d[k] for k in ("nombre", "unidad", "tipo_carta", "n", "decimales", "lei", "objetivo", "les",
                                         "frecuencia_min")}, "id": v.id, "clave": f"v{v.id}",
                    "inicio_numero": siguiente, "fecha_inicio": (momento or inicio_defecto).isoformat()}
        else:
            nombre = (x.nombre or "").strip()
            if not nombre or not x.que:
                raise HTTPException(422, f"Variable nueva {i + 1}: escribe el nombre y cómo se registra.")
            tipo = _tipo_carta(x.que, x.n, x.tamano_constante)
            if x.que == "medida" and x.lei is not None and x.les is not None and x.lei >= x.les:
                raise HTTPException(422, f"«{nombre}»: el mínimo aceptado debe ser menor que el máximo.")
            medida = x.que == "medida"
            item = {"id": None, "clave": f"n{i + 1}", "nombre": nombre, "unidad": x.unidad.strip(), "tipo_carta": tipo,
                    "n": 1 if tipo == "imr" else x.n, "decimales": x.decimales if medida else 0,
                    "lei": x.lei if medida else None, "objetivo": x.objetivo if medida else None,
                    "les": x.les if medida else None, "frecuencia_min": x.frecuencia_min, "inicio_numero": 1,
                    "fecha_inicio": inicio_defecto.isoformat()}
        if item["nombre"].lower() in nombres:
            raise HTTPException(422, f"La variable «{item['nombre']}» está repetida en la plantilla.")
        nombres.add(item["nombre"].lower())
        item.update({"fase_i": x.fase_i, "fase_ii": x.fase_ii})
        variables.append(item)
    if not variables:
        raise HTTPException(422, "Indica al menos una muestra para alguna variable.")
    return {"id": uuid.uuid4().hex[:12], "generada": ahora().isoformat(), "proceso": proceso,
            "opciones": {"lote": pedido.lote, "operario": pedido.operario, "observaciones": pedido.observaciones},
            "variables": variables}


@router.post("/generar", summary="Descargar la plantilla Excel paramétrica")
def generar(pedido: PedidoPlantilla, db: Session = Depends(obtener_sesion)):
    spec = armar_spec(db, pedido)
    datos = pl.construir_plantilla(spec)
    # Los encabezados HTTP solo admiten ASCII: nombre sin tildes + filename* (RFC 5987) con el original.
    sin_tildes = unicodedata.normalize("NFKD", spec["proceso"]["nombre"]).encode("ascii", "ignore").decode()
    seguro = "".join(ch if ch.isalnum() else "_" for ch in sin_tildes)[:40].strip("_") or "proceso"
    nombre = f"CEP_plantilla_{seguro}_{ahora():%Y%m%d}.xlsx"
    original = quote(f"CEP_plantilla_{spec['proceso']['nombre']}_{ahora():%Y%m%d}.xlsx")
    return StreamingResponse(iter([datos]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename=\"{nombre}\"; filename*=UTF-8''{original}"})


# ---------------------------------------------------------------------------
# Revisión y carga
# ---------------------------------------------------------------------------

def _clave_ajuste(id_plantilla: str) -> str:
    return f"plantilla:{id_plantilla}"


def _ids_creados(db: Session, id_plantilla: str) -> dict:
    aj = db.get(Ajuste, _clave_ajuste(id_plantilla))
    return dict(aj.valor) if aj else {}


def planificar(db: Session, leido: dict) -> dict:
    """Decide qué se carga de cada variable (sin guardar): nuevas, fase de cada muestra, repetidas."""
    creados = _ids_creados(db, leido["id"])
    proc = leido["proceso"]
    if proc.get("id") is not None and db.get(Proceso, proc["id"]) is None:
        raise HTTPException(409, "El proceso de esta plantilla ya no existe en la aplicación.")
    plan = {"id": leido["id"], "proceso": proc, "variables": [], "total_cargar": 0, "total_errores": 0}
    for x in leido["variables"]:
        vid = x["id"] or creados.get(x["clave"])
        v = sv.obtener_variable(db, vid) if vid else None
        fase = v.fase if v else "I"
        existentes = {n for (n,) in db.execute(select(Subgrupo.numero).where(Subgrupo.variable_id == v.id))} if v else set()
        cargar, ya, otra_fase = [], [], []
        for m in x["muestras"]:
            if m["numero"] in existentes:
                ya.append(m["numero"])
            elif m["fase"] != fase:
                otra_fase.append(m["numero"])
            else:
                cargar.append(m)
        avisos = list(x["avisos"])
        if otra_fase:
            avisos.append({"numero": None, "texto": (
                f"{len(otra_fase)} muestras de monitoreo quedan para después: primero hay que fijar los límites "
                "(Ingeniería → Gráficos → «Congelar límites») y volver a subir el archivo."
                if fase == "I" else
                f"{len(otra_fase)} muestras del bloque «para establecer los límites» no se cargan porque los límites ya "
                "están fijados (la variable está en monitoreo).")})
        plan["variables"].append({
            "clave": x["clave"], "id": v.id if v else None, "nombre": x["nombre"], "hoja": x["hoja"],
            "tipo_carta": x["tipo_carta"], "nueva": v is None, "fase": fase, "cargar": cargar,
            "ya_cargadas": len(ya), "otra_fase": len(otra_fase), "vacias": x["vacias"], "errores": x["errores"],
            "avisos": avisos, "definicion": {k: x[k] for k in ("nombre", "unidad", "tipo_carta", "n", "decimales", "lei",
                                                                "objetivo", "les", "frecuencia_min")},
        })
        plan["total_cargar"] += len(cargar)
        plan["total_errores"] += len(x["errores"])
    return plan


def _resumen(plan: dict) -> dict:
    """Plan sin las muestras completas (para mostrar en pantalla)."""
    return {**plan, "variables": [{**{k: x for k, x in v.items() if k not in ("cargar", "definicion")},
                                   "a_cargar": len(v["cargar"]),
                                   "numeros": [m["numero"] for m in v["cargar"]]} for v in plan["variables"]]}


async def _leer(archivo: UploadFile) -> tuple[bytes, dict]:
    datos = await archivo.read()
    try:
        return datos, pl.leer_plantilla(datos)
    except pl.ErrorPlantilla as e:
        raise HTTPException(422, str(e))


@router.post("/revisar", summary="Revisar una plantilla llenada (no guarda nada)")
async def revisar(archivo: UploadFile = File(...), db: Session = Depends(obtener_sesion)):
    _, leido = await _leer(archivo)
    return _resumen(planificar(db, leido))


@router.post("/importar", summary="Cargar las muestras válidas de una plantilla llenada")
async def importar(archivo: UploadFile = File(...), usuario: str | None = Form(None),
                   crear_nuevas: bool = Form(True), db: Session = Depends(obtener_sesion)):
    datos, leido = await _leer(archivo)
    plan = planificar(db, leido)
    huella = hashlib.sha256(datos).hexdigest()
    motivo = f"Plantilla «{archivo.filename}» (SHA-256 {huella[:12]}…)"
    proc = plan["proceso"]
    if proc.get("id") is None:
        # Proceso nuevo: se reutiliza si ya se creó en una carga anterior de esta plantilla.
        creados = _ids_creados(db, plan["id"])
        p = db.get(Proceso, creados["__proceso__"]) if creados.get("__proceso__") else None
        if p is None:
            if not crear_nuevas:
                raise HTTPException(409, "La plantilla trae un proceso nuevo: confirma que quieres crearlo.")
            p = Proceso(nombre=proc["nombre"], linea=proc.get("linea"))
            db.add(p)
            db.flush()
        proceso_id = p.id
    else:
        proceso_id = proc["id"]
    creados = _ids_creados(db, plan["id"])
    if proc.get("id") is None:
        creados["__proceso__"] = proceso_id
    resultado = []
    for x in plan["variables"]:
        if x["nueva"]:
            if not crear_nuevas:
                resultado.append({"nombre": x["nombre"], "cargadas": 0, "omitida": "variable nueva no confirmada"})
                continue
            if not x["cargar"] and not x["errores"]:
                continue
            v = sv.crear_variable(db, proceso_id, x["definicion"], usuario, f"Creada desde la plantilla: {motivo}")
            creados[x["clave"]] = v.id
        else:
            v = sv.obtener_variable(db, x["id"])
        cargadas = 0
        for m in x["cargar"]:
            sv.registrar_subgrupo(db, v, valores=m.get("valores"), conteo=m.get("conteo"), tamano=m.get("tamano"),
                                  timestamp=datetime.fromisoformat(m["timestamp"]), operario=m.get("operario"),
                                  lote=m.get("lote"), comentario=m.get("obs"), origen="plantilla",
                                  evaluar=v.fase == "II", numero=m["numero"])
            cargadas += 1
        if cargadas:
            sv.registrar_cambio(db, v, "importacion", None, f"{cargadas} muestras ({x['hoja']})", usuario, motivo)
        resultado.append({"id": v.id, "nombre": v.nombre, "nueva": x["nueva"], "cargadas": cargadas,
                          "errores": len(x["errores"]), "otra_fase": x["otra_fase"], "ya_cargadas": x["ya_cargadas"]})
    aj = db.get(Ajuste, _clave_ajuste(plan["id"]))
    if aj:
        aj.valor = creados
    elif creados:
        db.add(Ajuste(clave=_clave_ajuste(plan["id"]), valor=creados))
    db.commit()
    return {"variables": resultado, "total": sum(r.get("cargadas", 0) for r in resultado), "sha256": huella}
