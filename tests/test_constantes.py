"""La tabla de constantes debe coincidir con las fórmulas evaluadas numéricamente."""
import math

import pytest
from scipy import integrate, stats

from app.core.constantes import N_MAX, N_MIN, constantes, tabla_completa

Phi = stats.norm.cdf


def d2_numerico(n):
    """d2 = ∫ [1 − (1 − Φ(x))ⁿ − Φ(x)ⁿ] dx (valor esperado del rango relativo)."""
    return integrate.quad(lambda x: 1 - (1 - Phi(x)) ** n - Phi(x) ** n, -12, 12, limit=200)[0]


def c4_exacto(n):
    """c4 = √(2/(n−1)) · Γ(n/2) / Γ((n−1)/2)."""
    return math.sqrt(2 / (n - 1)) * math.exp(math.lgamma(n / 2) - math.lgamma((n - 1) / 2))


@pytest.mark.parametrize("n", range(N_MIN, N_MAX + 1))
def test_constantes_consistentes_con_formulas(n):
    c = constantes(n)
    d2 = d2_numerico(n)
    c4 = c4_exacto(n)
    assert c.d2 == pytest.approx(d2, abs=6e-4)
    assert c.c4 == pytest.approx(c4, abs=6e-5)
    assert c.A2 == pytest.approx(3 / (d2 * math.sqrt(n)), abs=6e-4)
    assert c.A3 == pytest.approx(3 / (c4 * math.sqrt(n)), abs=6e-4)
    b = 3 * math.sqrt(1 - c4**2) / c4
    assert c.B4 == pytest.approx(1 + b, abs=6e-4)
    assert c.B3 == pytest.approx(max(0, 1 - b), abs=6e-4)
    # D3 + D4 = 2 cuando D3 > 0 (simetría de la fórmula), con tolerancia de redondeo de la tabla.
    if c.D3 > 0:
        assert c.D3 + c.D4 == pytest.approx(2, abs=2e-3)
    assert c.D4 == pytest.approx(1 + 3 * c.d3 / c.d2, abs=2e-3)


def test_valores_conocidos_n5():
    """Fila n = 5 de la tabla (la más usada en el curso)."""
    c = constantes(5)
    assert (c.A2, c.A3, c.B3, c.B4, c.D3, c.D4, c.d2, c.c4) == (0.577, 1.427, 0.0, 2.089, 0.0, 2.114, 2.326, 0.94)


def test_fuera_de_tabla():
    with pytest.raises(ValueError):
        constantes(1)
    with pytest.raises(ValueError):
        constantes(26)


def test_tabla_completa():
    assert len(tabla_completa()) == 24
