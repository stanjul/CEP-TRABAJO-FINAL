"""Análisis de capacidad del proceso (Montgomery, cap. 8).

Con LEI/LES los límites de especificación y μ̂ = X̿ (media de todas las observaciones),
σ se estima con la variación dentro de los subgrupos (la misma σ de la carta de control):

      σ̂ = R̄/d2  (método "rbar"),   σ̂ = s̄/c4  (método "sbar"),   σ̂ = MR̄/1.128 (método "mr", n = 1)

o es la σ fijada por el ingeniero (método "fijada").

Índices de capacidad potencial y real (alcance del curso: Cp, Cpk, Cpu, Cpl):
      Cp  = (LES − LEI) / 6σ̂
      Cpu = (LES − μ̂) / 3σ̂,    Cpl = (μ̂ − LEI) / 3σ̂,    Cpk = mín(Cpu, Cpl)
Índice de Taguchi: Cpm = (LES − LEI) / (6·√(σ̂² + (μ̂ − T)²)).
Descentrado: k = |m − μ̂| / ((LES − LEI)/2), con m = (LES + LEI)/2.

Fracción no conforme esperada (suponiendo normalidad):
      p = Φ((LEI − μ̂)/σ̂) + 1 − Φ((LES − μ̂)/σ̂),   ppm = 10⁶·p
Nivel sigma: Z = 3·Cpk.
La desviación estándar muestral s = √(Σ(xᵢ − x̄)²/(N − 1)) se informa solo como dato descriptivo.

Veredicto (criterio usual): Cpk ≥ 1.33 capaz; 1.00 ≤ Cpk < 1.33 marginal; Cpk < 1 no capaz.
Los índices solo tienen sentido si el proceso está bajo control estadístico.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np
from scipy import stats

from .constantes import constantes

UMBRAL_CAPAZ = 1.33
UMBRAL_MARGINAL = 1.00


def sigma_dentro(subgrupos: Sequence[Iterable[float]], metodo: str = "rbar") -> float:
    """σ dentro de subgrupos: R̄/d2, s̄/c4 (n constante) o MR̄/1.128 (individuales en orden)."""
    grupos = [np.asarray(list(g), dtype=float) for g in subgrupos]
    grupos = [g[~np.isnan(g)] for g in grupos]
    if metodo == "mr":
        x = np.concatenate(grupos)
        if x.size < 2:
            raise ValueError("Se necesitan al menos 2 observaciones.")
        return float(np.mean(np.abs(np.diff(x))) / constantes(2).d2)
    tam = {g.size for g in grupos if g.size > 0}
    if len(tam) != 1:
        raise ValueError("σ dentro con R̄/d2 o s̄/c4 requiere subgrupos de igual tamaño.")
    n = tam.pop()
    if n < 2:
        return sigma_dentro(subgrupos, "mr")
    cst = constantes(n)
    if metodo == "rbar":
        return float(np.mean([np.ptp(g) for g in grupos if g.size]) / cst.d2)
    if metodo == "sbar":
        return float(np.mean([g.std(ddof=1) for g in grupos if g.size]) / cst.c4)
    raise ValueError(f"Método de σ desconocido: {metodo}")


def indices(mu: float, sigma: float, lei: float | None = None, les: float | None = None) -> dict:
    """Cp, Cpu, Cpl y Cpk para una media y una σ dadas.

    Con especificación unilateral Cp no está definido (None) y Cpk es el índice del lado
    especificado.
    """
    if sigma <= 0:
        raise ValueError("σ debe ser positiva.")
    cpu = (les - mu) / (3 * sigma) if les is not None else None
    cpl = (mu - lei) / (3 * sigma) if lei is not None else None
    cp = (les - lei) / (6 * sigma) if (les is not None and lei is not None) else None
    lados = [v for v in (cpu, cpl) if v is not None]
    if not lados:
        raise ValueError("Se necesita al menos un límite de especificación.")
    return {"cp": cp, "cpu": cpu, "cpl": cpl, "cpk": min(lados)}


def fraccion_no_conforme(mu: float, sigma: float, lei: float | None, les: float | None) -> dict:
    """Fracción esperada fuera de especificación bajo normalidad (y en ppm)."""
    bajo = float(stats.norm.cdf((lei - mu) / sigma)) if lei is not None else 0.0
    sobre = float(stats.norm.sf((les - mu) / sigma)) if les is not None else 0.0
    return {"bajo_lei": bajo, "sobre_les": sobre, "total": bajo + sobre, "ppm": 1e6 * (bajo + sobre)}


def veredicto(cpk: float) -> dict:
    """Clasificación del proceso según Cpk."""
    if cpk >= UMBRAL_CAPAZ:
        return {"nivel": "capaz", "texto": f"Proceso capaz (Cpk = {cpk:.2f} ≥ {UMBRAL_CAPAZ})", "semaforo": "verde"}
    if cpk >= UMBRAL_MARGINAL:
        return {"nivel": "marginal",
                "texto": f"Proceso marginalmente capaz ({UMBRAL_MARGINAL} ≤ Cpk = {cpk:.2f} < {UMBRAL_CAPAZ})",
                "semaforo": "ambar"}
    return {"nivel": "no_capaz", "texto": f"Proceso no capaz (Cpk = {cpk:.2f} < {UMBRAL_MARGINAL})", "semaforo": "rojo"}


def analizar_capacidad(
    subgrupos: Sequence[Iterable[float]],
    lei: float | None,
    les: float | None,
    objetivo: float | None = None,
    metodo: str = "rbar",
    en_control: bool | None = None,
    sigma: float | None = None,
) -> dict:
    """Estudio completo de capacidad a partir de los subgrupos.

    Devuelve Cp, Cpk, Cpu y Cpl (con σ dentro de subgrupos, o la `sigma` fijada por el
    ingeniero si se indica), Cpm, el descentrado k, la fracción no conforme esperada (ppm),
    la observada, el nivel sigma y el veredicto. `en_control=False` agrega una advertencia.
    """
    grupos = [np.asarray(list(g), dtype=float) for g in subgrupos]
    x = np.concatenate(grupos)
    x = x[~np.isnan(x)]
    if x.size < 2:
        raise ValueError("No hay datos suficientes.")
    mu = float(x.mean())
    if sigma is not None:
        if not sigma > 0:
            raise ValueError("σ debe ser positiva.")
        s_dentro, metodo = float(sigma), "fijada"
    else:
        s_dentro = sigma_dentro(grupos, metodo)

    corto = indices(mu, s_dentro, lei, les)

    cpm = None
    k = None
    if lei is not None and les is not None:
        t = objetivo if objetivo is not None else (lei + les) / 2
        cpm = (les - lei) / (6 * math.sqrt(s_dentro**2 + (mu - t) ** 2))
        k = abs((les + lei) / 2 - mu) / ((les - lei) / 2)

    bajo = int((x < lei).sum()) if lei is not None else 0
    sobre = int((x > les).sum()) if les is not None else 0
    observados = bajo + sobre
    advertencias = []
    if en_control is False:
        advertencias.append("El proceso no está bajo control estadístico: los índices no son confiables.")

    return {
        "N": int(x.size),
        "media": mu,
        "mediana": float(np.median(x)),
        "minimo": float(x.min()),
        "maximo": float(x.max()),
        "lei": lei,
        "les": les,
        "objetivo": objetivo,
        "metodo_sigma": metodo,
        "sigma_dentro": s_dentro,
        "desviacion_estandar": float(x.std(ddof=1)),  # descriptivo, no se usa en los índices
        "indices": corto,
        "cpm": cpm,
        "k_descentrado": k,
        "ppm_esperado": fraccion_no_conforme(mu, s_dentro, lei, les),
        "observado": {"fuera": observados, "bajo_lei": bajo, "sobre_les": sobre, "ppm": 1e6 * observados / x.size},
        "nivel_sigma": 3 * corto["cpk"],
        "veredicto": veredicto(corto["cpk"]),
        "advertencias": advertencias,
    }
