"""Diseño de la carta X̄: ARL0, ARL1 y ATS (Montgomery, §6.2.6).

Carta X̄ con límites μ0 ± k·σ/√n, muestras cada h horas y un corrimiento de la media
μ1 = μ0 + δ·σ (δ en unidades de σ del proceso):

    α   = P(señal | en control)       = 2·Φ(−k)
    β   = P(no señal | corrimiento δ)  = Φ(k − δ√n) − Φ(−k − δ√n)
    ARL0 = 1/α                        (longitud media de corrida en control)
    ARL1 = 1/(1 − β)                  (longitud media hasta detectar el corrimiento)
    ATS  = ARL·h                      (tiempo medio hasta la señal)

La longitud de corrida es geométrica con probabilidad de señal p por muestra, por lo que
ARL = 1/p y DE(RL) = √(1 − p)/p.

La simulación de Monte Carlo genera medias X̄ ~ N(μ0 + δσ, σ/√n), cuenta cuántas muestras
pasan hasta el primer punto fuera de límites y promedia sobre las réplicas.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from scipy import stats


def alfa(k: float = 3.0) -> float:
    """Probabilidad de falsa alarma por muestra: α = 2Φ(−k)."""
    return float(2 * stats.norm.cdf(-k))


def beta(k: float, n: int, delta: float) -> float:
    """Riesgo β de no detectar un corrimiento δσ en la muestra siguiente:
    β = Φ(k − δ√n) − Φ(−k − δ√n)."""
    r = delta * math.sqrt(n)
    return float(stats.norm.cdf(k - r) - stats.norm.cdf(-k - r))


def arl0(k: float = 3.0) -> float:
    """ARL en control: 1/α."""
    return 1.0 / alfa(k)


def arl1(k: float, n: int, delta: float) -> float:
    """ARL fuera de control: 1/(1 − β). Con δ = 0 coincide con ARL0."""
    return 1.0 / (1.0 - beta(k, n, delta))


def ats(arl: float, h: float) -> float:
    """Tiempo medio hasta la señal: ATS = ARL·h."""
    return arl * h


def diseno(k: float, n: int, h: float, delta: float) -> dict:
    """Resumen del diseño (k, n, h) frente a un corrimiento δ."""
    b = beta(k, n, delta)
    a0, a1 = arl0(k), arl1(k, n, delta)
    p1 = 1 - b
    return {
        "k": k, "n": n, "h": h, "delta": delta,
        "alfa": alfa(k),
        "beta": b,
        "potencia": p1,
        "arl0": a0,
        "arl1": a1,
        "de_rl1": math.sqrt(1 - p1) / p1,
        "ats0": ats(a0, h),
        "ats1": ats(a1, h),
        "muestras_por_hora": n / h,
    }


TIPOS_ATRIBUTOS = ("p", "np", "c", "u")
_EPS = 1e-9  # tolerancia para que un conteo justo sobre el límite no cuente como señal


def limites_atributos(tipo: str, centro: float, n: float, k: float = 3.0) -> dict:
    """Límites de las cartas de atributos expresados en la escala del conteo X.

    p:  LC = p₀,  LCS/LCI = p₀ ± k·√(p₀(1−p₀)/n);  en conteo: X ≤ n·LCS, X ≥ n·LCI
    np: LC = n·p₀, LCS/LCI = n·p₀ ± k·√(n·p₀(1−p₀))
    c:  LC = c₀,  LCS/LCI = c₀ ± k·√c₀
    u:  LC = u₀,  LCS/LCI = u₀ ± k·√(u₀/n);   en conteo (n unidades): X ≤ n·LCS
    LCI se recorta en 0 y, en p, LCS se recorta en 1.
    Devuelve {lc, lcs, lci} en la escala de la carta y {x_max, x_min} en la escala del conteo.
    """
    if tipo in ("p", "np"):
        if not 0 < centro < 1:
            raise ValueError("La fracción defectuosa debe estar entre 0 y 1.")
        sig = math.sqrt(centro * (1 - centro) / n)
        lcs, lci = min(1.0, centro + k * sig), max(0.0, centro - k * sig)
        escala = n
        if tipo == "np":
            return {"lc": n * centro, "lcs": n * lcs, "lci": n * lci, "x_max": n * lcs, "x_min": n * lci}
    elif tipo in ("c", "u"):
        if not centro > 0:
            raise ValueError("El promedio de defectos debe ser positivo.")
        base = 1.0 if tipo == "c" else n
        sig = math.sqrt(centro / base)
        lcs, lci = centro + k * sig, max(0.0, centro - k * sig)
        escala = base
    else:
        raise ValueError(f"Tipo de carta de atributos desconocido: {tipo}")
    return {"lc": centro, "lcs": lcs, "lci": lci, "x_max": escala * lcs, "x_min": escala * lci}


def prob_senal_atributos(tipo: str, lim: dict, centro_real: float, n: float) -> float:
    """Probabilidad de que una muestra caiga fuera de los límites cuando el proceso opera en
    `centro_real` (p real, o defectos promedio reales).

    p / np: X ~ Binomial(n, p);  c: X ~ Poisson(c);  u: X ~ Poisson(n·u).
    P(señal) = 1 − P(x_min ≤ X ≤ x_max) = 1 − [F(⌊x_max⌋) − F(⌈x_min⌉ − 1)].
    """
    sup = math.floor(lim["x_max"] + _EPS)
    inf = math.ceil(lim["x_min"] - _EPS) - 1
    if tipo in ("p", "np"):
        dist = stats.binom(int(round(n)), min(max(centro_real, 0.0), 1.0))
    else:
        dist = stats.poisson(centro_real * (1.0 if tipo == "c" else n))
    dentro = float(dist.cdf(sup)) - (float(dist.cdf(inf)) if inf >= 0 else 0.0)
    return min(1.0, max(0.0, 1.0 - dentro))


def diseno_atributos(tipo: str, centro: float, centro_1: float, n: float, k: float, h: float) -> dict:
    """Diseño de una carta de atributos (Montgomery §7, curva OC de las cartas p y c).

    α = P(señal | centro),  β = 1 − P(señal | centro_1),
    ARL0 = 1/α, ARL1 = 1/(1 − β), ATS = ARL·h. A diferencia de la carta X̄, α no es 0.0027:
    depende de n y del centro porque la distribución es discreta y asimétrica.
    Si una probabilidad de señal es 0 (p. ej. LCI = 0 y LCS ≥ n) el ARL es infinito.
    """
    if tipo not in TIPOS_ATRIBUTOS:
        raise ValueError(f"Tipo de carta de atributos desconocido: {tipo}")
    lim = limites_atributos(tipo, centro, n, k)
    a = prob_senal_atributos(tipo, lim, centro, n)
    p1 = prob_senal_atributos(tipo, lim, centro_1, n)
    a0 = 1.0 / a if a > 0 else math.inf
    a1 = 1.0 / p1 if p1 > 0 else math.inf
    unidades = 1.0 if tipo == "c" else float(n)
    return {
        "tipo": tipo, "k": k, "n": n, "h": h, "centro": centro, "centro_1": centro_1,
        "limites": {kk: lim[kk] for kk in ("lc", "lcs", "lci")},
        "alfa": a, "beta": 1.0 - p1, "potencia": p1,
        "arl0": a0, "arl1": a1,
        "de_rl1": math.sqrt(1 - p1) / p1 if p1 > 0 else math.inf,
        "ats0": ats(a0, h), "ats1": ats(a1, h),
        "muestras_por_hora": unidades / h,
    }


def carga_muestral(n: float, frecuencia_min: float, horas_turno: float = 8.0) -> dict:
    """Unidades a inspeccionar con un plan de n unidades cada `frecuencia_min` minutos.

    Muestras por hora = 60/f;  unidades por hora = n·60/f;  por turno = unidades/hora · horas del turno.
    """
    por_hora = 60.0 / frecuencia_min
    return {
        "muestras_por_hora": por_hora,
        "unidades_por_hora": n * por_hora,
        "muestras_por_turno": por_hora * horas_turno,
        "unidades_por_turno": n * por_hora * horas_turno,
        "horas_turno": horas_turno,
    }


def _num(x: float, d: int = 1) -> str:
    """Número con coma decimal y punto de miles (formato de la interfaz)."""
    t = f"{x:,.{d}f}"
    return t.replace(",", "§").replace(".", ",").replace("§", ".")


def duracion_legible(horas: float, horas_turno: float = 8.0) -> str:
    """Convierte horas de producción en un texto legible (minutos, horas o turnos)."""
    if horas is None or math.isinf(horas):
        return "nunca (en la práctica)"
    if horas < 1:
        return f"{_num(horas * 60, 0)} minutos"
    if horas < 2 * horas_turno:
        return f"{_num(horas, 1)} horas"
    return f"{_num(horas, 0)} horas (unos {_num(horas / horas_turno, 0)} turnos de {_num(horas_turno, 0)} h)"


def textos_plan(d: dict, carga: dict, unidad: str = "", sigma: float | None = None,
                es_porcentaje: bool = False) -> dict:
    """Explicación del plan en lenguaje simple (para operarios, supervisores y reportes).

    Usa ARL0/ATS0 (falsas alarmas), ARL1/ATS1 (detección del cambio) y la carga muestral.
    `d` es la salida de `diseno` (carta X̄/I) o de `diseno_atributos`.
    """
    ht = carga.get("horas_turno", 8.0)
    falsa = (f"Aunque el proceso esté bien, la carta dará en promedio una falsa alarma cada "
             f"{_num(d['arl0'], 0)} muestras, es decir, cada {duracion_legible(d['ats0'], ht)} de producción."
             if not math.isinf(d["arl0"]) else
             "Con este plan la carta prácticamente nunca da falsas alarmas.")
    if "centro_1" in d:  # atributos
        f = (lambda x: f"{_num(100 * x, 2)} %") if es_porcentaje else (lambda x: _num(x, 2))
        cambio = f"Si el nivel de defectos pasa de {f(d['centro'])} a {f(d['centro_1'])}"
    else:
        en_unidades = f" (≈ {' '.join(filter(None, [_num(d['delta'] * sigma, 3), unidad]))})" if sigma else ""
        cambio = f"Si el promedio del proceso se corre {_num(d['delta'], 1)} σ{en_unidades}"
    deteccion = (f"{cambio}, la carta lo detecta en promedio en {_num(d['arl1'], 1)} muestras, unas "
                 f"{duracion_legible(d['ats1'], ht)}."
                 if not math.isinf(d["arl1"]) else f"{cambio}, la carta no lo detectaría con este plan.")
    return {"falsa_alarma": falsa, "deteccion": deteccion, "carga": texto_carga(carga)}


def _cantidad(x: float, singular: str, plural: str) -> str:
    """'1 muestra', '2 muestras', '2,5 muestras' (sin decimales si el número es entero)."""
    entero = abs(x - round(x)) < 1e-9
    texto = _num(x, 0 if entero else 1)
    return f"{texto} {singular if entero and round(x) == 1 else plural}"


def texto_carga(carga: dict) -> str:
    """Carga muestral en palabras: muestras y unidades por hora y por turno."""
    m = carga["muestras_por_hora"]
    verbo = "Se toma" if abs(m - 1) < 1e-9 else "Se toman"
    return (f"{verbo} {_cantidad(m, 'muestra', 'muestras')} por hora: "
            f"{_cantidad(carga['unidades_por_hora'], 'unidad', 'unidades')} por hora, "
            f"{_num(carga['unidades_por_turno'], 0)} por turno de {_num(carga.get('horas_turno', 8.0), 0)} h.")


def curva_arl(k: float, n: int, deltas: Sequence[float] | None = None, h: float = 1.0,
              tamanos_comparar: Sequence[int] = ()) -> dict:
    """ARL1 y ATS1 en función de δ para el n elegido (y otros n para comparar)."""
    if deltas is None:
        deltas = np.round(np.linspace(0, 3, 31), 3)
    series = {}
    for nn in [n, *[t for t in tamanos_comparar if t != n]]:
        arls = [arl1(k, nn, float(d)) for d in deltas]
        series[str(nn)] = {"arl": arls, "ats": [a * h for a in arls]}
    return {"deltas": [float(d) for d in deltas], "series": series, "k": k, "h": h}


def simular_arl(k: float, n: int, delta: float, replicas: int = 2000, semilla: int | None = 12345,
                max_muestras: int = 200_000) -> dict:
    """Estimación de ARL por Monte Carlo.

    Para cada réplica se simulan medias estandarizadas Z = (X̄ − μ0)/(σ/√n) ~ N(δ√n, 1)
    hasta que |Z| > k. Devuelve ARL estimado, DE de las longitudes, IC 95 % de la media y
    el valor teórico para comparar.
    """
    rng = np.random.default_rng(semilla)
    corrimiento = delta * math.sqrt(n)
    largos = np.zeros(replicas, dtype=np.int64)
    pendientes = np.arange(replicas)
    bloque = max(64, int(min(4 * arl1(k, n, delta), 4096)))
    contador = 0
    while pendientes.size and contador < max_muestras:
        z = rng.normal(corrimiento, 1.0, size=(pendientes.size, bloque))
        senal = np.abs(z) > k
        hay = senal.any(axis=1)
        primera = senal.argmax(axis=1)
        largos[pendientes[hay]] = contador + primera[hay] + 1
        pendientes = pendientes[~hay]
        contador += bloque
    largos[pendientes] = max_muestras  # truncadas (muy improbable con los valores usuales)
    media = float(largos.mean())
    de = float(largos.std(ddof=1))
    ee = de / math.sqrt(replicas)
    teorico = arl1(k, n, delta)
    return {
        "replicas": replicas,
        "semilla": semilla,
        "arl_simulado": media,
        "de_rl": de,
        "ic95": [media - 1.96 * ee, media + 1.96 * ee],
        "arl_teorico": teorico,
        "error_relativo": (media - teorico) / teorico,
        "truncadas": int(pendientes.size),
        "histograma": np.bincount(np.minimum(largos, 50)).tolist(),
    }
