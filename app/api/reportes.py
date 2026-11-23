"""Módulo 8 — Reportes: vista previa, generación de PDF / Excel, historial y verificación SHA-256.

Los archivos se guardan en `<carpeta de la base>/reportes/` (por defecto data/reportes) y se
registran en la tabla `reportes` con su hash para poder verificar que no se modificaron.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import diseno_arl, reporte_latex
from app.core.reportes import MODULOS, NOMBRES_CARTA, PLANTILLAS, _f, construir_excel, construir_pdf, generar_conclusiones
from app.db import sesion
from app.db.modelos import Alarma, CambioConfiguracion, LoteInspeccion, ReporteGenerado, ahora
from app.db.sesion import obtener_sesion

from . import servicios as sv
from .util import limpiar_json, usuario_o_anonimo

router = APIRouter(prefix="/reportes", tags=["Reportes"])


class PedidoReporte(BaseModel):
    variable_id: int
    plantilla: Literal["integral", "capacidad", "control", "auditoria"] = "integral"
    modulos: list[str] | None = Field(None, description=f"Subconjunto de {list(MODULOS)}; vacío = los de la plantilla")
    formato: Literal["pdf", "xlsx"] = "pdf"
    usuario: str | None = None


def carpeta_reportes() -> Path:
    """Carpeta junto a la base SQLite (así los tests con base temporal no escriben en data/)."""
    bd = sesion.engine.url.database
    base = Path(bd).parent if bd and bd != ":memory:" else sesion.DIR_DATOS
    carpeta = base / "reportes"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


# ---------------------------------------------------------------------------
# Armado del contenido (datos → diccionario que consumen construir_pdf / construir_excel)
# ---------------------------------------------------------------------------

def _sintesis_variable(db: Session, v) -> dict:
    """Fila de la síntesis del proceso: especificación, estado de control y capacidad."""
    d = v.decimales + 1
    espec = ("—" if v.lei is None and v.les is None else
             f"{_f(v.lei, v.decimales) if v.lei is not None else '—'} – {_f(v.les, v.decimales) if v.les is not None else '—'}")
    fila = {"variable": v.nombre, "unidad": v.unidad, "especificacion": espec, "tipo": NOMBRES_CARTA[v.tipo_carta],
            "fase": v.fase, "media": "—", "s": "—", "cpk": "—", "estado": "Sin datos"}
    try:
        carta = sv.carta_variable(db, v)
    except HTTPException:
        return fila
    if carta.get("vacio"):
        return fila
    clave = next(iter(carta["cartas"]))
    lc = carta["cartas"][clave]["lc"]
    lc = lc[-1] if isinstance(lc, list) else lc
    fila["media"] = _f(lc, 4 if v.tipo_carta == "p" else d)
    senales = carta.get("puntos_con_senal") or []
    fila["estado"] = ("Fuera de control" if senales else "Bajo control") + (" (Fase I)" if v.fase == "I" else "")
    if not sv.es_atributos(v) and (v.lei is not None or v.les is not None):
        try:
            cap = sv.capacidad_variable(db, v, None, None)
            fila.update({"media": _f(cap["media"], d), "s": _f(cap["desviacion_estandar"], d + 1), "cpk": _f(cap["indices"]["cpk"], 2)})
        except HTTPException:
            pass
    return fila


def armar_contenido(db: Session, v, plantilla: str, modulos: list[str] | None, usuario: str | None) -> dict:
    titulo, por_defecto = PLANTILLAS[plantilla]
    modulos = [m for m in (modulos or por_defecto) if m in MODULOS]
    fecha = ahora()
    contenido = {
        "folio": f"REP-{plantilla[:3].upper()}-{v.id:03d}-{fecha:%Y%m%d-%H%M%S}",
        "plantilla": plantilla, "titulo": titulo, "fecha": fecha.strftime("%d/%m/%Y %H:%M"),
        "usuario": usuario_o_anonimo(usuario), "modulos": modulos,
        "proceso": sv.proceso_a_dict(v.proceso, False), "variable": sv.variable_a_dict(v),
        "sintesis_proceso": [_sintesis_variable(db, x) for x in v.proceso.variables],
        "carta": None, "limites_congelados": None, "capacidad": None, "supuestos": None, "diseno": None,
        "alarmas": [], "exclusiones": [], "historial": [], "lotes": [],
    }
    try:
        carta = sv.carta_variable(db, v)
        if not carta.get("vacio"):
            contenido["carta"] = carta
            contenido["limites_congelados"] = carta.get("limites_congelados")
    except HTTPException:
        pass
    contenido["exclusiones"] = [sv.subgrupo_a_dict(sg, v) for sg in sv.subgrupos_de(db, v, ("I",)) if sg.excluido]
    if not sv.es_atributos(v):
        if v.lei is not None or v.les is not None:
            try:
                contenido["capacidad"] = sv.capacidad_variable(db, v, None, None)
            except HTTPException:
                pass
        try:
            contenido["supuestos"] = sv.supuestos_variable(db, v, None, 0.05, 20)
        except HTTPException:
            pass
        n = 1 if v.tipo_carta == "imr" else v.n
        h = v.frecuencia_min / 60
        contenido["diseno"] = {"resumen": diseno_arl.diseno(v.k_sigma, n, h, 1.0),
                               "curva": diseno_arl.curva_arl(v.k_sigma, n, None, h, [m for m in (3, 10) if m != n])}
    # Plan vigente explicado en palabras (variables y atributos) para el informe LaTeX.
    try:
        contenido["plan"] = sv.plan_muestreo(db, v)["actual"]
    except (HTTPException, ValueError):
        contenido["plan"] = None
    contenido["alarmas"] = [sv.alarma_a_dict(a) for a in db.scalars(
        select(Alarma).where(Alarma.variable_id == v.id).order_by(Alarma.creada.desc()))]
    contenido["historial"] = [sv.cambio_a_dict(c) for c in db.scalars(
        select(CambioConfiguracion).where(CambioConfiguracion.variable_id == v.id).order_by(CambioConfiguracion.id.desc()))]
    contenido["lotes"] = [{"codigo": l.codigo, "fecha": l.fecha, "N": l.N, "n": l.n, "c": l.c, "defectos": l.defectos,
                           "p_hat": l.p_hat, "dictamen": l.dictamen, "usuario": l.usuario}
                          for l in db.scalars(select(LoteInspeccion).order_by(LoteInspeccion.id.desc()))]

    carta = contenido["carta"]
    if carta is not None:
        carta = {**carta, "etiquetas": carta.get("etiquetas")}
    contenido["conclusiones"] = generar_conclusiones(
        carta=carta if "cartas" in modulos or "resumen" in modulos else None,
        capacidad=contenido["capacidad"] if {"capacidad", "resumen"} & set(modulos) else None,
        supuestos=contenido["supuestos"] if {"supuestos", "resumen"} & set(modulos) else None,
        diseno=contenido["diseno"]["resumen"] if contenido["diseno"] and "diseno" in modulos else None,
    )
    return contenido


def conclusiones_descriptivas(contenido: dict) -> list[dict]:
    """Conclusiones para el PDF de respaldo y el Excel con los mismos textos del informe LaTeX:
    solo describen (sin recomendaciones), con el formato {seccion, nivel, texto}."""
    r = reporte_latex.resumen_pantalla(contenido)
    nivel = {"verde": "ok", "ambar": "advertencia", "rojo": "critico"}.get(r["estado"]["color"], "advertencia")
    return [{"seccion": "sintesis", "nivel": nivel, "texto": f"{r['estado']['titulo']}. {r['estado']['texto']}"},
            *({"seccion": "resumen", "nivel": "ok", "texto": h} for h in r["hallazgos"])]


def _reporte_dict(r: ReporteGenerado) -> dict:
    return {"id": r.id, "variable_id": r.variable_id, "nombre_archivo": r.nombre_archivo, "plantilla": r.plantilla,
            "formato": r.formato, "tamano_bytes": r.tamano_bytes, "sha256": r.sha256, "usuario": r.usuario, "fecha": r.fecha,
            "titulo": PLANTILLAS.get(r.plantilla, (r.plantilla,))[0]}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/plantillas", summary="Plantillas y módulos disponibles")
def plantillas():
    return {"plantillas": {k: {"titulo": t, "modulos": m} for k, (t, m) in PLANTILLAS.items()}, "modulos": list(MODULOS),
            "latex": bool(reporte_latex.disponible()["pdflatex"])}


@router.post("/vista-previa", summary="Contenido del reporte (JSON) para la vista previa")
def vista_previa(pedido: PedidoReporte, db: Session = Depends(obtener_sesion)):
    v = sv.obtener_variable(db, pedido.variable_id)
    c = limpiar_json(armar_contenido(db, v, pedido.plantilla, pedido.modulos, pedido.usuario))
    # Mismos textos que la primera página del PDF (estado, hallazgos e indicadores en palabras).
    c["informe"] = reporte_latex.resumen_pantalla(c)
    # La vista previa no necesita las series completas de supuestos.
    if c["supuestos"]:
        c["supuestos"] = {k: c["supuestos"][k] for k in ("normalidad", "independencia", "rachas", "box_cox", "apto_shewhart")}
        c["supuestos"]["independencia"] = {k: x for k, x in c["supuestos"]["independencia"].items() if k != "ljung_box"}
    return limpiar_json(c)


@router.post("/generar", status_code=201, summary="Generar el reporte PDF o Excel y registrarlo con su SHA-256")
def generar(pedido: PedidoReporte, db: Session = Depends(obtener_sesion)):
    v = sv.obtener_variable(db, pedido.variable_id)
    contenido = limpiar_json(armar_contenido(db, v, pedido.plantilla, pedido.modulos, pedido.usuario))
    contenido["conclusiones"] = conclusiones_descriptivas(contenido)
    motor, aviso = ("excel", None) if pedido.formato == "xlsx" else ("latex", None)
    try:
        if pedido.formato == "xlsx":
            datos = construir_excel(contenido)
        else:
            try:
                datos = reporte_latex.construir_pdf_latex(contenido)
            except reporte_latex.ErrorLatex as e:
                # Respaldo: el PDF con reportlab funciona en cualquier equipo, aunque no tenga LaTeX.
                datos, motor, aviso = construir_pdf(contenido), "reportlab", str(e)
    except Exception as e:  # se informa el error del motor de reportes sin tumbar el servidor
        raise HTTPException(500, f"No se pudo generar el reporte: {e}")
    nombre = f"{contenido['folio']}.{pedido.formato}"
    ruta = carpeta_reportes() / nombre
    sufijo = 2
    while ruta.exists():  # dos reportes en el mismo segundo no se pisan
        nombre = f"{contenido['folio']}-{sufijo}.{pedido.formato}"
        ruta = carpeta_reportes() / nombre
        sufijo += 1
    ruta.write_bytes(datos)
    r = ReporteGenerado(variable_id=v.id, nombre_archivo=nombre, plantilla=pedido.plantilla, formato=pedido.formato,
                        tamano_bytes=len(datos), sha256=hashlib.sha256(datos).hexdigest(), ruta=str(ruta),
                        usuario=usuario_o_anonimo(pedido.usuario))
    db.add(r)
    db.commit()
    return {**_reporte_dict(r), "motor": motor, "aviso": aviso}


@router.get("", summary="Historial de reportes generados")
def listar(variable_id: int | None = None, db: Session = Depends(obtener_sesion)):
    q = select(ReporteGenerado).order_by(ReporteGenerado.id.desc())
    if variable_id:
        q = q.where(ReporteGenerado.variable_id == variable_id)
    return [_reporte_dict(r) for r in db.scalars(q.limit(200))]


def _obtener(db: Session, reporte_id: int) -> ReporteGenerado:
    r = db.get(ReporteGenerado, reporte_id)
    if r is None or not Path(r.ruta).exists():
        raise HTTPException(404, "Reporte no encontrado (el archivo pudo haberse borrado).")
    return r


@router.get("/{reporte_id}/descargar", summary="Descargar un reporte generado")
def descargar(reporte_id: int, db: Session = Depends(obtener_sesion)):
    r = _obtener(db, reporte_id)
    tipo = "application/pdf" if r.formato == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(r.ruta, media_type=tipo, filename=r.nombre_archivo, headers={"X-SHA256": r.sha256})


@router.get("/{reporte_id}/verificar", summary="Recalcular el SHA-256 del archivo y compararlo con el registrado")
def verificar(reporte_id: int, db: Session = Depends(obtener_sesion)):
    r = _obtener(db, reporte_id)
    actual = hashlib.sha256(Path(r.ruta).read_bytes()).hexdigest()
    return {"id": r.id, "sha256_registrado": r.sha256, "sha256_actual": actual, "integro": actual == r.sha256}
