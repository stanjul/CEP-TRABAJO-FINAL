"""Ingesta, mapeo, subgrupos, limpieza y descriptivos."""
import io

import numpy as np
import pandas as pd
import pytest

from app.core import datos as dt
from tests.datos_montgomery import ANILLOS

CSV_LARGO = """subgrupo,fecha,valor,operario
1,2024-10-18 06:00,500.25,OP-1
1,2024-10-18 06:00,499.80,OP-1
1,2024-10-18 06:00,500.60,OP-1
2,2024-10-18 06:15,500.15,OP-2
2,2024-10-18 06:15,,OP-2
2,2024-10-18 06:15,500.45,OP-2
"""

CSV_PUNTO_COMA = "Subgrupo;M1;M2;M3\n1;10,5;10,7;10,6\n2;10,4;10,9;10,8\n"


def test_leer_csv_y_perfil():
    df = dt.leer_tabla(CSV_LARGO.encode(), "datos.csv")
    assert list(df.columns) == ["subgrupo", "fecha", "valor", "operario"]
    perfil = {p["columna"]: p for p in dt.perfilar_columnas(df)}
    assert perfil["valor"]["tipo"] == "decimal"
    assert perfil["valor"]["nulos"] == 1
    assert perfil["subgrupo"]["tipo"] == "entero"
    assert perfil["fecha"]["tipo"] == "fecha"
    assert perfil["operario"]["tipo"] == "texto"


def test_punto_y_coma_con_coma_decimal():
    df = dt.leer_tabla(CSV_PUNTO_COMA.encode(), "x.csv")
    assert dt.detectar_delimitador(CSV_PUNTO_COMA) == ";"
    assert dt.columnas_ancho(df) == ["M1", "M2", "M3"]
    grupos = dt.formar_subgrupos(df, cols_ancho=["M1", "M2", "M3"], col_subgrupo="Subgrupo")
    assert grupos[0]["valores"] == [10.5, 10.7, 10.6]


def test_leer_excel(tmp_path):
    ruta = tmp_path / "d.xlsx"
    pd.DataFrame({"x": [1.5, 2.5], "g": [1, 1]}).to_excel(ruta, index=False)
    df = dt.leer_tabla(ruta)
    assert df["x"].tolist() == [1.5, 2.5]


def test_sugerir_mapeo():
    df = dt.leer_tabla(CSV_LARGO.encode(), "datos.csv")
    m = dt.sugerir_mapeo(df)
    assert m == {"subgrupo": "subgrupo", "fecha": "fecha", "valor": "valor", "operario": "operario"}


def test_faltantes_descartar_e_imputar():
    df = dt.leer_tabla(CSV_LARGO.encode(), "datos.csv")
    d1, i1 = dt.tratar_faltantes(df, "valor", "descartar")
    assert len(d1) == 5 and i1["descartados"] == 1
    d2, i2 = dt.tratar_faltantes(df, "valor", "imputar_media_subgrupo", "subgrupo")
    assert i2["imputados"] == 1
    assert d2.loc[4, "valor"] == pytest.approx((500.15 + 500.45) / 2)
    _, i3 = dt.tratar_faltantes(df, "valor", "bloquear")
    assert i3["error"]


def test_atipicos():
    x = [10, 10.2, 9.9, 10.1, 10.0, 9.8, 15.0]
    r = dt.detectar_atipicos(x, "iqr")
    assert r["mascara"] == [False] * 6 + [True]
    r2 = dt.detectar_atipicos(x, "sigma", k=2)
    assert r2["cantidad"] == 1
    assert dt.detectar_atipicos(x, "ninguno")["cantidad"] == 0


def test_subgrupos_por_columna_y_por_n():
    df = dt.leer_tabla(CSV_LARGO.encode(), "datos.csv")
    g = dt.formar_subgrupos(df, "valor", col_subgrupo="subgrupo", col_fecha="fecha", col_operario="operario")
    assert [len(s["valores"]) for s in g] == [3, 2]
    assert g[1]["operario"] == "OP-2"
    g2 = dt.formar_subgrupos(pd.DataFrame({"v": range(11)}), "v", n=5)
    assert len(g2) == 2  # el subgrupo incompleto se descarta


def test_descriptivos_anillos():
    todos = np.concatenate(ANILLOS)
    d = dt.descriptivos(todos, ANILLOS)
    assert d["N"] == 125
    assert d["media"] == pytest.approx(74.001, abs=5e-4)
    assert d["r_barra"] == pytest.approx(0.023, abs=5e-4)
    assert d["sigma_r_d2"] == pytest.approx(0.0099, abs=1e-4)
    assert d["n"] == 5


def test_preparar_dataset():
    df = dt.leer_tabla(CSV_LARGO.encode(), "datos.csv")
    r = dt.preparar_dataset(df, dt.sugerir_mapeo(df), faltantes="descartar", atipicos="iqr")
    assert r["informe"]["k_subgrupos"] == 2
    assert not r["informe"]["n_constante"]
    assert r["descriptivos"]["N"] == 5


def test_formato_ancho_por_mapeo():
    df = dt.leer_tabla(CSV_PUNTO_COMA.encode(), "x.csv")
    m = dt.sugerir_mapeo(df)
    assert [c for c, r in m.items() if r == "valor"] == ["M1", "M2", "M3"]
    r = dt.preparar_dataset(df, m)
    assert r["informe"]["tamanos"] == [3] and r["informe"]["k_subgrupos"] == 2


def test_preparar_dataset_sin_valor_falla():
    df = pd.DataFrame({"a": ["x", "y"]})
    with pytest.raises(ValueError):
        dt.preparar_dataset(df, {"a": "ignorar"})
