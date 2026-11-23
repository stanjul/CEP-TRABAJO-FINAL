"""Cartas de control por atributos: p, np, c y u (Montgomery, cap. 7).

Notación: m muestras; dᵢ = número de unidades defectuosas (p, np) o de defectos (c, u);
nᵢ = tamaño de la muestra (p, np) o número de unidades de inspección (u).

    p :  p̂ᵢ = dᵢ/nᵢ,   p̄ = Σdᵢ/Σnᵢ,   LC = p̄,   LCS/LCI = p̄ ± k·√(p̄(1−p̄)/nᵢ)
    np:  n constante,  LC = n·p̄,       LCS/LCI = n·p̄ ± k·√(n·p̄(1−p̄))
    c :  c̄ = Σcᵢ/m,                     LCS/LCI = c̄ ± k·√c̄
    u :  uᵢ = cᵢ/nᵢ,   ū = Σcᵢ/Σnᵢ,     LCS/LCI = ū ± k·√(ū/nᵢ)

Si nᵢ varía, las cartas p y u tienen límites variables (uno por muestra). Un LCI negativo se
reemplaza por 0. La σ de cada punto (para las reglas de zonas) es la raíz que aparece en
la fórmula de los límites.

El resultado tiene la misma forma que el de `graficos_variables`, con una sola carta.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np

from .reglas import PRESETS, evaluar_reglas, puntos_con_senal

TIPOS = ("p", "np", "c", "u")


def _mascara(m: int, excluidos: Iterable[int]) -> np.ndarray:
    mascara = np.ones(m, dtype=bool)
    for i in excluidos:
        if 0 <= int(i) < m:
            mascara[int(i)] = False
    return mascara


def _lista(a) -> float | list[float]:
    """Escalar si todos los valores son iguales (límites constantes), si no una lista."""
    arr = np.asarray(a, dtype=float)
    if arr.ndim == 0:
        return float(arr)
    return float(arr[0]) if np.allclose(arr, arr[0]) else [float(v) for v in arr]


def _resultado(tipo, nombre, valores, lc, lcs, lci, sigma, reglas, incl, excluidos, limites, fase, extra=None):
    viol = evaluar_reglas(valores, lc, lcs, lci, sigma, reglas, incl)
    res = {
        "tipo": tipo,
        "fase": fase,
        "cartas": {
            tipo: {
                "nombre": nombre,
                "valores": [float(v) for v in valores],
                "lc": _lista(lc),
                "lcs": _lista(lcs),
                "lci": _lista(lci),
                "sigma": _lista(sigma),
                "violaciones": viol,
            }
        },
        "excluidos": sorted(int(i) for i in excluidos),
        "puntos_con_senal": puntos_con_senal(viol),
        "limites": limites,
    }
    if extra:
        res.update(extra)
    return res


def calcular_p(
    defectuosos: Sequence[float],
    tamanos: Sequence[float] | float,
    excluidos: Iterable[int] = (),
    k: float = 3.0,
    limites: dict | None = None,
    reglas: Iterable[str] = PRESETS["nelson"],
) -> dict:
    """Carta p (fracción defectuosa), con límites variables si nᵢ cambia.

    p̄ = Σdᵢ/Σnᵢ sobre las muestras incluidas; LCS/LCI = p̄ ± k·√(p̄(1−p̄)/nᵢ),
    recortados a [0, 1]. En Fase II se usa el p̄ congelado en `limites["p_barra"]`.
    """
    excluidos = list(excluidos)
    d = np.asarray(defectuosos, dtype=float)
    n = np.broadcast_to(np.asarray(tamanos, dtype=float), d.shape).astype(float)
    if np.any(d > n) or np.any(d < 0):
        raise ValueError("Cada número de defectuosos debe estar entre 0 y n.")
    incl = _mascara(d.size, excluidos)
    if limites is None:
        p_barra = float(d[incl].sum() / n[incl].sum())
        limites = {"tipo": "p", "k": k, "p_barra": p_barra, "m_usados": int(incl.sum())}
        fase = "I"
    else:
        p_barra, k, fase = float(limites["p_barra"]), float(limites.get("k", k)), "II"
    sigma = np.sqrt(p_barra * (1 - p_barra) / n)
    lcs = np.minimum(1.0, p_barra + k * sigma)
    lci = np.maximum(0.0, p_barra - k * sigma)
    return _resultado("p", "p", d / n, p_barra, lcs, lci, sigma, list(reglas), incl, excluidos, limites, fase,
                      {"n_variable": bool(not np.allclose(n, n[0])), "tamanos": [float(v) for v in n]})


def calcular_np(
    defectuosos: Sequence[float],
    n: int,
    excluidos: Iterable[int] = (),
    k: float = 3.0,
    limites: dict | None = None,
    reglas: Iterable[str] = PRESETS["nelson"],
) -> dict:
    """Carta np (número de defectuosos), requiere n constante.

    LC = n·p̄;  LCS/LCI = n·p̄ ± k·√(n·p̄(1−p̄)), con LCI ≥ 0.
    """
    excluidos = list(excluidos)
    d = np.asarray(defectuosos, dtype=float)
    if np.any(d > n) or np.any(d < 0):
        raise ValueError("Cada número de defectuosos debe estar entre 0 y n.")
    incl = _mascara(d.size, excluidos)
    if limites is None:
        p_barra = float(d[incl].sum() / (n * incl.sum()))
        limites = {"tipo": "np", "k": k, "n": int(n), "p_barra": p_barra, "m_usados": int(incl.sum())}
        fase = "I"
    else:
        p_barra, k, n, fase = float(limites["p_barra"]), float(limites.get("k", k)), int(limites["n"]), "II"
    lc = n * p_barra
    sigma = math.sqrt(n * p_barra * (1 - p_barra))
    return _resultado("np", "np", d, lc, lc + k * sigma, max(0.0, lc - k * sigma), sigma, list(reglas), incl,
                      excluidos, limites, fase, {"n": int(n)})


def calcular_c(
    defectos: Sequence[float],
    excluidos: Iterable[int] = (),
    k: float = 3.0,
    limites: dict | None = None,
    reglas: Iterable[str] = PRESETS["nelson"],
) -> dict:
    """Carta c (número de defectos por unidad de inspección constante).

    c̄ = Σcᵢ/m;  LCS/LCI = c̄ ± k·√c̄, con LCI ≥ 0 (modelo de Poisson: varianza = media).
    """
    excluidos = list(excluidos)
    c = np.asarray(defectos, dtype=float)
    if np.any(c < 0):
        raise ValueError("El número de defectos no puede ser negativo.")
    incl = _mascara(c.size, excluidos)
    if limites is None:
        c_barra = float(c[incl].mean())
        limites = {"tipo": "c", "k": k, "c_barra": c_barra, "m_usados": int(incl.sum())}
        fase = "I"
    else:
        c_barra, k, fase = float(limites["c_barra"]), float(limites.get("k", k)), "II"
    sigma = math.sqrt(c_barra)
    return _resultado("c", "c", c, c_barra, c_barra + k * sigma, max(0.0, c_barra - k * sigma), sigma,
                      list(reglas), incl, excluidos, limites, fase)


def calcular_u(
    defectos: Sequence[float],
    unidades: Sequence[float] | float,
    excluidos: Iterable[int] = (),
    k: float = 3.0,
    limites: dict | None = None,
    reglas: Iterable[str] = PRESETS["nelson"],
) -> dict:
    """Carta u (defectos por unidad), con límites variables si nᵢ cambia.

    uᵢ = cᵢ/nᵢ;  ū = Σcᵢ/Σnᵢ;  LCS/LCI = ū ± k·√(ū/nᵢ), con LCI ≥ 0.
    """
    excluidos = list(excluidos)
    c = np.asarray(defectos, dtype=float)
    n = np.broadcast_to(np.asarray(unidades, dtype=float), c.shape).astype(float)
    if np.any(n <= 0):
        raise ValueError("El número de unidades inspeccionadas debe ser positivo.")
    incl = _mascara(c.size, excluidos)
    if limites is None:
        u_barra = float(c[incl].sum() / n[incl].sum())
        limites = {"tipo": "u", "k": k, "u_barra": u_barra, "m_usados": int(incl.sum())}
        fase = "I"
    else:
        u_barra, k, fase = float(limites["u_barra"]), float(limites.get("k", k)), "II"
    sigma = np.sqrt(u_barra / n)
    return _resultado("u", "u", c / n, u_barra, u_barra + k * sigma, np.maximum(0.0, u_barra - k * sigma), sigma,
                      list(reglas), incl, excluidos, limites, fase,
                      {"n_variable": bool(not np.allclose(n, n[0])), "tamanos": [float(v) for v in n]})


def calcular_carta_atributos(tipo: str, conteos, tamanos=None, **kwargs) -> dict:
    """Despacha según el tipo de carta de atributos."""
    if tipo == "p":
        return calcular_p(conteos, tamanos, **kwargs)
    if tipo == "np":
        tam = np.atleast_1d(np.asarray(tamanos, dtype=float))
        if not np.allclose(tam, tam[0]):
            raise ValueError("La carta np requiere n constante; use la carta p.")
        return calcular_np(conteos, int(tam[0]), **kwargs)
    if tipo == "c":
        return calcular_c(conteos, **kwargs)
    if tipo == "u":
        return calcular_u(conteos, 1.0 if tamanos is None else tamanos, **kwargs)
    raise ValueError(f"Tipo de carta de atributos desconocido: {tipo}")


def recomendar_grafico(tipo_dato: str, tamano_constante: bool, interes: str = "proporcion") -> dict:
    """Asistente: recomienda la carta de atributos según el tipo de dato.

    - tipo_dato = "defectuosos": cada unidad se clasifica como conforme / no conforme
      (distribución binomial) → carta p, o np si n es constante y se prefiere el conteo.
    - tipo_dato = "defectos": se cuentan las no conformidades en cada unidad o área de
      oportunidad (distribución de Poisson) → carta c si la unidad de inspección es
      constante, carta u si cambia.
    - interes = "proporcion" | "conteo" decide entre p y np cuando n es constante.
    """
    if tipo_dato == "defectuosos":
        if tamano_constante and interes == "conteo":
            carta, razon = "np", ("Cada unidad es buena o mala y siempre se revisa la misma cantidad: se grafica "
                                  "directamente cuántas unidades salieron malas.")
        else:
            carta = "p"
            razon = ("Cada unidad es buena o mala y la cantidad revisada cambia de una muestra a otra: se grafica "
                     "el porcentaje de unidades malas, que se puede comparar aunque cambie el tamaño."
                     if not tamano_constante else
                     "Cada unidad es buena o mala: se grafica el porcentaje de unidades malas, que es fácil de leer.")
        distribucion = "Binomial"
    elif tipo_dato == "defectos":
        if tamano_constante:
            carta, razon = "c", ("Se cuentan las fallas y siempre se revisa la misma cantidad de producto: se "
                                 "grafica el número de fallas por muestra.")
        else:
            carta, razon = "u", ("Se cuentan las fallas y la cantidad revisada cambia: se grafica el número de "
                                 "fallas por unidad para poder comparar las muestras.")
        distribucion = "Poisson"
    else:
        raise ValueError("tipo_dato debe ser 'defectuosos' o 'defectos'.")
    alternativas = [t for t in TIPOS if t != carta and ((t in ("p", "np")) == (tipo_dato == "defectuosos"))]
    return {"carta": carta, "distribucion": distribucion, "razon": razon, "alternativas": alternativas}
