"""Validación de supuestos: normalidad, independencia y patrones/rachas.

Las cartas de Shewhart y los índices de capacidad suponen observaciones normales e
independientes. Este módulo reúne las pruebas que muestra la pantalla de Supuestos.

Normalidad (H0: los datos provienen de una normal):
- Shapiro-Wilk: W = (Σ aᵢ x₍ᵢ₎)² / Σ(xᵢ − x̄)².  W cercano a 1 ⇒ normalidad.
- Anderson-Darling: A² = −N − (1/N)·Σ(2i−1)[ln Φ(z₍ᵢ₎) + ln(1 − Φ(z₍N+1−i₎))],
  con zᵢ = (xᵢ − x̄)/s. El p-valor usa la corrección A²* = A²(1 + 0.75/N + 2.25/N²)
  (Stephens / D'Agostino), implementada en statsmodels.
- Kolmogorov-Smirnov con corrección de Lilliefors (μ y σ estimados).
- Asimetría g1 y curtosis en exceso g2, con errores estándar ≈ √(6/N) y √(24/N).
- Q-Q normal: cuantiles teóricos Φ⁻¹((i − 0.375)/(N + 0.25)) (Blom) frente a los datos
  ordenados, con bandas puntuales del 95 % basadas en la distribución Beta de los
  estadísticos de orden.

Independencia:
- ACF: r_k = Σ(x_t − x̄)(x_{t+k} − x̄) / Σ(x_t − x̄)², con bandas ±1.96/√N.
- Ljung-Box: Q = N(N+2)·Σ_{k=1}^{h} r_k²/(N − k) ~ χ²(h) bajo H0 (ruido blanco).
- Durbin-Watson: d = Σ(e_t − e_{t−1})² / Σe_t², con e_t = x_t − x̄. d ≈ 2(1 − r₁);
  se interpreta con la regla práctica 1.5 ≤ d ≤ 2.5 ⇒ sin autocorrelación de orden 1.

Patrones / rachas:
- Prueba de rachas de Wald-Wolfowitz respecto de la mediana:
  E[R] = 2n₁n₂/(n₁+n₂) + 1,  Var[R] = 2n₁n₂(2n₁n₂ − n₁ − n₂)/[(n₁+n₂)²(n₁+n₂−1)],
  Z = (R − E[R])/√Var[R].  Pocas rachas ⇒ agrupamiento/tendencia; muchas ⇒ oscilación.
- Tendencia: τ de Kendall entre el orden temporal y los valores (prueba de Mann-Kendall).
- Racha más larga por encima / por debajo de la mediana.

Transformación:
- Box-Cox: y(λ) = (x^λ − 1)/λ (λ ≠ 0), ln x (λ = 0). λ̂ maximiza la log-verosimilitud;
  si el IC del 95 % de λ contiene 1, no se recomienda transformar.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox, lilliefors, normal_ad
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tsa.stattools import acf


def _datos(valores: Sequence[float]) -> np.ndarray:
    x = np.asarray(valores, dtype=float)
    x = x[~np.isnan(x)]
    if x.size < 8:
        raise ValueError("Se necesitan al menos 8 observaciones para validar supuestos.")
    return x


# ---------------------------------------------------------------------------
# Normalidad
# ---------------------------------------------------------------------------

def normalidad(valores: Sequence[float], alfa: float = 0.05) -> dict:
    """Batería de pruebas de normalidad (Shapiro-Wilk, Anderson-Darling, Lilliefors)
    más asimetría y curtosis. Devuelve estadísticos, p-valores y la conclusión."""
    x = _datos(valores)
    N = x.size
    sw = stats.shapiro(x)
    ad_stat, ad_p = normal_ad(x)
    ks_stat, ks_p = lilliefors(x, dist="norm", pvalmethod="table")
    g1 = float(stats.skew(x, bias=False))
    g2 = float(stats.kurtosis(x, fisher=True, bias=False))

    pruebas = {
        "shapiro_wilk": {"estadistico": float(sw.statistic), "p_valor": float(sw.pvalue)},
        "anderson_darling": {"estadistico": float(ad_stat), "p_valor": float(ad_p)},
        "lilliefors": {"estadistico": float(ks_stat), "p_valor": float(ks_p)},
    }
    for p in pruebas.values():
        p["rechaza_h0"] = p["p_valor"] < alfa
    rechazos = sum(p["rechaza_h0"] for p in pruebas.values())
    return {
        "N": int(N),
        "alfa": alfa,
        "pruebas": pruebas,
        "forma": {
            "asimetria": g1,
            "ee_asimetria": math.sqrt(6 / N),
            "curtosis_exceso": g2,
            "ee_curtosis": math.sqrt(24 / N),
        },
        # Se toma Anderson-Darling como prueba principal (es la que reporta la pantalla de Capacidad).
        "es_normal": not pruebas["anderson_darling"]["rechaza_h0"],
        "pruebas_que_rechazan": rechazos,
    }


def qq_normal(valores: Sequence[float], confianza: float = 0.95) -> dict:
    """Datos para el gráfico Q-Q normal con recta de referencia y bandas de confianza.

    Posiciones de Blom: pᵢ = (i − 0.375)/(N + 0.25), zᵢ = Φ⁻¹(pᵢ).
    La recta de referencia es x = x̄ + s·z. Las bandas usan que U₍ᵢ₎ ~ Beta(i, N − i + 1):
    límites x̄ + s·Φ⁻¹(Beta⁻¹(α/2)) y x̄ + s·Φ⁻¹(Beta⁻¹(1 − α/2)).
    """
    x = np.sort(_datos(valores))
    N = x.size
    i = np.arange(1, N + 1)
    z = stats.norm.ppf((i - 0.375) / (N + 0.25))
    media, s = float(x.mean()), float(x.std(ddof=1))
    a = (1 - confianza) / 2
    inf = media + s * stats.norm.ppf(stats.beta.ppf(a, i, N - i + 1))
    sup = media + s * stats.norm.ppf(stats.beta.ppf(1 - a, i, N - i + 1))
    r = float(np.corrcoef(z, x)[0, 1])
    dentro = float(np.mean((x >= inf) & (x <= sup)))
    return {
        "teoricos": z.tolist(),
        "ordenados": x.tolist(),
        "recta": {"intercepto": media, "pendiente": s},
        "banda_inf": inf.tolist(),
        "banda_sup": sup.tolist(),
        "r_qq": r,
        "fraccion_dentro_bandas": dentro,
    }


def histograma(valores: Sequence[float], bins: int | str = "auto", puntos_curva: int = 120) -> dict:
    """Histograma de frecuencias más la curva normal N(x̄, s) escalada a frecuencias:
    f(x) = N·ancho·φ((x − x̄)/s)/s."""
    x = np.asarray(valores, dtype=float)
    x = x[~np.isnan(x)]
    if x.size < 2:
        raise ValueError("Se necesitan al menos 2 observaciones para el histograma.")
    cuentas, bordes = np.histogram(x, bins=bins)
    media, s = float(x.mean()), float(x.std(ddof=1))
    ancho = float(bordes[1] - bordes[0])
    xs = np.linspace(min(bordes[0], media - 4 * s), max(bordes[-1], media + 4 * s), puntos_curva)
    curva = x.size * ancho * stats.norm.pdf(xs, media, s)
    return {
        "bordes": bordes.tolist(),
        "cuentas": cuentas.tolist(),
        "media": media,
        "s": s,
        "curva_x": xs.tolist(),
        "curva_y": curva.tolist(),
    }


# ---------------------------------------------------------------------------
# Independencia
# ---------------------------------------------------------------------------

def independencia(valores: Sequence[float], rezagos: int = 20, alfa: float = 0.05) -> dict:
    """ACF con bandas ±z/√N, prueba de Ljung-Box y estadístico de Durbin-Watson."""
    x = _datos(valores)
    N = x.size
    h = int(min(rezagos, N // 2 - 1))
    r = acf(x, nlags=h, fft=False)
    banda = float(stats.norm.ppf(1 - alfa / 2) / math.sqrt(N))
    lb = acorr_ljungbox(x, lags=list(range(1, h + 1)), return_df=True)
    h_lb = int(min(10, h))  # rezago de resumen habitual: mín(10, N/5)
    q, p_lb = float(lb["lb_stat"].iloc[h_lb - 1]), float(lb["lb_pvalue"].iloc[h_lb - 1])
    d = float(durbin_watson(x - x.mean()))
    if d < 1.5:
        dw_txt = "Autocorrelación positiva"
    elif d > 2.5:
        dw_txt = "Autocorrelación negativa"
    else:
        dw_txt = "Sin autocorrelación de orden 1"
    fuera = [k for k in range(1, h + 1) if abs(r[k]) > banda]
    return {
        "N": int(N),
        "acf": {"rezagos": list(range(1, h + 1)), "r": [float(v) for v in r[1:]], "banda": banda,
                "rezagos_fuera": fuera},
        "ljung_box": {"rezago": h_lb, "Q": q, "p_valor": p_lb, "rechaza_h0": p_lb < alfa,
                      "por_rezago": [{"k": int(k), "Q": float(a), "p": float(b)}
                                     for k, a, b in zip(range(1, h + 1), lb["lb_stat"], lb["lb_pvalue"])]},
        "durbin_watson": {"d": d, "interpretacion": dw_txt, "independiente": 1.5 <= d <= 2.5},
        "es_independiente": (p_lb >= alfa) and (1.5 <= d <= 2.5),
    }


def rachas(valores: Sequence[float], alfa: float = 0.05) -> dict:
    """Prueba de rachas respecto de la mediana, tendencia (Kendall) y racha más larga.

    Los valores iguales a la mediana se descartan (convención habitual)."""
    x = _datos(valores)
    mediana = float(np.median(x))
    signos = np.sign(x - mediana)
    signos = signos[signos != 0]
    n1, n2 = int((signos > 0).sum()), int((signos < 0).sum())
    R = int(1 + np.count_nonzero(signos[1:] != signos[:-1]))
    n = n1 + n2
    esperado = 2 * n1 * n2 / n + 1
    var = 2 * n1 * n2 * (2 * n1 * n2 - n) / (n**2 * (n - 1))
    Z = (R - esperado) / math.sqrt(var) if var > 0 else 0.0
    p = float(2 * stats.norm.sf(abs(Z)))

    # Racha más larga de cada lado.
    mayor = {1: 0, -1: 0}
    actual, previo = 0, 0
    for s in signos:
        actual = actual + 1 if s == previo else 1
        previo = s
        mayor[int(s)] = max(mayor[int(s)], actual)

    tau = stats.kendalltau(np.arange(x.size), x)
    if p < alfa:
        patron = "Agrupamiento / tendencia (pocas rachas)" if R < esperado else "Oscilación (demasiadas rachas)"
    else:
        patron = "Aleatorio"
    return {
        "mediana": mediana,
        "n_sobre": n1,
        "n_bajo": n2,
        "rachas_observadas": R,
        "rachas_esperadas": float(esperado),
        "Z": float(Z),
        "p_valor": p,
        "racha_max_sobre": mayor[1],
        "racha_max_bajo": mayor[-1],
        "tendencia": {"tau_kendall": float(tau.statistic), "p_valor": float(tau.pvalue),
                      "hay_tendencia": float(tau.pvalue) < alfa},
        "patron": patron,
        "es_aleatorio": p >= alfa and float(tau.pvalue) >= alfa,
    }


# ---------------------------------------------------------------------------
# Box-Cox y diagnóstico global
# ---------------------------------------------------------------------------

LAMBDA_MIN, LAMBDA_MAX = -5.0, 5.0


def box_cox(valores: Sequence[float], confianza: float = 0.95) -> dict:
    """Estimación de λ de Box-Cox por máxima verosimilitud con su IC (perfil de verosimilitud).

    ℓ(λ) = −(N/2)·ln σ̂²(λ) + (λ − 1)·Σ ln xᵢ;  IC = {λ : ℓ(λ) ≥ ℓ(λ̂) − ½·χ²₁(1−α)}.
    La búsqueda se acota a λ ∈ [−5, 5]: con datos lejos de 0 y poca dispersión relativa
    (p. ej. pesos de 500 g con σ = 1 g) la verosimilitud es casi plana y λ no está bien
    identificado; en ese caso el IC llega a los bordes y contiene a 1, por lo que no se
    recomienda transformar. Requiere datos estrictamente positivos.
    """
    from scipy.optimize import minimize_scalar

    x = _datos(valores)
    if np.any(x <= 0):
        return {"aplicable": False, "motivo": "Box-Cox requiere datos positivos."}
    llf = lambda lam: float(stats.boxcox_llf(lam, x))
    opt = minimize_scalar(lambda lam: -llf(lam), bounds=(LAMBDA_MIN, LAMBDA_MAX), method="bounded")
    lam = float(opt.x)
    umbral = llf(lam) - 0.5 * stats.chi2.ppf(confianza, 1)
    grilla = np.linspace(LAMBDA_MIN, LAMBDA_MAX, 1001)
    dentro = grilla[np.array([llf(g) for g in grilla]) >= umbral]
    lo, hi = (float(dentro.min()), float(dentro.max())) if dentro.size else (lam, lam)
    acotado = lo <= LAMBDA_MIN + 1e-9 or hi >= LAMBDA_MAX - 1e-9
    return {
        "aplicable": True,
        "lambda": lam,
        "ic": [lo, hi],
        "ic_en_borde": acotado,
        "recomendar_transformar": not (lo <= 1 <= hi),
    }


def transformar_box_cox(valores: Sequence[float], lam: float) -> list[float]:
    """Aplica y = (x^λ − 1)/λ, o ln x si λ = 0."""
    x = np.asarray(valores, dtype=float)
    return (np.log(x) if abs(lam) < 1e-12 else (x**lam - 1) / lam).tolist()


def diagnostico(valores: Sequence[float], alfa: float = 0.05, rezagos: int = 20) -> dict:
    """Ejecuta todas las validaciones y emite un veredicto global para la pantalla."""
    norm = normalidad(valores, alfa)
    ind = independencia(valores, rezagos, alfa)
    rch = rachas(valores, alfa)
    apto = norm["es_normal"] and ind["es_independiente"] and rch["es_aleatorio"]
    problemas = []
    if not norm["es_normal"]:
        problemas.append("no normalidad")
    if not ind["es_independiente"]:
        problemas.append("autocorrelación")
    if not rch["es_aleatorio"]:
        problemas.append("patrón no aleatorio")
    return {
        "normalidad": norm,
        "qq": qq_normal(valores),
        "histograma": histograma(valores),
        "independencia": ind,
        "rachas": rch,
        "box_cox": box_cox(valores),
        "apto_shewhart": apto,
        "problemas": problemas,
    }
