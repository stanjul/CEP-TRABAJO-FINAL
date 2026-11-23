"""Módulo 1 — Datos: carga de CSV/Excel, mapeo de columnas, limpieza e importación.

El archivo se envía en cada paso (multipart/form-data); el servidor no guarda borradores.
Flujo de la pantalla: /datos/analizar → (el usuario ajusta el mapeo) → /datos/preparar →
/datos/importar.
"""

from __future__ import annotations

import io
import json
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core import datos as dt
from app.core import supuestos as core_sup
from app.db.sesion import obtener_sesion

from . import servicios as sv

router = APIRouter(prefix="/datos", tags=["Datos"])

MAX_BYTES = 50 * 1024 * 1024


async def _leer(archivo: UploadFile, delimitador: str | None, codificacion: str, encabezado: bool) -> pd.DataFrame:
    contenido = await archivo.read()
    if len(contenido) > MAX_BYTES:
        raise HTTPException(413, "El archivo supera los 50 MB.")
    try:
        return dt.leer_tabla(contenido, archivo.filename, delimitador or None, codificacion, encabezado)
    except Exception as e:  # errores de pandas/openpyxl con archivos mal formados
        raise HTTPException(422, f"No se pudo leer el archivo: {e}")


def _mapeo(texto: str | None, df: pd.DataFrame) -> dict[str, str]:
    if not texto:
        return dt.sugerir_mapeo(df)
    try:
        mapeo = json.loads(texto)
    except json.JSONDecodeError:
        raise HTTPException(422, "El mapeo debe ser un objeto JSON {columna: rol}.")
    desconocidas = [c for c in mapeo if c not in df.columns]
    if desconocidas:
        raise HTTPException(422, f"Columnas inexistentes en el mapeo: {desconocidas}")
    malos = [r for r in mapeo.values() if r not in dt.ROLES]
    if malos:
        raise HTTPException(422, f"Roles desconocidos: {malos}. Válidos: {dt.ROLES}")
    return mapeo


@router.post("/analizar", summary="Leer el archivo: perfil de columnas, mapeo sugerido y vista previa")
async def analizar(archivo: UploadFile = File(...), delimitador: str | None = Form(None),
                   codificacion: str = Form("utf-8"), encabezado: bool = Form(True)):
    df = await _leer(archivo, delimitador, codificacion, encabezado)
    return {
        "archivo": archivo.filename, "filas": int(len(df)), "columnas": list(df.columns),
        "perfil": dt.perfilar_columnas(df), "mapeo_sugerido": dt.sugerir_mapeo(df),
        "columnas_ancho": dt.columnas_ancho(df),
        "vista_previa": json.loads(df.head(20).to_json(orient="records", date_format="iso")),
        "roles": list(dt.ROLES),
    }


async def _preparar(archivo, mapeo, n, faltantes, atipicos, excluir_atipicos, delimitador, codificacion, encabezado):
    df = await _leer(archivo, delimitador, codificacion, encabezado)
    m = _mapeo(mapeo, df)
    try:
        r = dt.preparar_dataset(df, m, n, faltantes, atipicos, excluir_atipicos)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return df, m, r


@router.post("/preparar", summary="Aplicar mapeo, limpieza y subgrupos; devuelve descriptivos e histograma")
async def preparar(archivo: UploadFile = File(...), mapeo: str | None = Form(None), n: int | None = Form(None),
                   faltantes: str = Form("descartar"), atipicos: str = Form("iqr"),
                   excluir_atipicos: bool = Form(False), delimitador: str | None = Form(None),
                   codificacion: str = Form("utf-8"), encabezado: bool = Form(True)):
    df, m, r = await _preparar(archivo, mapeo, n, faltantes, atipicos, excluir_atipicos, delimitador, codificacion,
                               encabezado)
    if "error" in r:
        raise HTTPException(422, r["error"])
    valores = [v for g in r["subgrupos"] for v in g["valores"]]
    r["histograma"] = core_sup.histograma(valores) if len(valores) >= 2 else None
    r["normalidad"] = core_sup.normalidad(valores) if len(valores) >= 8 else None
    r["mapeo"] = m
    r["subgrupos_muestra"] = r["subgrupos"][:10]
    r["subgrupos_total"] = len(r["subgrupos"])
    del r["subgrupos"]  # la lista completa puede ser larga; se envía al importar
    return r


@router.post("/exportar", summary="Descargar el dataset depurado en formato largo (CSV)")
async def exportar(archivo: UploadFile = File(...), mapeo: str | None = Form(None), n: int | None = Form(None),
                   faltantes: str = Form("descartar"), atipicos: str = Form("iqr"),
                   excluir_atipicos: bool = Form(False), delimitador: str | None = Form(None),
                   codificacion: str = Form("utf-8"), encabezado: bool = Form(True)):
    _, _, r = await _preparar(archivo, mapeo, n, faltantes, atipicos, excluir_atipicos, delimitador, codificacion,
                              encabezado)
    filas = [{"subgrupo": g["id"], "muestra": j + 1, "valor": v, "fecha": g["fecha"], "operario": g["operario"],
              "lote": g["lote"]} for g in r["subgrupos"] for j, v in enumerate(g["valores"])]
    salida = io.StringIO()
    pd.DataFrame(filas).to_csv(salida, index=False)
    nombre = (archivo.filename or "datos").rsplit(".", 1)[0] + "_depurado.csv"
    return StreamingResponse(iter([salida.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


def _fecha(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        return pd.to_datetime(texto).to_pydatetime().replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


@router.post("/importar", summary="Importar los subgrupos a una variable (Fase I por defecto)")
async def importar(variable_id: int = Form(...), archivo: UploadFile = File(...), mapeo: str | None = Form(None),
                   n: int | None = Form(None), faltantes: str = Form("descartar"), atipicos: str = Form("iqr"),
                   excluir_atipicos: bool = Form(False), reemplazar: bool = Form(False),
                   delimitador: str | None = Form(None), codificacion: str = Form("utf-8"),
                   encabezado: bool = Form(True), usuario: str | None = Form(None),
                   db: Session = Depends(obtener_sesion)):
    """Para atributos el archivo debe tener columnas con rol 'conteo' (y 'tamano' si aplica)."""
    v = sv.obtener_variable(db, variable_id)
    df = await _leer(archivo, delimitador, codificacion, encabezado)
    m = _mapeo(mapeo, df)
    rol = {r: c for c, r in m.items() if r != "ignorar"}

    if reemplazar:
        if v.fase != "I":
            raise HTTPException(409, "Solo se reemplazan datos en Fase I.")
        for sg in sv.subgrupos_de(db, v, ("I",)):
            db.delete(sg)
        db.flush()

    importados = 0
    if sv.es_atributos(v):
        if "conteo" not in rol:
            raise HTTPException(422, "Asigne la columna de conteo (defectuosos o defectos).")
        conteos = dt.a_numerico(df[rol["conteo"]])
        tamanos = dt.a_numerico(df[rol["tamano"]]) if "tamano" in rol else None
        for i in range(len(df)):
            if pd.isna(conteos.iloc[i]):
                continue
            tam = None if tamanos is None or pd.isna(tamanos.iloc[i]) else float(tamanos.iloc[i])
            sv.registrar_subgrupo(db, v, conteo=float(conteos.iloc[i]), tamano=tam,
                                  timestamp=_fecha(str(df[rol["fecha"]].iloc[i])) if "fecha" in rol else None,
                                  operario=str(df[rol["operario"]].iloc[i]) if "operario" in rol else None,
                                  lote=str(df[rol["lote"]].iloc[i]) if "lote" in rol else None,
                                  origen="importado", evaluar=False)
            importados += 1
        informe = {"filas": int(len(df))}
    else:
        try:
            r = dt.preparar_dataset(df, m, n, faltantes, atipicos, excluir_atipicos)
        except ValueError as e:
            raise HTTPException(422, str(e))
        if "error" in r:
            raise HTTPException(422, r["error"])
        for g in r["subgrupos"]:
            if v.tipo_carta == "xbar_r" and len(g["valores"]) != v.n:
                continue  # subgrupo incompleto: se omite y se informa
            if v.tipo_carta == "imr":
                for x in g["valores"]:
                    sv.registrar_subgrupo(db, v, valores=[x], timestamp=_fecha(g["fecha"]), operario=g["operario"],
                                          lote=g["lote"], origen="importado", evaluar=False)
                    importados += 1
                continue
            sv.registrar_subgrupo(db, v, valores=g["valores"], timestamp=_fecha(g["fecha"]), operario=g["operario"],
                                  lote=g["lote"], origen="importado", evaluar=False)
            importados += 1
        informe = r["informe"]
        informe["omitidos_incompletos"] = len(r["subgrupos"]) - importados if v.tipo_carta == "xbar_r" else 0
    sv.registrar_cambio(db, v, "importacion", None, f"{importados} subgrupos desde {archivo.filename}", usuario,
                        "Reemplazo de datos de Fase I" if reemplazar else "Importación de datos")
    db.commit()
    return {"importados": importados, "fase": v.fase, "informe": informe}
