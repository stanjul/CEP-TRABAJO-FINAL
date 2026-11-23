"""Muestreo de aceptación simple (Montgomery, cap. 15)."""
import pytest

from app.core import muestreo_aceptacion as ma


def test_pa_libro():
    """n = 89, c = 2, p = 0.01 ⇒ Pa = 0.9397."""
    assert ma.prob_aceptacion(0.01, 89, 2) == pytest.approx(0.9397, abs=1e-4)


def test_aoq_ati_libro():
    """N = 10 000, n = 89, c = 2, p = 0.01 ⇒ AOQ ≈ 0.0093, ATI ≈ 687."""
    assert ma.aoq(0.01, 89, 2, 10_000) == pytest.approx(0.0093, abs=1e-4)
    assert ma.ati(0.01, 89, 2, 10_000) == pytest.approx(687, abs=1)


def test_plan_del_nomograma():
    """El libro obtiene n = 89, c = 2 con el nomograma para (p1 = 0.01, 1−α = 0.95) y
    (p2 = 0.06, β = 0.10). Es una aproximación: Pa(0.01) = 0.940 y Pa(0.06) = 0.092."""
    assert ma.prob_aceptacion(0.01, 89, 2) == pytest.approx(0.94, abs=0.005)
    assert ma.prob_aceptacion(0.06, 89, 2) == pytest.approx(0.092, abs=0.005)


def test_disenar_plan_exacto():
    """La búsqueda exacta (binomial) que cumple ambos riesgos da n = 110, c = 3."""
    plan = ma.disenar_plan(0.01, 0.06, 0.05, 0.10)
    assert (plan["n"], plan["c"]) == (110, 3)
    assert plan["pa_aql"] >= 0.95
    assert plan["pa_ltpd"] <= 0.10
    # Es el menor n: con n − 1 ya no se cumple el riesgo del consumidor.
    assert ma.prob_aceptacion(0.06, plan["n"] - 1, plan["c"]) > 0.10


def test_hipergeometrica_se_aproxima_a_binomial_en_lote_grande():
    assert ma.prob_aceptacion(0.02, 50, 1, 100_000, "hipergeometrica") == pytest.approx(
        ma.prob_aceptacion(0.02, 50, 1), abs=2e-3)


def test_hipergeometrica_lote_pequeno():
    """N = 20, D = 2, n = 5, c = 0: Pa = C(18,5)/C(20,5) = 8568/15504 = 0.5526."""
    assert ma.prob_aceptacion(0.10, 5, 0, 20, "hipergeometrica") == pytest.approx(0.5526, abs=1e-4)


def test_curvas_y_aoql():
    cur = ma.curvas(89, 2, 10_000, aql=0.01, ltpd=0.06)
    assert cur["oc"]["binomial"][0] == pytest.approx(1.0)
    assert all(a >= b for a, b in zip(cur["oc"]["binomial"], cur["oc"]["binomial"][1:]))
    # AOQL de este plan ≈ 0.0155 (máximo de la curva AOQ).
    assert cur["aoql"]["valor"] == pytest.approx(0.0155, abs=5e-4)
    assert 0 < cur["p50"] < 0.06
    assert cur["en_aql"]["pa"] == pytest.approx(0.94, abs=0.01)


def test_decision_lote_y_wilson():
    r = ma.decidir_lote(2, 200, 3)
    assert r["aceptado"]
    assert r["p_hat"] == 0.01
    lo, hi = r["ic95"]
    assert lo == pytest.approx(0.0027, abs=2e-4)
    assert hi == pytest.approx(0.0357, abs=3e-4)
    assert not ma.decidir_lote(4, 200, 3)["aceptado"]


def test_validaciones():
    with pytest.raises(ValueError):
        ma.disenar_plan(0.05, 0.01)
    with pytest.raises(ValueError):
        ma.prob_aceptacion(0.1, 10, 1, None, "hipergeometrica")
