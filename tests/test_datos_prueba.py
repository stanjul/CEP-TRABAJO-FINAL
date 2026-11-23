"""Flujo completo sobre los archivos de datos_prueba/ (lectura → subgrupos → Fase I → Fase II)."""
from pathlib import Path

import pytest

from app.core import capacidad, datos as dt, graficos_variables as gv

CARPETA = Path(__file__).resolve().parents[1] / "datos_prueba"


@pytest.fixture(scope="module")
def subgrupos():
    df = dt.leer_tabla(CARPETA / "proceso_simulado.csv")
    mapeo = dt.sugerir_mapeo(df)
    assert mapeo["peso_neto_g"] == "valor"
    assert mapeo["subgrupo"] == "subgrupo"
    r = dt.preparar_dataset(df, mapeo)
    assert r["informe"]["k_subgrupos"] == 25 and r["informe"]["tamanos"] == [5]
    return [g["valores"] for g in r["subgrupos"]]


def test_base_estable_y_corrimiento_detectado(subgrupos):
    base = gv.calcular_xbar_r(subgrupos[:19])
    assert base["puntos_con_senal"] == []
    fase2 = gv.calcular_xbar_r(subgrupos[19:], limites=base["limites"])
    assert fase2["fase"] == "II"
    # Todas las señales ocurren en los subgrupos 20–25 (índices 0–5 de la Fase II).
    assert fase2["puntos_con_senal"]
    assert min(fase2["puntos_con_senal"]) <= 2  # se detecta en los primeros subgrupos tras el corrimiento


def test_fase_i_contaminada_y_depuracion(subgrupos):
    """Con los 25 subgrupos en la Fase I, los corridos inflan X̿ y aparece una señal espuria
    (subgrupo 9 bajo el LCI) además de las del corrimiento. Al excluir los subgrupos 20–25
    (causa asignable: cambio de lote) y recalcular, la base queda limpia."""
    res = gv.calcular_xbar_r(subgrupos)
    senales = res["puntos_con_senal"]
    assert sum(i >= 19 for i in senales) >= 4
    depurada = gv.calcular_xbar_r(subgrupos, excluidos=list(range(19, 25)))
    assert [i for i in depurada["puntos_con_senal"] if i < 19] == []


def test_ancho_equivale_a_largo(subgrupos):
    df = dt.leer_tabla(CARPETA / "proceso_simulado_ancho.csv")
    ancho = dt.formar_subgrupos(df, cols_ancho=dt.columnas_ancho(df), col_subgrupo="Subgrupo")
    assert [g["valores"] for g in ancho] == subgrupos


def test_excel(subgrupos):
    df = dt.leer_tabla(CARPETA / "proceso_simulado.xlsx")
    assert len(df) == 125


def test_limpieza_faltantes_y_atipicos():
    df = dt.leer_tabla(CARPETA / "proceso_con_faltantes.csv")
    r = dt.preparar_dataset(df, dt.sugerir_mapeo(df), faltantes="imputar_media_subgrupo",
                            atipicos="iqr", excluir_atipicos=True)
    assert r["informe"]["faltantes"]["imputados"] == 3
    # Los dos atípicos plantados (filas 12 y 48) deben estar entre los marcados por Tukey.
    assert {12, 48} <= set(r["informe"]["filas_atipicas"])
    assert r["descriptivos"]["maximo"] < 512 and r["descriptivos"]["minimo"] > 450


def test_capacidad_base(subgrupos):
    cap = capacidad.analizar_capacidad(subgrupos[:19], 495, 505, 500)
    assert cap["indices"]["cp"] == pytest.approx(10 / 6, rel=0.25)  # σ ≈ 1 ⇒ Cp ≈ 1.67
