"""Validación de supuestos con datos simulados de propiedades conocidas."""
import numpy as np
import pytest
from scipy import stats

from app.core import supuestos as sp
from tests.datos_montgomery import ANILLOS


@pytest.fixture
def normales():
    return np.random.default_rng(42).normal(500, 1, 200)


def test_normalidad_datos_normales(normales):
    r = sp.normalidad(normales)
    assert r["es_normal"]
    assert r["pruebas"]["shapiro_wilk"]["p_valor"] > 0.05
    # Coincide con scipy.
    assert r["pruebas"]["shapiro_wilk"]["estadistico"] == pytest.approx(stats.shapiro(normales).statistic)


def test_normalidad_rechaza_exponencial():
    x = np.random.default_rng(1).exponential(1, 200)
    r = sp.normalidad(x)
    assert not r["es_normal"]
    assert r["pruebas_que_rechazan"] == 3
    assert r["forma"]["asimetria"] > 1


def test_anillos_normales():
    """Los anillos de pistón se modelan como normales en el libro."""
    x = np.concatenate(ANILLOS)
    assert sp.normalidad(x)["es_normal"]


def test_qq_bandas(normales):
    q = sp.qq_normal(normales)
    assert len(q["teoricos"]) == 200
    assert q["r_qq"] > 0.99
    assert q["fraccion_dentro_bandas"] > 0.9
    assert all(a <= b for a, b in zip(q["banda_inf"], q["banda_sup"]))


def test_independencia_ruido_blanco(normales):
    r = sp.independencia(normales)
    assert r["es_independiente"]
    assert 1.5 <= r["durbin_watson"]["d"] <= 2.5


def test_independencia_detecta_ar1():
    rng = np.random.default_rng(5)
    e = rng.normal(0, 1, 300)
    x = np.zeros(300)
    for t in range(1, 300):
        x[t] = 0.8 * x[t - 1] + e[t]
    r = sp.independencia(x)
    assert not r["es_independiente"]
    assert r["ljung_box"]["p_valor"] < 0.001
    assert r["durbin_watson"]["d"] < 1.5
    assert r["acf"]["r"][0] > 0.6


def test_rachas_aleatorias(normales):
    r = sp.rachas(normales)
    assert r["es_aleatorio"]
    assert r["n_sobre"] == r["n_bajo"] == 100


def test_rachas_detecta_tendencia():
    x = np.linspace(0, 10, 60) + np.random.default_rng(2).normal(0, 0.5, 60)
    r = sp.rachas(x)
    assert not r["es_aleatorio"]
    assert r["tendencia"]["hay_tendencia"]
    assert r["rachas_observadas"] < r["rachas_esperadas"]


def test_rachas_formula_esperada():
    """E[R] = 2·n1·n2/(n1+n2) + 1 con una secuencia alternada exacta."""
    x = [1, -1] * 10
    r = sp.rachas(x)
    assert r["rachas_esperadas"] == pytest.approx(2 * 10 * 10 / 20 + 1)
    assert r["rachas_observadas"] == 20
    assert r["patron"].startswith("Oscilación")


def test_box_cox():
    x = np.random.default_rng(3).lognormal(0, 0.5, 300)
    r = sp.box_cox(x)
    assert r["aplicable"]
    assert r["recomendar_transformar"]
    assert abs(r["lambda"]) < 0.3  # lognormal ⇒ λ ≈ 0 (logaritmo)
    assert not sp.box_cox(-x)["aplicable"]


def test_box_cox_normal_no_transforma(normales):
    assert not sp.box_cox(normales)["recomendar_transformar"]


def test_diagnostico_global(normales):
    r = sp.diagnostico(normales)
    assert r["apto_shewhart"]
    assert r["problemas"] == []


def test_minimo_de_datos():
    with pytest.raises(ValueError):
        sp.normalidad([1, 2, 3])
