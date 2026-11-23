"""ARL / ATS de la carta X̄ (Montgomery §6.2.6) y de las cartas de atributos (§7)."""
import math

import pytest

from app.core import diseno_arl as d


def test_arl0_tres_sigma():
    """Con k = 3: α = 0.0027 y ARL0 ≈ 370."""
    assert d.alfa(3) == pytest.approx(0.0027, abs=1e-4)
    assert d.arl0(3) == pytest.approx(370.4, abs=0.1)


def test_ejemplo_libro_n4_delta_1_5():
    """n = 4, k = 3, corrimiento 1.5σ ⇒ β = 0.50, ARL1 = 2; con h = 1 h, ATS = 2 h."""
    r = d.diseno(3, 4, 1.0, 1.5)
    assert r["beta"] == pytest.approx(0.50, abs=1e-6)
    assert r["arl1"] == pytest.approx(2.0, abs=1e-6)
    assert r["ats1"] == pytest.approx(2.0, abs=1e-6)


def test_formula_beta():
    """n = 5, δ = 1: β = Φ(3 − √5) − Φ(−3 − √5) = 0.7775 ⇒ ARL1 = 4.50."""
    assert d.beta(3, 5, 1.0) == pytest.approx(0.7775, abs=1e-4)
    assert d.arl1(3, 5, 1.0) == pytest.approx(4.495, abs=1e-3)


def test_sin_corrimiento_arl1_igual_arl0():
    assert d.arl1(3, 5, 0) == pytest.approx(d.arl0(3))


def test_ats_con_h():
    assert d.ats(4.0, 0.5) == 2.0


def test_curva_monotona():
    c = d.curva_arl(3, 5, tamanos_comparar=[10])
    arls = c["series"]["5"]["arl"]
    assert all(a >= b for a, b in zip(arls, arls[1:]))
    assert all(a <= b for a, b in zip(c["series"]["10"]["arl"], arls))  # n mayor detecta antes


# ---------------------------------------------------------------------------
# Cartas de atributos: ARL exacto con Binomial / Poisson (curva OC, Montgomery §7)
# ---------------------------------------------------------------------------

def _binom_cdf(x, n, p):
    """CDF binomial por suma directa (implementación independiente de scipy)."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, x + 1)) if x >= 0 else 0.0


def _poisson_cdf(x, lam):
    return sum(math.exp(-lam) * lam**i / math.factorial(i) for i in range(0, x + 1)) if x >= 0 else 0.0


def test_limites_p_jugo_montgomery():
    """Ejemplo del jugo de naranja (Montgomery §7.2), base revisada p̄ = 0.20, n = 50:
    LCS = 0.3697, LCI = 0.0303."""
    lim = d.limites_atributos("p", 0.20, 50, 3)
    assert lim["lcs"] == pytest.approx(0.3697, abs=1e-4)
    assert lim["lci"] == pytest.approx(0.0303, abs=1e-4)


def test_oc_carta_p_contra_suma_directa():
    """β(p) = P(D ≤ 18) − P(D ≤ 1) con n = 50 (n·LCS = 18.49, n·LCI = 1.52)."""
    for p1 in (0.20, 0.30, 0.40):
        r = d.diseno_atributos("p", 0.20, p1, 50, 3, 1.0)
        esperado = _binom_cdf(18, 50, p1) - _binom_cdf(1, 50, p1)
        assert r["beta"] == pytest.approx(esperado, abs=1e-9)
    r0 = d.diseno_atributos("p", 0.20, 0.20, 50, 3, 1.0)
    assert r0["arl0"] == pytest.approx(r0["arl1"])
    # Distribución discreta: α no es 0.0027.
    assert r0["alfa"] == pytest.approx(1 - (_binom_cdf(18, 50, 0.2) - _binom_cdf(1, 50, 0.2)), abs=1e-9)


def test_oc_carta_c_circuitos():
    """Circuitos (Montgomery Ej. 7.3): c̄ = 19.85 ⇒ LCS = 33.22, LCI = 6.48;
    sin señal si 7 ≤ X ≤ 33."""
    lim = d.limites_atributos("c", 19.85, 1, 3)
    assert lim["lcs"] == pytest.approx(33.22, abs=0.01)
    assert lim["lci"] == pytest.approx(6.48, abs=0.01)
    r = d.diseno_atributos("c", 19.85, 25.0, 1, 3, 0.5)
    assert r["beta"] == pytest.approx(_poisson_cdf(33, 25.0) - _poisson_cdf(6, 25.0), abs=1e-9)
    assert r["ats1"] == pytest.approx(r["arl1"] * 0.5)


def test_carta_u_escala_con_unidades():
    """u con n unidades: X ~ Poisson(n·u) y sin señal si X ≤ n·LCS."""
    r = d.diseno_atributos("u", 1.5, 3.0, 4, 3, 1.0)
    lcs = 1.5 + 3 * math.sqrt(1.5 / 4)
    esperado = _poisson_cdf(math.floor(4 * lcs), 12.0) - _poisson_cdf(math.ceil(4 * max(0, 1.5 - 3 * math.sqrt(1.5 / 4))) - 1, 12.0)
    assert r["beta"] == pytest.approx(esperado, abs=1e-9)


def test_atributos_arl_infinito_si_no_hay_senal_posible():
    """n = 2, p₀ = 0.5: LCS = 1 y LCI = 0 ⇒ ningún conteo da señal ⇒ ARL = ∞."""
    r = d.diseno_atributos("p", 0.5, 0.6, 2, 3, 1.0)
    assert math.isinf(r["arl0"]) and math.isinf(r["arl1"])


def test_carga_muestral():
    """n = 5 cada 30 min: 2 muestras/h, 10 unidades/h, 80 por turno de 8 h."""
    c = d.carga_muestral(5, 30)
    assert c["muestras_por_hora"] == 2
    assert c["unidades_por_hora"] == 10
    assert c["unidades_por_turno"] == 80


def test_textos_plan_en_lenguaje_simple():
    r = d.diseno(3, 5, 0.5, 1.0)
    t = d.textos_plan(r, d.carga_muestral(5, 30), "g", sigma=0.8)
    assert "falsa alarma cada 370 muestras" in t["falsa_alarma"]
    assert "0,800 g" in t["deteccion"] and "4,5 muestras" in t["deteccion"]
    assert "2 muestras por hora: 10 unidades por hora, 80 por turno" in t["carga"]
    assert "1 muestra por hora" in d.texto_carga(d.carga_muestral(1, 60))
    assert "2,5 unidades por hora" in d.texto_carga(d.carga_muestral(1, 24))
    ta = d.textos_plan(d.diseno_atributos("p", 0.05, 0.10, 100, 3, 1.0), d.carga_muestral(100, 60), es_porcentaje=True)
    assert "5,00 % a 10,00 %" in ta["deteccion"]


def test_duracion_legible():
    assert d.duracion_legible(0.5) == "30 minutos"
    assert d.duracion_legible(2.5) == "2,5 horas"
    assert "turnos" in d.duracion_legible(185)
    assert d.duracion_legible(math.inf).startswith("nunca")


@pytest.mark.parametrize("n,delta", [(4, 1.5), (5, 1.0)])
def test_monte_carlo_coincide_con_teoria(n, delta):
    sim = d.simular_arl(3, n, delta, replicas=4000, semilla=7)
    assert sim["ic95"][0] - 0.1 <= sim["arl_teorico"] <= sim["ic95"][1] + 0.1
    assert abs(sim["error_relativo"]) < 0.06
