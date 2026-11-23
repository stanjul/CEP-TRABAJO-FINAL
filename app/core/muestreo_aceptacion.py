"""Muestreo de aceptación por atributos: plan simple (N, n, c) (Montgomery, cap. 15).

De un lote de N unidades con fracción defectuosa p se inspecciona una muestra de n; el
lote se acepta si el número de defectuosos d es ≤ c.

Probabilidad de aceptación (curva OC):
    Binomial (tipo B, lote grande):   Pa = Σ_{d=0}^{c} C(n,d)·p^d·(1−p)^(n−d)
    Hipergeométrica (tipo A, lote finito, D = round(N·p) defectuosos en el lote):
                                      Pa = Σ_{d=0}^{c} C(D,d)·C(N−D, n−d) / C(N,n)
    Poisson (aproximación):           Pa = Σ_{d=0}^{c} e^(−np)(np)^d / d!

Con inspección rectificadora (los lotes rechazados se inspeccionan al 100 %):
    AOQ  = Pa·p·(N − n)/N            (calidad de salida promedio)
    AOQL = máx_p AOQ(p)              (límite de la calidad de salida promedio)
    ATI  = n + (1 − Pa)·(N − n)      (inspección total promedio por lote)

Diseño del plan a partir de dos puntos de la OC: (AQL, 1 − α) y (LTPD, β). Se buscan el
menor c y, para ese c, el menor n tales que Pa(LTPD) ≤ β y Pa(AQL) ≥ 1 − α. Como el n que
cumple el riesgo del consumidor crece con c, el primer c factible da el plan de menor n.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from scipy import stats

MODELOS = ("binomial", "hipergeometrica", "poisson")


def prob_aceptacion(p: float, n: int, c: int, N: int | None = None, modelo: str = "binomial") -> float:
    """Pa para una fracción defectuosa p según el modelo indicado."""
    if not 0 <= p <= 1:
        raise ValueError("p debe estar entre 0 y 1.")
    if modelo == "binomial":
        return float(stats.binom.cdf(c, n, p))
    if modelo == "poisson":
        return float(stats.poisson.cdf(c, n * p))
    if modelo == "hipergeometrica":
        if N is None or N < n:
            raise ValueError("El modelo hipergeométrico requiere N ≥ n.")
        D = int(round(N * p))
        return float(stats.hypergeom.cdf(c, N, D, n))
    raise ValueError(f"Modelo desconocido: {modelo}")


def aoq(p: float, n: int, c: int, N: int, modelo: str = "binomial") -> float:
    """Calidad de salida promedio: AOQ = Pa·p·(N − n)/N."""
    return prob_aceptacion(p, n, c, N, modelo) * p * (N - n) / N


def ati(p: float, n: int, c: int, N: int, modelo: str = "binomial") -> float:
    """Inspección total promedio: ATI = n + (1 − Pa)(N − n)."""
    return n + (1 - prob_aceptacion(p, n, c, N, modelo)) * (N - n)


def _grilla(p_max: float, puntos: int) -> np.ndarray:
    return np.linspace(0, p_max, puntos)


def curvas(n: int, c: int, N: int | None = None, p_max: float | None = None, puntos: int = 101,
           aql: float | None = None, ltpd: float | None = None) -> dict:
    """Curvas OC (binomial, Poisson e hipergeométrica si hay N), AOQ y ATI, más AOQL.

    Si se dan AQL y LTPD se informan Pa en esos puntos y los riesgos α y β del plan.
    """
    if p_max is None:
        p_max = min(1.0, max(0.05, 3 * (c + 1) / n, 1.5 * (ltpd or 0)))
    ps = _grilla(p_max, puntos)
    res = {"n": n, "c": c, "N": N, "p": ps.tolist(),
           "oc": {"binomial": [prob_aceptacion(p, n, c, modelo="binomial") for p in ps],
                  "poisson": [prob_aceptacion(p, n, c, modelo="poisson") for p in ps]}}
    if N is not None:
        res["oc"]["hipergeometrica"] = [prob_aceptacion(p, n, c, N, "hipergeometrica") for p in ps]
        aoqs = [aoq(p, n, c, N) for p in ps]
        res["aoq"] = aoqs
        res["ati"] = [ati(p, n, c, N) for p in ps]
        # AOQL: máximo refinado con una grilla fina alrededor del máximo de la gruesa.
        i = int(np.argmax(aoqs))
        fina = np.linspace(ps[max(0, i - 1)], ps[min(len(ps) - 1, i + 1)], 201)
        valores = [aoq(p, n, c, N) for p in fina]
        j = int(np.argmax(valores))
        res["aoql"] = {"valor": float(valores[j]), "p": float(fina[j])}
    # Punto de indiferencia p50 (Pa = 0.5), por bisección sobre la OC binomial.
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if prob_aceptacion(mid, n, c) > 0.5 else (lo, mid)
    res["p50"] = (lo + hi) / 2
    if aql is not None:
        pa = prob_aceptacion(aql, n, c, N, "hipergeometrica" if N else "binomial")
        res["en_aql"] = {"p": aql, "pa": pa, "alfa_real": 1 - pa}
    if ltpd is not None:
        pb = prob_aceptacion(ltpd, n, c, N, "hipergeometrica" if N else "binomial")
        res["en_ltpd"] = {"p": ltpd, "pa": pb, "beta_real": pb}
    return res


def disenar_plan(aql: float, ltpd: float, alfa: float = 0.05, beta: float = 0.10,
                 modelo: str = "binomial", N: int | None = None, n_max: int = 5000, c_max: int = 60) -> dict:
    """Plan simple (n, c) de menor tamaño que cumple Pa(AQL) ≥ 1 − α y Pa(LTPD) ≤ β."""
    if not 0 < aql < ltpd < 1:
        raise ValueError("Debe cumplirse 0 < AQL < LTPD < 1.")
    tope = n_max if N is None else min(n_max, N)
    for c in range(c_max + 1):
        # Menor n que cumple el riesgo del consumidor (Pa decrece con n).
        lo, hi = c + 1, tope
        if prob_aceptacion(ltpd, hi, c, N, modelo) > beta:
            continue
        while lo < hi:
            mid = (lo + hi) // 2
            if prob_aceptacion(ltpd, mid, c, N, modelo) <= beta:
                hi = mid
            else:
                lo = mid + 1
        n = lo
        pa_aql = prob_aceptacion(aql, n, c, N, modelo)
        if pa_aql >= 1 - alfa:
            pa_ltpd = prob_aceptacion(ltpd, n, c, N, modelo)
            return {
                "n": int(n), "c": int(c), "modelo": modelo,
                "pa_aql": pa_aql, "pa_ltpd": pa_ltpd,
                "alfa_real": 1 - pa_aql, "beta_real": pa_ltpd,
                "aql": aql, "ltpd": ltpd, "alfa": alfa, "beta": beta,
                "razon_discriminacion": ltpd / aql,
            }
    raise ValueError("No se encontró un plan dentro de los límites de búsqueda.")


def ic_wilson(d: int, n: int, confianza: float = 0.95) -> tuple[float, float]:
    """Intervalo de Wilson para una proporción p̂ = d/n:
    (p̂ + z²/2n ± z·√(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n)."""
    if n <= 0:
        raise ValueError("n debe ser positivo.")
    z = stats.norm.ppf(1 - (1 - confianza) / 2)
    p = d / n
    centro = p + z * z / (2 * n)
    radio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    den = 1 + z * z / n
    return max(0.0, (centro - radio) / den), min(1.0, (centro + radio) / den)


def decidir_lote(d: int, n: int, c: int) -> dict:
    """Dictamen del lote: aceptar si d ≤ c. Incluye p̂ e IC de Wilson al 95 %."""
    if d < 0 or d > n:
        raise ValueError("d debe estar entre 0 y n.")
    lo, hi = ic_wilson(d, n)
    return {
        "aceptado": d <= c,
        "dictamen": "ACEPTADO" if d <= c else "RECHAZADO",
        "condicion": f"d ({d}) {'≤' if d <= c else '>'} c ({c})",
        "p_hat": d / n,
        "ic95": [lo, hi],
    }


def evaluar_plan(n: int, c: int, ps: Sequence[float], N: int | None = None) -> list[dict]:
    """Tabla Pa / AOQ / ATI para una lista de fracciones defectuosas."""
    filas = []
    for p in ps:
        fila = {"p": p, "pa_binomial": prob_aceptacion(p, n, c)}
        if N is not None:
            fila.update({"pa_hipergeometrica": prob_aceptacion(p, n, c, N, "hipergeometrica"),
                         "aoq": aoq(p, n, c, N), "ati": ati(p, n, c, N)})
        filas.append(fila)
    return filas
