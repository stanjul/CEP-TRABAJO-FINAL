"""Cartas por atributos validadas con los ejemplos de Montgomery (cap. 7)."""
import numpy as np
import pytest

from app.core import graficos_atributos as ga
from tests.datos_montgomery import (CIRCUITOS, COMPUTADORAS, COMPUTADORAS_N, JUGO_DEFECTUOSOS, JUGO_N)


class TestPJugo:
    """Jugo de naranja: p̄ = 0.2313, LCS = 0.4102, LCI = 0.0524; muestras 15 y 23 fuera."""

    res = ga.calcular_p(JUGO_DEFECTUOSOS, JUGO_N, reglas=["N1"])

    def test_limites_libro(self):
        c = self.res["cartas"]["p"]
        assert c["lc"] == pytest.approx(0.2313, abs=5e-5)
        assert c["lcs"] == pytest.approx(0.4102, abs=5e-5)
        assert c["lci"] == pytest.approx(0.0524, abs=5e-5)

    def test_puntos_fuera(self):
        assert [i + 1 for i in self.res["puntos_con_senal"]] == [15, 23]

    def test_limites_revisados(self):
        """Excluidas las muestras 15 y 23: p̄ = 0.2150, LCS = 0.3893, LCI = 0.0407."""
        rev = ga.calcular_p(JUGO_DEFECTUOSOS, JUGO_N, excluidos=[14, 22])
        c = rev["cartas"]["p"]
        assert c["lc"] == pytest.approx(0.2150, abs=5e-5)
        assert c["lcs"] == pytest.approx(0.3893, abs=5e-5)
        assert c["lci"] == pytest.approx(0.0407, abs=5e-5)


def test_np_jugo():
    """Carta np: LC = 11.57, LCS = 20.51, LCI = 2.62."""
    c = ga.calcular_np(JUGO_DEFECTUOSOS, JUGO_N)["cartas"]["np"]
    assert c["lc"] == pytest.approx(11.57, abs=5e-3)
    assert c["lcs"] == pytest.approx(20.51, abs=5e-3)
    assert c["lci"] == pytest.approx(2.62, abs=5e-3)


class TestCCircuitos:
    """Circuitos impresos: c̄ = 19.85, LCS = 33.22, LCI = 6.48; muestras 6 y 20 fuera."""

    res = ga.calcular_c(CIRCUITOS, reglas=["N1"])

    def test_limites_libro(self):
        c = self.res["cartas"]["c"]
        assert c["lc"] == pytest.approx(19.85, abs=5e-3)
        # El libro usa c̄ = 19.85 redondeado: 19.85 + 3√19.85 = 33.22. Con c̄ = 19.846 exacto: 33.211.
        assert c["lcs"] == pytest.approx(33.22, abs=0.015)
        assert c["lci"] == pytest.approx(6.48, abs=0.015)
        assert 19.85 + 3 * 19.85**0.5 == pytest.approx(33.22, abs=5e-3)
        assert 19.85 - 3 * 19.85**0.5 == pytest.approx(6.48, abs=5e-3)
        assert [i + 1 for i in self.res["puntos_con_senal"]] == [6, 20]

    def test_revisados(self):
        """Excluidas 6 y 20: c̄ = 19.67, LCS = 32.97, LCI = 6.36."""
        c = ga.calcular_c(CIRCUITOS, excluidos=[5, 19])["cartas"]["c"]
        assert c["lc"] == pytest.approx(19.67, abs=5e-3)
        assert c["lcs"] == pytest.approx(32.97, abs=5e-3)
        assert c["lci"] == pytest.approx(6.36, abs=5e-3)


def test_u_computadoras():
    """Computadoras: ū = 1.93, LCS = 3.79, LCI = 0.07."""
    c = ga.calcular_u(COMPUTADORAS, COMPUTADORAS_N)["cartas"]["u"]
    assert c["lc"] == pytest.approx(1.93, abs=5e-3)
    assert c["lcs"] == pytest.approx(3.79, abs=5e-3)
    assert c["lci"] == pytest.approx(0.07, abs=5e-3)


def test_p_con_n_variable_limites_por_muestra():
    d = [5, 8, 3, 10]
    n = [100, 200, 50, 150]
    res = ga.calcular_p(d, n)
    c = res["cartas"]["p"]
    assert res["n_variable"]
    p = sum(d) / sum(n)
    esperado = [p + 3 * np.sqrt(p * (1 - p) / ni) for ni in n]
    assert c["lcs"] == pytest.approx(esperado)
    assert c["lcs"][1] < c["lcs"][2]  # n mayor ⇒ límites más estrechos


def test_u_n_variable():
    res = ga.calcular_u([10, 20, 6], [5, 10, 2])
    assert isinstance(res["cartas"]["u"]["lcs"], list)


def test_fase_ii_atributos():
    base = ga.calcular_p(JUGO_DEFECTUOSOS, JUGO_N, excluidos=[14, 22])
    nuevo = ga.calcular_p([25, 5], JUGO_N, limites=base["limites"], reglas=["N1"])
    assert nuevo["fase"] == "II"
    assert nuevo["puntos_con_senal"] == [0]


def test_validaciones():
    with pytest.raises(ValueError):
        ga.calcular_p([60], 50)
    with pytest.raises(ValueError):
        ga.calcular_carta_atributos("np", [1, 2], [10, 20])


@pytest.mark.parametrize("tipo_dato,constante,interes,esperado", [
    ("defectuosos", False, "proporcion", "p"),
    ("defectuosos", True, "proporcion", "p"),
    ("defectuosos", True, "conteo", "np"),
    ("defectos", True, "conteo", "c"),
    ("defectos", False, "conteo", "u"),
])
def test_asistente(tipo_dato, constante, interes, esperado):
    assert ga.recomendar_grafico(tipo_dato, constante, interes)["carta"] == esperado
