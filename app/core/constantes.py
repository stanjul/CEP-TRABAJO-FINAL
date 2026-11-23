"""Constantes tabuladas para cartas de control por variables.

Fuente: Montgomery, D. C., *Introduction to Statistical Quality Control*, Apéndice VI
("Factors for Constructing Variables Control Charts"), n = 2 … 25.

Definiciones (σ = desviación estándar del proceso, R = rango, s = desviación muestral):

- d2 = E[R/σ]                 → σ̂ = R̄ / d2
- d3 = DE[R/σ]                → σ_R = d3·σ
- c4 = E[s/σ] = √(2/(n−1))·Γ(n/2)/Γ((n−1)/2) → σ̂ = s̄ / c4
- A2 = 3 / (d2·√n)            → límites X̄ con R̄:  X̿ ± A2·R̄
- A3 = 3 / (c4·√n)            → límites X̄ con s̄:  X̿ ± A3·s̄
- D3 = máx(0, 1 − 3·d3/d2), D4 = 1 + 3·d3/d2   → carta R: [D3·R̄, D4·R̄]
- B3 = máx(0, 1 − 3·√(1−c4²)/c4), B4 = 1 + 3·√(1−c4²)/c4 → carta S: [B3·s̄, B4·s̄]

Los valores se guardan tal como aparecen en la tabla del libro (no se calculan en tiempo
de ejecución). El test `tests/test_constantes.py` verifica que coinciden, a la precisión
tabulada, con las fórmulas anteriores evaluadas por integración numérica.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

N_MIN = 2
N_MAX = 25

# n: (A2, A3, B3, B4, D3, D4, d2, d3, c4)
_TABLA: dict[int, tuple[float, ...]] = {
    2: (1.880, 2.659, 0.000, 3.267, 0.000, 3.267, 1.128, 0.853, 0.7979),
    3: (1.023, 1.954, 0.000, 2.568, 0.000, 2.574, 1.693, 0.888, 0.8862),
    4: (0.729, 1.628, 0.000, 2.266, 0.000, 2.282, 2.059, 0.880, 0.9213),
    5: (0.577, 1.427, 0.000, 2.089, 0.000, 2.114, 2.326, 0.864, 0.9400),
    6: (0.483, 1.287, 0.030, 1.970, 0.000, 2.004, 2.534, 0.848, 0.9515),
    7: (0.419, 1.182, 0.118, 1.882, 0.076, 1.924, 2.704, 0.833, 0.9594),
    8: (0.373, 1.099, 0.185, 1.815, 0.136, 1.864, 2.847, 0.820, 0.9650),
    9: (0.337, 1.032, 0.239, 1.761, 0.184, 1.816, 2.970, 0.808, 0.9693),
    10: (0.308, 0.975, 0.284, 1.716, 0.223, 1.777, 3.078, 0.797, 0.9727),
    11: (0.285, 0.927, 0.321, 1.679, 0.256, 1.744, 3.173, 0.787, 0.9754),
    12: (0.266, 0.886, 0.354, 1.646, 0.283, 1.717, 3.258, 0.778, 0.9776),
    13: (0.249, 0.850, 0.382, 1.618, 0.307, 1.693, 3.336, 0.770, 0.9794),
    14: (0.235, 0.817, 0.406, 1.594, 0.328, 1.672, 3.407, 0.763, 0.9810),
    15: (0.223, 0.789, 0.428, 1.572, 0.347, 1.653, 3.472, 0.756, 0.9823),
    16: (0.212, 0.763, 0.448, 1.552, 0.363, 1.637, 3.532, 0.750, 0.9835),
    17: (0.203, 0.739, 0.466, 1.534, 0.378, 1.622, 3.588, 0.744, 0.9845),
    18: (0.194, 0.718, 0.482, 1.518, 0.391, 1.608, 3.640, 0.739, 0.9854),
    19: (0.187, 0.698, 0.497, 1.503, 0.403, 1.597, 3.689, 0.734, 0.9862),
    20: (0.180, 0.680, 0.510, 1.490, 0.415, 1.585, 3.735, 0.729, 0.9869),
    21: (0.173, 0.663, 0.523, 1.477, 0.425, 1.575, 3.778, 0.724, 0.9876),
    22: (0.167, 0.647, 0.534, 1.466, 0.434, 1.566, 3.819, 0.720, 0.9882),
    23: (0.162, 0.633, 0.545, 1.455, 0.443, 1.557, 3.858, 0.716, 0.9887),
    24: (0.157, 0.619, 0.555, 1.445, 0.451, 1.548, 3.895, 0.712, 0.9892),
    25: (0.153, 0.606, 0.565, 1.435, 0.459, 1.541, 3.931, 0.708, 0.9896),
}


@dataclass(frozen=True)
class Constantes:
    """Factores de la tabla para un tamaño de subgrupo n."""

    n: int
    A2: float
    A3: float
    B3: float
    B4: float
    D3: float
    D4: float
    d2: float
    d3: float
    c4: float

    def a_dict(self) -> dict:
        return asdict(self)


def constantes(n: int) -> Constantes:
    """Devuelve los factores tabulados para un subgrupo de tamaño n (2 ≤ n ≤ 25).

    Lanza ValueError si n está fuera de la tabla: en ese caso conviene usar una carta
    I-MR (n = 1) o, para n > 25, la aproximación c4 ≈ 4(n−1)/(4n−3).
    """
    if n not in _TABLA:
        raise ValueError(f"n={n} fuera de la tabla de constantes ({N_MIN}–{N_MAX}).")
    return Constantes(n, *_TABLA[n])


def tabla_completa() -> list[dict]:
    """Toda la tabla como lista de diccionarios (para mostrarla en la interfaz)."""
    return [constantes(n).a_dict() for n in range(N_MIN, N_MAX + 1)]
