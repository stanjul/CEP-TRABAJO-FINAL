"""Ingesta y preparación de datos: lectura de CSV/Excel, mapeo de columnas, formación de
subgrupos racionales, tratamiento de faltantes y atípicos, y estadística descriptiva.

Formatos admitidos para datos por variables:

- **Largo**: una fila por medición. Columnas típicas: subgrupo, (muestra), valor, fecha…
  Si no hay columna de subgrupo, se forman subgrupos de n mediciones consecutivas.
- **Ancho**: una fila por subgrupo con columnas M1 … Mn.

Para atributos: una fila por muestra con el conteo (defectuosos/defectos) y, si aplica,
el tamaño de la muestra.

Atípicos:
- Regla de Tukey: fuera de [Q1 − k·IQR, Q3 + k·IQR] con k = 1.5 (IQR = Q3 − Q1).
- Regla sigma: |x − x̄| > k·s con k = 3.
"""

from __future__ import annotations

import csv
import io
import math
import re
import unicodedata
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from .constantes import N_MAX, constantes

ROLES = ("fecha", "subgrupo", "muestra", "valor", "conteo", "tamano", "operario", "lote", "ignorar")

# Palabras clave para sugerir el rol de cada columna a partir de su nombre.
_PISTAS = {
    "fecha": ("fecha", "hora", "time", "date", "timestamp"),
    "subgrupo": ("subgrupo", "subgroup", "grupo", "muestra_id", "sg", "lote_muestra"),
    "muestra": ("sample_index", "posicion", "indice", "replica", "obs"),
    "conteo": ("defect", "defectuos", "conteo", "no_conform", "count"),
    "tamano": ("tamano", "tamaño", "size", "n_muestra", "inspeccionad", "unidades"),
    "operario": ("operario", "operador", "operator", "inspector"),
    "lote": ("lote", "lot", "batch"),
}


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

def detectar_delimitador(muestra: str) -> str:
    """Detecta el delimitador de un CSV a partir de las primeras líneas."""
    try:
        return csv.Sniffer().sniff(muestra, delimiters=",;\t| ").delimiter
    except csv.Error:
        return ";" if muestra.count(";") > muestra.count(",") else ","


def leer_tabla(
    origen: bytes | str | Path,
    nombre_archivo: str | None = None,
    delimitador: str | None = None,
    codificacion: str = "utf-8",
    encabezado: bool = True,
    decimal: str | None = None,
    hoja: int | str = 0,
) -> pd.DataFrame:
    """Lee un CSV/TXT/DAT o un Excel (.xlsx/.xls) y devuelve un DataFrame.

    - `origen` puede ser una ruta o el contenido en bytes (archivo subido).
    - Si `delimitador` es None se detecta automáticamente.
    - Si `decimal` es None: se usa coma decimal cuando el delimitador es ';'.
    """
    nombre = nombre_archivo or (str(origen) if isinstance(origen, (str, Path)) else "datos.csv")
    ext = Path(nombre).suffix.lower()
    contenido = Path(origen).read_bytes() if isinstance(origen, (str, Path)) else origen

    if ext in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(io.BytesIO(contenido), sheet_name=hoja, header=0 if encabezado else None)
    else:
        texto = contenido.decode(codificacion, errors="replace").lstrip("﻿")
        sep = delimitador or detectar_delimitador("\n".join(texto.splitlines()[:20]))
        dec = decimal or ("," if sep == ";" else ".")
        df = pd.read_csv(io.StringIO(texto), sep=sep, decimal=dec, header=0 if encabezado else None,
                         skipinitialspace=True)
    if not encabezado:
        df.columns = [f"col_{i + 1}" for i in range(df.shape[1])]
    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all")


# ---------------------------------------------------------------------------
# Perfil de columnas y mapeo
# ---------------------------------------------------------------------------

def _tipo_columna(s: pd.Series) -> str:
    """Clasifica una columna en 'entero', 'decimal', 'fecha' o 'texto'."""
    no_nulos = s.dropna()
    if no_nulos.empty:
        return "vacia"
    if pd.api.types.is_bool_dtype(s):
        return "texto"
    if pd.api.types.is_numeric_dtype(s):
        return "entero" if np.allclose(no_nulos, np.round(no_nulos)) else "decimal"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "fecha"
    num = pd.to_numeric(no_nulos.astype(str).str.replace(",", ".", regex=False), errors="coerce")
    if num.notna().mean() > 0.95:
        return "entero" if np.allclose(num.dropna(), np.round(num.dropna())) else "decimal"
    fechas = pd.to_datetime(no_nulos.astype(str), errors="coerce", format="mixed")
    if fechas.notna().mean() > 0.9:
        return "fecha"
    return "texto"


def perfilar_columnas(df: pd.DataFrame) -> list[dict]:
    """Describe cada columna: tipo inferido, nulos, valores únicos, rango y ejemplos."""
    perfil = []
    for col in df.columns:
        s = df[col]
        tipo = _tipo_columna(s)
        info = {"columna": col, "tipo": tipo, "nulos": int(s.isna().sum()), "unicos": int(s.nunique(dropna=True)),
                "ejemplos": [str(v) for v in s.dropna().head(3).tolist()]}
        if tipo in ("entero", "decimal"):
            num = a_numerico(s)
            info.update({"min": float(num.min()), "max": float(num.max()), "media": float(num.mean())})
        elif tipo == "fecha":
            f = pd.to_datetime(s.astype(str), errors="coerce", format="mixed")
            info.update({"min": str(f.min()), "max": str(f.max())})
        perfil.append(info)
    return perfil


def sugerir_mapeo(df: pd.DataFrame) -> dict[str, str]:
    """Propone un rol para cada columna (ver ROLES) a partir del nombre y del tipo.

    La primera columna decimal sin otro rol se propone como 'valor' (variable CTQ). En formato
    ancho (M1…Mn) todas esas columnas reciben el rol 'valor'.
    """
    perfil = {p["columna"]: p for p in perfilar_columnas(df)}
    mapeo: dict[str, str] = {}
    usados: set[str] = set()
    ancho = columnas_ancho(df)
    if len(ancho) >= 2:
        usados.add("valor")
    for col in df.columns:
        if col in ancho and len(ancho) >= 2:
            mapeo[col] = "valor"
            continue
        nombre = _normalizar(col)
        rol = "ignorar"
        for candidato, pistas in _PISTAS.items():
            if candidato in usados:
                continue
            if any(p in nombre for p in pistas):
                rol = candidato
                break
        if rol == "ignorar" and perfil[col]["tipo"] == "fecha" and "fecha" not in usados:
            rol = "fecha"
        mapeo[col] = rol
        if rol != "ignorar":
            usados.add(rol)
    if "valor" not in usados and "conteo" not in usados:
        for col in df.columns:
            if mapeo[col] == "ignorar" and perfil[col]["tipo"] == "decimal":
                mapeo[col] = "valor"
                break
    return mapeo


def a_numerico(s: pd.Series) -> pd.Series:
    """Convierte una columna a número aceptando coma decimal; lo no numérico queda NaN."""
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float)
    return pd.to_numeric(s.astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce")


def columnas_ancho(df: pd.DataFrame) -> list[str]:
    """Detecta columnas de formato ancho (M1…Mn, X1…Xn, Muestra 1…)."""
    patron = re.compile(r"^(m|x|muestra|medicion|valor|obs)_?\d+$")
    return [c for c in df.columns if patron.match(_normalizar(c))]


# ---------------------------------------------------------------------------
# Faltantes y atípicos
# ---------------------------------------------------------------------------

def detectar_atipicos(valores: Sequence[float], metodo: str = "iqr", k: float | None = None) -> dict:
    """Marca atípicos con la regla de Tukey (k = 1.5 por defecto) o la regla sigma (k = 3).

    Devuelve la máscara, los límites usados y la cantidad detectada.
    """
    x = np.asarray(valores, dtype=float)
    validos = x[~np.isnan(x)]
    if metodo == "ninguno" or validos.size < 4:
        return {"metodo": metodo, "mascara": [False] * x.size, "limites": None, "cantidad": 0}
    if metodo == "iqr":
        k = 1.5 if k is None else k
        q1, q3 = np.percentile(validos, [25, 75])
        lo, hi = q1 - k * (q3 - q1), q3 + k * (q3 - q1)
    elif metodo == "sigma":
        k = 3.0 if k is None else k
        m, s = validos.mean(), validos.std(ddof=1)
        lo, hi = m - k * s, m + k * s
    else:
        raise ValueError(f"Método de atípicos desconocido: {metodo}")
    mascara = (x < lo) | (x > hi)
    return {"metodo": metodo, "k": k, "mascara": mascara.tolist(), "limites": [float(lo), float(hi)],
            "cantidad": int(mascara.sum())}


def tratar_faltantes(df: pd.DataFrame, col_valor: str, metodo: str = "descartar",
                     col_subgrupo: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Trata valores faltantes o no numéricos de la variable.

    - "descartar": elimina las filas sin valor.
    - "imputar_media_subgrupo": reemplaza por la media de su subgrupo (requiere columna
      de subgrupo; si el subgrupo no tiene datos se descarta la fila).
    - "bloquear": no modifica nada y reporta error si hay faltantes.
    """
    df = df.copy()
    df[col_valor] = a_numerico(df[col_valor])
    faltantes = int(df[col_valor].isna().sum())
    info = {"metodo": metodo, "faltantes": faltantes, "descartados": 0, "imputados": 0, "error": None}
    if faltantes == 0:
        return df, info
    if metodo == "descartar":
        df = df[df[col_valor].notna()]
        info["descartados"] = faltantes
    elif metodo == "imputar_media_subgrupo":
        if not col_subgrupo:
            raise ValueError("Para imputar por subgrupo se necesita la columna de subgrupo.")
        medias = df.groupby(col_subgrupo)[col_valor].transform("mean")
        imputables = df[col_valor].isna() & medias.notna()
        df.loc[imputables, col_valor] = medias[imputables]
        info["imputados"] = int(imputables.sum())
        restantes = df[col_valor].isna()
        info["descartados"] = int(restantes.sum())
        df = df[~restantes]
    elif metodo == "bloquear":
        info["error"] = f"Hay {faltantes} valores faltantes; corrija el archivo antes de continuar."
    else:
        raise ValueError(f"Método de faltantes desconocido: {metodo}")
    return df, info


# ---------------------------------------------------------------------------
# Subgrupos racionales
# ---------------------------------------------------------------------------

def formar_subgrupos(
    df: pd.DataFrame,
    col_valor: str | None = None,
    col_subgrupo: str | None = None,
    n: int | None = None,
    col_fecha: str | None = None,
    cols_ancho: Sequence[str] | None = None,
    col_operario: str | None = None,
    col_lote: str | None = None,
) -> list[dict]:
    """Agrupa las mediciones en subgrupos racionales.

    Prioridad: formato ancho (`cols_ancho`) → columna de subgrupo → n consecutivas.
    Cada subgrupo es ``{"id", "valores", "fecha", "operario", "lote"}``. En el modo de n
    consecutivas, un último subgrupo incompleto se descarta.
    """
    def meta(filas: pd.DataFrame, col):
        if not col or col not in filas:
            return None
        v = filas[col].dropna()
        return None if v.empty else str(v.iloc[0])

    salida: list[dict] = []
    if cols_ancho:
        for i, (_, fila) in enumerate(df.iterrows()):
            valores = [float(v) for v in a_numerico(fila[list(cols_ancho)]) if not math.isnan(v)]
            ident = fila[col_subgrupo] if col_subgrupo else i + 1
            f = fila.to_frame().T
            salida.append({"id": str(ident), "valores": valores, "fecha": meta(f, col_fecha),
                           "operario": meta(f, col_operario), "lote": meta(f, col_lote)})
        return salida

    if col_valor is None:
        raise ValueError("Indique la columna de la variable.")
    datos = df.copy()
    datos[col_valor] = a_numerico(datos[col_valor])
    if col_subgrupo:
        for ident, filas in datos.groupby(col_subgrupo, sort=False):
            valores = filas[col_valor].dropna().astype(float).tolist()
            salida.append({"id": str(ident), "valores": valores, "fecha": meta(filas, col_fecha),
                           "operario": meta(filas, col_operario), "lote": meta(filas, col_lote)})
        return salida

    if not n or n < 1:
        raise ValueError("Sin columna de subgrupo hay que indicar n.")
    valores = datos[col_valor].dropna()
    datos = datos.loc[valores.index]
    for i in range(len(datos) // n):
        filas = datos.iloc[i * n:(i + 1) * n]
        salida.append({"id": str(i + 1), "valores": filas[col_valor].astype(float).tolist(),
                       "fecha": meta(filas, col_fecha), "operario": meta(filas, col_operario),
                       "lote": meta(filas, col_lote)})
    return salida


# ---------------------------------------------------------------------------
# Descriptivos
# ---------------------------------------------------------------------------

def descriptivos(valores: Iterable[float], subgrupos: Sequence[Sequence[float]] | None = None) -> dict:
    """Estadística descriptiva de la variable.

    Incluye N, media, mediana, s, mín, máx, cuartiles, IQR, asimetría y curtosis. Si se
    dan subgrupos de tamaño constante, agrega R̄, s̄ y las estimaciones σ̂ = R̄/d2 y s̄/c4.
    """
    x = np.asarray(list(valores), dtype=float)
    x = x[~np.isnan(x)]
    if x.size == 0:
        raise ValueError("No hay datos numéricos.")
    q1, q2, q3 = np.percentile(x, [25, 50, 75])
    res = {
        "N": int(x.size),
        "media": float(x.mean()),
        "mediana": float(q2),
        "s": float(x.std(ddof=1)) if x.size > 1 else None,
        "minimo": float(x.min()),
        "maximo": float(x.max()),
        "rango": float(x.max() - x.min()),
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(q3 - q1),
        "asimetria": float(stats.skew(x, bias=False)) if x.size > 2 else None,
        "curtosis": float(stats.kurtosis(x, bias=False)) if x.size > 3 else None,
    }
    if subgrupos:
        tam = {len(g) for g in subgrupos if len(g)}
        res["k_subgrupos"] = len(subgrupos)
        if len(tam) == 1 and 2 <= (n := tam.pop()) <= N_MAX:
            cst = constantes(n)
            rbar = float(np.mean([np.ptp(g) for g in subgrupos]))
            sbar = float(np.mean([np.std(g, ddof=1) for g in subgrupos]))
            res.update({"n": n, "r_barra": rbar, "s_barra": sbar,
                        "sigma_r_d2": rbar / cst.d2, "sigma_s_c4": sbar / cst.c4})
    return res


def preparar_dataset(df: pd.DataFrame, mapeo: dict[str, str], n: int | None = None,
                     faltantes: str = "descartar", atipicos: str = "ninguno",
                     excluir_atipicos: bool = False) -> dict:
    """Pipeline completo de la pantalla de Datos: aplica el mapeo, trata faltantes,
    detecta atípicos (y opcionalmente los quita) y forma subgrupos con su descriptiva.

    `mapeo` asocia columna → rol. Si varias columnas tienen el rol 'valor' se interpreta como
    formato ancho (una fila por subgrupo). Devuelve subgrupos, informe de limpieza y descriptivos.
    """
    rol = {v: k for k, v in mapeo.items() if v != "ignorar"}
    columnas_valor = [c for c, r in mapeo.items() if r == "valor"]
    col_sub = rol.get("subgrupo")
    if len(columnas_valor) > 1:
        col_valor, ancho = None, columnas_valor
    else:
        col_valor = columnas_valor[0] if columnas_valor else None
        ancho = columnas_ancho(df) if not col_valor else []
    if not col_valor and not ancho:
        raise ValueError("Asigne una columna con el rol 'valor' (variable CTQ).")

    informe: dict = {"filas_originales": int(len(df))}
    if ancho:
        subgrupos = formar_subgrupos(df, cols_ancho=ancho, col_subgrupo=col_sub, col_fecha=rol.get("fecha"),
                                     col_operario=rol.get("operario"), col_lote=rol.get("lote"))
        informe["faltantes"] = {"metodo": faltantes, "faltantes": int(a_numerico(df[ancho].stack()).isna().sum())}
        informe["atipicos"] = {"metodo": atipicos, "cantidad": 0}
    else:
        limpio, info_f = tratar_faltantes(df, col_valor, faltantes, col_sub)
        informe["faltantes"] = info_f
        if info_f.get("error"):
            return {"error": info_f["error"], "informe": informe}
        at = detectar_atipicos(limpio[col_valor].to_numpy(), atipicos)
        informe["atipicos"] = {k: v for k, v in at.items() if k != "mascara"}
        informe["filas_atipicas"] = [int(i) for i, m in zip(limpio.index, at["mascara"]) if m]
        if excluir_atipicos and at["cantidad"]:
            limpio = limpio[~np.asarray(at["mascara"])]
        subgrupos = formar_subgrupos(limpio, col_valor, col_sub, n, rol.get("fecha"),
                                     col_operario=rol.get("operario"), col_lote=rol.get("lote"))
    todos = [v for g in subgrupos for v in g["valores"]]
    tamanos = [len(g["valores"]) for g in subgrupos]
    informe.update({"k_subgrupos": len(subgrupos), "tamanos": sorted(set(tamanos)),
                    "n_constante": len(set(tamanos)) == 1})
    return {"subgrupos": subgrupos, "informe": informe,
            "descriptivos": descriptivos(todos, [g["valores"] for g in subgrupos])}
