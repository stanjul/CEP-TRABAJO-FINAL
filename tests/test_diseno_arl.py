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


# ---------------------------------------------------------------------------
# Carga muestral objetivo: potencia y detección en m muestras / en un horizonte
# ---------------------------------------------------------------------------

def test_evaluar_carga_ejemplo_montgomery():
    """Montgomery (n = 4, k = 3, δ = 1,5): β ≈ 0,50, potencia ≈ 0,50 y ARL₁ ≈ 2. Con h = 60 min,
    ATS₁ = 2 h y la probabilidad de detectar en 3 muestras es 1 − β³ ≈ 0,875."""
    e = d.evaluar_carga(4, 60, 3.0, 1.5, m=3)
    assert e["beta"] == pytest.approx(0.5, abs=0.002)
    assert e["potencia"] == pytest.approx(0.5, abs=0.002)
    assert e["arl1"] == pytest.approx(2.0, abs=0.01)
    assert e["ats1_horas"] == pytest.approx(2.0, abs=0.01)
    assert e["p_m"] == pytest.approx(1 - e["beta"] ** 3)
    assert e["carga_hora"] == pytest.approx(4.0)
    assert e["ats0_horas"] == pytest.approx(370.4, abs=0.1)


def test_evaluar_carga_horizonte_cuenta_muestras_enteras():
    """En 70 min con muestras cada 30 min se toman 2 muestras: P = 1 − β²."""
    e = d.evaluar_carga(5, 30, 3.0, 1.0, m=5, horizonte_min=70)
    assert e["muestras_en_horizonte"] == 2
    assert e["p_horizonte"] == pytest.approx(1 - e["beta"] ** 2)


def test_caminos_carga():
    """Carga actual 5 cada 30 min = 10 u/h; objetivo 20 u/h → A: 10 cada 30 min; B: 5 cada 15 min."""
    r = d.caminos_carga(5, 30, 20)
    assert (r["a"]["n"], r["a"]["frecuencia_min"]) == (10, 30)
    assert (r["b"]["n"], r["b"]["frecuencia_min"]) == (5, 15)
    assert r["a"]["carga_hora"] == pytest.approx(20) and r["b"]["carga_hora"] == pytest.approx(20)
    # Redondeos: objetivo 13 u/h → n_A = 6.5 → 6 (redondeo bancario de Python: 6); h_B = 300/13 ≈ 23 min.
    r = d.caminos_carga(5, 30, 13)
    assert r["a"]["n"] in (6, 7) and r["b"]["frecuencia_min"] == 23
    # Valores individuales: solo existe el camino de reducir el intervalo.
    r = d.caminos_carga(1, 60, 2, n_fijo=True)
    assert r["a"] is None and r["b"]["frecuencia_min"] == 30
    with pytest.raises(ValueError):
        d.caminos_carga(5, 30, 0)


def test_comparar_carga_caso_peso():
    """Peso de llenado (σ = 2,651 mL), cambio de 2 mL, carga de 10 a 20 u/h, horizonte 2,5 h:
    aumentar n detecta más (≈79 % frente a ≈63 %) y reducir el intervalo duplica las falsas alarmas."""
    r = d.comparar_carga(5, 30, 3.0, 2.651, 2.0, 20.0, m=5)
    act, a, b = r["planes"]["actual"], r["planes"]["a"], r["planes"]["b"]
    assert r["delta"] == pytest.approx(2.0 / 2.651)
    assert act["potencia"] == pytest.approx(0.095, abs=0.002)
    assert a["potencia"] == pytest.approx(0.270, abs=0.002)
    assert b["potencia"] == pytest.approx(act["potencia"])           # mismo n: misma potencia por muestra
    assert act["p_m"] == pytest.approx(0.392, abs=0.002)
    assert a["p_m"] == pytest.approx(0.792, abs=0.002)
    assert r["horizonte_min"] == 150
    assert b["muestras_en_horizonte"] == 10 and b["p_horizonte"] == pytest.approx(0.630, abs=0.002)
    assert a["p_horizonte"] > b["p_horizonte"]
    assert b["ats0_horas"] == pytest.approx(act["ats0_horas"] / 2)
    # Curvas: potencia creciente con el cambio y acumulada creciente con el tiempo.
    pot = r["curva_potencia"]["series"]["a"]
    assert pot[0] == pytest.approx(d.alfa(3.0)) and all(x <= y + 1e-12 for x, y in zip(pot, pot[1:]))
    acum = r["curva_acumulada"]["series"]["b"]
    assert acum[0] == 0 and all(x <= y + 1e-12 for x, y in zip(acum, acum[1:]))
    textos = d.textos_carga(r, "mL", 0)
    assert any("aumentar n" in t for t in textos) and any("falsas alarmas" in t for t in textos)


def test_comparar_carga_valida_entradas():
    with pytest.raises(ValueError):
        d.comparar_carga(5, 30, 3.0, 0, 2.0, 20.0)
    with pytest.raises(ValueError):
        d.comparar_carga(5, 30, 3.0, 2.0, 0, 20.0)
