"""Cartas de control por variables: X̄-R, X̄-S e I-MR, en Fase I y Fase II.

Fase I (estimación): los límites se estiman con los subgrupos no excluidos. El usuario
puede excluir subgrupos con causa asignable y recalcular hasta que no queden señales.

Fase II (monitoreo): se reciben los límites congelados (el diccionario `limites` que
devuelve la Fase I) y los subgrupos nuevos se evalúan contra ellos sin recalcular.

Fórmulas (Montgomery, cap. 6), con m subgrupos de tamaño n y k = ancho en sigmas (3):

    X̄-R:  X̿ = ΣX̄ᵢ/m,  R̄ = ΣRᵢ/m,  σ̂ = R̄/d2
          X̄:  LC = X̿,  LCS/LCI = X̿ ± A2·R̄              (k = 3)
          R:  LC = R̄,  LCS = D4·R̄,  LCI = D3·R̄          (k = 3)
    X̄-S:  s̄ = Σsᵢ/m,  σ̂ = s̄/c4
          X̄:  X̿ ± A3·s̄;   S: LCS = B4·s̄, LCI = B3·s̄    (k = 3)
    I-MR: MRᵢ = |xᵢ − xᵢ₋₁|,  σ̂ = MR̄/d2(2) = MR̄/1.128
          I:  x̄ ± 3·MR̄/1.128 (= x̄ ± 2.66·MR̄);  MR: LCS = D4(2)·MR̄ = 3.267·MR̄

Si k ≠ 3 se usan las expresiones generales equivalentes (p. ej. X̿ ± k·R̄/(d2√n),
R̄ ± k·d3·R̄/d2), porque los factores tabulados ya incluyen el 3.

Todas las funciones devuelven un diccionario serializable con la forma:

    {
      "tipo": "xbar_r" | "xbar_s" | "imr",
      "fase": "I" | "II",
      "n": int, "sigma_hat": float, "estimador": str,
      "cartas": {
         "<clave>": {"nombre", "valores", "lc", "lcs", "lci", "sigma", "violaciones"}
      },
      "excluidos": [...], "puntos_con_senal": [...],
      "limites": {...}     # para congelar y reutilizar en Fase II
    }
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np

from .constantes import constantes
from .reglas import PRESETS, REGLAS_DISPERSION, evaluar_reglas, puntos_con_senal

TIPOS = ("xbar_r", "xbar_s", "imr")


# ---------------------------------------------------------------------------
# Estadísticos de subgrupo
# ---------------------------------------------------------------------------

def _limpiar(valores: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(valores), dtype=float)
    return arr[~np.isnan(arr)]


def estadisticos_subgrupo(valores: Iterable[float]) -> dict:
    """Media, rango y desviación estándar muestral de un subgrupo.

    X̄ = Σxⱼ/n,  R = máx − mín,  s = √(Σ(xⱼ − X̄)²/(n − 1)).  Se ignoran los faltantes.
    """
    x = _limpiar(valores)
    n = int(x.size)
    if n == 0:
        return {"n": 0, "media": math.nan, "rango": math.nan, "s": math.nan}
    return {
        "n": n,
        "media": float(x.mean()),
        "rango": float(x.max() - x.min()),
        "s": float(x.std(ddof=1)) if n > 1 else math.nan,
    }


def estadisticos_subgrupos(subgrupos: Sequence[Iterable[float]]) -> dict[str, np.ndarray]:
    """Aplica `estadisticos_subgrupo` a cada subgrupo y devuelve arreglos n, media, rango, s."""
    filas = [estadisticos_subgrupo(s) for s in subgrupos]
    return {c: np.array([f[c] for f in filas], dtype=float) for c in ("n", "media", "rango", "s")}


def _mascara_incluidos(m: int, excluidos: Iterable[int]) -> np.ndarray:
    mascara = np.ones(m, dtype=bool)
    for i in excluidos:
        if 0 <= int(i) < m:
            mascara[int(i)] = False
    return mascara


def _serie(nombre, valores, lc, lcs, lci, sigma, reglas, incluidos) -> dict:
    """Arma la descripción de una carta y evalúa sus reglas."""
    viol = evaluar_reglas(valores, lc, lcs, lci, sigma, reglas, incluidos)

    def a_lista(v):
        arr = np.asarray(v, dtype=float)
        return float(arr) if arr.ndim == 0 else [float(a) for a in arr]

    return {
        "nombre": nombre,
        "valores": [None if math.isnan(v) else float(v) for v in np.asarray(valores, dtype=float)],
        "lc": a_lista(lc),
        "lcs": a_lista(lcs),
        "lci": a_lista(lci),
        "sigma": a_lista(sigma),
        "violaciones": viol,
    }


def _armar_resultado(tipo, fase, n, sigma_hat, estimador, cartas, excluidos, limites, extra=None) -> dict:
    senales = sorted({i for c in cartas.values() for i in puntos_con_senal(c["violaciones"])})
    res = {
        "tipo": tipo,
        "fase": fase,
        "n": n,
        "sigma_hat": float(sigma_hat),
        "estimador": estimador,
        "cartas": cartas,
        "excluidos": sorted(int(i) for i in excluidos),
        "puntos_con_senal": senales,
        "limites": limites,
    }
    if extra:
        res.update(extra)
    return res


def _n_constante(n_i: np.ndarray, tipo: str) -> int:
    validos = n_i[n_i > 0]
    if validos.size == 0:
        raise ValueError("No hay subgrupos con datos.")
    if np.any(validos != validos[0]):
        raise ValueError(f"La carta {tipo} requiere n constante; use X̄-S para n variable.")
    n = int(validos[0])
    if n < 2:
        raise ValueError("Para subgrupos de tamaño 1 use la carta I-MR.")
    return n


# ---------------------------------------------------------------------------
# X̄-R
# ---------------------------------------------------------------------------

def calcular_xbar_r(
    subgrupos: Sequence[Iterable[float]],
    excluidos: Iterable[int] = (),
    k: float = 3.0,
    limites: dict | None = None,
    reglas: Iterable[str] = PRESETS["nelson"],
) -> dict:
    """Carta X̄-R.

    Fase I (``limites=None``): X̿ y R̄ se calculan con los subgrupos no excluidos y
    LCS/LCI_X̄ = X̿ ± A2·R̄, LCS_R = D4·R̄, LCI_R = D3·R̄ (con k = 3).
    Fase II: se usan los límites recibidos tal cual.
    La σ de las zonas es σ̂/√n para X̄ y d3·σ̂ para R.
    """
    excluidos = list(excluidos)
    est = estadisticos_subgrupos(subgrupos)
    m = est["n"].size
    incl = _mascara_incluidos(m, excluidos)
    reglas = list(reglas)

    if limites is None:
        n = _n_constante(est["n"][incl], "X̄-R")
        cst = constantes(n)
        sel = incl & (est["n"] > 0)
        if sel.sum() < 2:
            raise ValueError("Se necesitan al menos 2 subgrupos incluidos para estimar límites.")
        xbb = float(est["media"][sel].mean())
        rbar = float(est["rango"][sel].mean())
        sigma = rbar / cst.d2
        if k == 3:
            lcs_x, lci_x = xbb + cst.A2 * rbar, xbb - cst.A2 * rbar
            lcs_r, lci_r = cst.D4 * rbar, cst.D3 * rbar
        else:
            lcs_x, lci_x = xbb + k * sigma / math.sqrt(n), xbb - k * sigma / math.sqrt(n)
            lcs_r, lci_r = rbar + k * cst.d3 * sigma, max(0.0, rbar - k * cst.d3 * sigma)
        limites = {
            "tipo": "xbar_r", "n": n, "k": k, "sigma_hat": sigma,
            "xbar": {"lc": xbb, "lcs": lcs_x, "lci": lci_x},
            "r": {"lc": rbar, "lcs": lcs_r, "lci": lci_r},
            "m_usados": int(sel.sum()),
        }
        fase = "I"
    else:
        n = int(limites["n"])
        cst = constantes(n)
        sigma = float(limites["sigma_hat"])
        fase = "II"

    lx, lr = limites["xbar"], limites["r"]
    cartas = {
        "xbar": _serie("X̄", est["media"], lx["lc"], lx["lcs"], lx["lci"], sigma / math.sqrt(n), reglas, incl),
        "r": _serie("R", est["rango"], lr["lc"], lr["lcs"], lr["lci"], cst.d3 * sigma,
                    [r for r in reglas if r in REGLAS_DISPERSION], incl),
    }
    return _armar_resultado("xbar_r", fase, n, sigma, "R̄/d2", cartas, excluidos, limites,
                            {"constantes": cst.a_dict()})


# ---------------------------------------------------------------------------
# X̄-S
# ---------------------------------------------------------------------------

def calcular_xbar_s(
    subgrupos: Sequence[Iterable[float]],
    excluidos: Iterable[int] = (),
    k: float = 3.0,
    limites: dict | None = None,
    reglas: Iterable[str] = PRESETS["nelson"],
) -> dict:
    """Carta X̄-S.

    n constante: s̄ = Σsᵢ/m, σ̂ = s̄/c4, LCS/LCI_X̄ = X̿ ± A3·s̄, LCS_S = B4·s̄, LCI_S = B3·s̄.

    n variable (Montgomery §6.3.2): X̿ = Σnᵢ X̄ᵢ / Σnᵢ,
    s̄ = √[Σ(nᵢ − 1)sᵢ² / (Σnᵢ − m)] y límites por subgrupo X̿ ± A3(nᵢ)·s̄,
    [B3(nᵢ)·s̄, B4(nᵢ)·s̄]. En ese caso σ̂ = s̄ (estimador combinado).
    """
    excluidos = list(excluidos)
    est = estadisticos_subgrupos(subgrupos)
    m = est["n"].size
    incl = _mascara_incluidos(m, excluidos)
    reglas = list(reglas)
    n_i = est["n"].astype(int)
    if np.any(n_i[n_i > 0] < 2):
        raise ValueError("La carta X̄-S requiere subgrupos de al menos 2 observaciones.")

    if limites is None:
        sel = incl & (n_i > 0)
        if sel.sum() < 2:
            raise ValueError("Se necesitan al menos 2 subgrupos incluidos para estimar límites.")
        constante = bool(np.all(n_i[sel] == n_i[sel][0]))
        if constante:
            n = int(n_i[sel][0])
            xbb = float(est["media"][sel].mean())
            sbar = float(est["s"][sel].mean())
            sigma = sbar / constantes(n).c4
        else:
            n = int(round(n_i[sel].mean()))
            xbb = float((n_i[sel] * est["media"][sel]).sum() / n_i[sel].sum())
            sbar = float(math.sqrt(((n_i[sel] - 1) * est["s"][sel] ** 2).sum() / (n_i[sel].sum() - sel.sum())))
            sigma = sbar
        limites = {"tipo": "xbar_s", "n": n, "k": k, "sigma_hat": sigma, "x_barra": xbb, "s_barra": sbar,
                   "n_variable": not constante, "m_usados": int(sel.sum())}
        fase = "I"
    else:
        limites = dict(limites)  # no modificar el diccionario congelado del llamador
        fase = "II"

    xbb, sbar, k = float(limites["x_barra"]), float(limites["s_barra"]), float(limites.get("k", k))
    sigma, n = float(limites["sigma_hat"]), int(limites["n"])

    # Límites por subgrupo (si n es constante todos los valores son iguales).
    n_eval = np.where(n_i > 0, n_i, n)
    A3 = np.array([constantes(int(v)).A3 for v in n_eval])
    B3 = np.array([constantes(int(v)).B3 for v in n_eval])
    B4 = np.array([constantes(int(v)).B4 for v in n_eval])
    c4 = np.array([constantes(int(v)).c4 for v in n_eval])
    if k == 3:
        lcs_x, lci_x = xbb + A3 * sbar, xbb - A3 * sbar
        lcs_s, lci_s = B4 * sbar, B3 * sbar
    else:
        sig_x = sbar / c4 / np.sqrt(n_eval)
        lcs_x, lci_x = xbb + k * sig_x, xbb - k * sig_x
        sig_s = sbar * np.sqrt(1 - c4**2) / c4
        lcs_s, lci_s = sbar + k * sig_s, np.maximum(0, sbar - k * sig_s)
    sigma_x = (sbar / c4) / np.sqrt(n_eval)
    sigma_s = (sbar / c4) * np.sqrt(1 - c4**2)

    def reducir(a):
        """Si todos los valores son iguales devuelve el escalar (límites constantes)."""
        a = np.asarray(a, dtype=float)
        return float(a[0]) if np.allclose(a, a[0]) else a

    if not limites.get("n_variable"):
        limites.setdefault("xbar", {"lc": xbb, "lcs": float(reducir(lcs_x)), "lci": float(reducir(lci_x))})
        limites.setdefault("s", {"lc": sbar, "lcs": float(reducir(lcs_s)), "lci": float(reducir(lci_s))})

    cartas = {
        "xbar": _serie("X̄", est["media"], xbb, reducir(lcs_x), reducir(lci_x), reducir(sigma_x), reglas, incl),
        "s": _serie("S", est["s"], sbar, reducir(lcs_s), reducir(lci_s), reducir(sigma_s),
                    [r for r in reglas if r in REGLAS_DISPERSION], incl),
    }
    return _armar_resultado("xbar_s", fase, n, sigma, "s̄/c4", cartas, excluidos, limites,
                            {"constantes": constantes(n).a_dict()})


# ---------------------------------------------------------------------------
# I-MR
# ---------------------------------------------------------------------------

def calcular_imr(
    valores: Sequence[float],
    excluidos: Iterable[int] = (),
    k: float = 3.0,
    limites: dict | None = None,
    reglas: Iterable[str] = PRESETS["nelson"],
) -> dict:
    """Carta de individuales y rangos móviles (I-MR), para subgrupos de tamaño 1.

    MRᵢ = |xᵢ − xᵢ₋₁| (el primer punto no tiene MR). En Fase I, MR̄ se calcula con los MRᵢ
    cuyos dos puntos están incluidos y σ̂ = MR̄/d2, con d2 = 1.128 (n = 2).
    I: LC = x̄, LCS/LCI = x̄ ± k·σ̂.   MR: LC = MR̄, LCS = D4(2)·MR̄ = 3.267·MR̄, LCI = 0.
    """
    excluidos = list(excluidos)
    x = np.asarray(valores, dtype=float)
    m = x.size
    incl = _mascara_incluidos(m, excluidos) & ~np.isnan(x)
    cst = constantes(2)
    mr = np.full(m, np.nan)
    mr[1:] = np.abs(np.diff(x))
    reglas = list(reglas)

    if limites is None:
        if incl.sum() < 3:
            raise ValueError("Se necesitan al menos 3 observaciones incluidas.")
        par_incl = np.zeros(m, dtype=bool)
        par_incl[1:] = incl[1:] & incl[:-1]
        mrbar = float(np.nanmean(mr[par_incl]))
        xbar = float(x[incl].mean())
        sigma = mrbar / cst.d2
        lcs_mr = cst.D4 * mrbar if k == 3 else mrbar + k * cst.d3 * sigma
        limites = {
            "tipo": "imr", "n": 1, "k": k, "sigma_hat": sigma,
            "i": {"lc": xbar, "lcs": xbar + k * sigma, "lci": xbar - k * sigma},
            "mr": {"lc": mrbar, "lcs": lcs_mr, "lci": 0.0},
            "m_usados": int(incl.sum()),
        }
        fase = "I"
    else:
        sigma = float(limites["sigma_hat"])
        fase = "II"

    li, lm = limites["i"], limites["mr"]
    incl_mr = incl.copy()
    incl_mr[1:] &= incl[:-1]
    incl_mr[0] = False
    cartas = {
        "i": _serie("I", x, li["lc"], li["lcs"], li["lci"], sigma, reglas, incl),
        "mr": _serie("MR", mr, lm["lc"], lm["lcs"], lm["lci"], cst.d3 * sigma,
                     [r for r in reglas if r in REGLAS_DISPERSION], incl_mr),
    }
    return _armar_resultado("imr", fase, 1, sigma, "MR̄/d2", cartas, excluidos, limites,
                            {"constantes": cst.a_dict()})


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def recomendar_carta_variables(n: int, n_constante: bool = True) -> dict:
    """Asistente: qué carta usar para una característica medida (peso, diámetro, …).

    Criterio (Montgomery §6.3–6.4):
    - n = 1 (una medición por vez: ensayos destructivos, producción lenta, lotes) → I-MR;
      σ se estima con el rango móvil MR̄/1.128.
    - 2 ≤ n ≤ 10 con n constante → X̄-R: el rango es casi tan eficiente como s para n chicos
      y más fácil de calcular en planta.
    - n > 10 o n variable → X̄-S: el rango pierde eficiencia al crecer n y s admite n variable.
    """
    n = int(n)
    if n < 1:
        raise ValueError("El tamaño de muestra debe ser al menos 1.")
    if n == 1:
        carta = "imr"
        razon = ("Se mide una sola unidad por vez, así que se grafica cada valor (I) y la diferencia "
                 "con el anterior (MR).")
    elif n <= 10 and n_constante:
        carta = "xbar_r"
        razon = (f"Se miden {n} unidades por muestra: se grafica el promedio (X̄) y el rango (R), "
                 "que con muestras chicas es simple y casi tan preciso como la desviación estándar.")
    else:
        carta = "xbar_s"
        razon = ("Las muestras son grandes o cambian de tamaño: se grafica el promedio (X̄) y la "
                 "desviación estándar (S), que aprovecha mejor la información.")
    alternativas = [t for t in TIPOS if t != carta and (t == "imr") == (n == 1)]
    return {"carta": carta, "razon": razon, "alternativas": alternativas}


def limites_con_sigma(tipo: str, centro: float, sigma: float, n: int, k: float = 3.0) -> dict:
    """Límites "con estándar dado" a partir de un σ fijado (por el ingeniero o congelado).

    Se usan cuando σ no se estima con los subgrupos de la Fase I: el ingeniero la fija por
    historial o norma de la empresa, o se cambia n en la Fase II conservando la σ congelada.
    Con centro μ (X̿ o x̄) y σ (Montgomery §6.2, tabla de límites con estándares dados):

        X̄:  LC = μ,          LCS/LCI = μ ± k·σ/√n
        R:  LC = d2·σ,       LCS = (d2 + k·d3)·σ,        LCI = máx(0, (d2 − k·d3)·σ)
        S:  LC = c4·σ,       LCS = (c4 + k·√(1−c4²))·σ,  LCI = máx(0, (c4 − k·√(1−c4²))·σ)
        I:  LC = μ,          LCS/LCI = μ ± k·σ
        MR: LC = d2(2)·σ,    LCS = (d2 + k·d3)·σ con n = 2,  LCI = 0

    Con k = 3 coinciden con los factores tabulados D1, D2 (R) y B5, B6 (S).
    Devuelve el diccionario `limites` con la misma forma que la Fase I, listo para pasarlo
    como `limites=` a la función de la carta.
    """
    if sigma is None or not sigma > 0:
        raise ValueError("σ debe ser un número positivo.")
    if tipo == "imr":
        c2 = constantes(2)
        return {
            "tipo": "imr", "n": 1, "k": k, "sigma_hat": float(sigma),
            "i": {"lc": float(centro), "lcs": centro + k * sigma, "lci": centro - k * sigma},
            "mr": {"lc": c2.d2 * sigma, "lcs": (c2.d2 + k * c2.d3) * sigma, "lci": 0.0},
        }
    n = int(n)
    if n < 2:
        raise ValueError("Las cartas X̄-R y X̄-S requieren n ≥ 2.")
    cst = constantes(n)
    x = {"lc": float(centro), "lcs": centro + k * sigma / math.sqrt(n), "lci": centro - k * sigma / math.sqrt(n)}
    if tipo == "xbar_r":
        return {
            "tipo": "xbar_r", "n": n, "k": k, "sigma_hat": float(sigma), "xbar": x,
            "r": {"lc": cst.d2 * sigma, "lcs": (cst.d2 + k * cst.d3) * sigma,
                  "lci": max(0.0, (cst.d2 - k * cst.d3) * sigma)},
        }
    if tipo == "xbar_s":
        raiz = math.sqrt(1 - cst.c4 ** 2)
        sbar = cst.c4 * sigma
        return {
            "tipo": "xbar_s", "n": n, "k": k, "sigma_hat": float(sigma), "x_barra": float(centro),
            "s_barra": sbar, "n_variable": False, "xbar": x,
            "s": {"lc": sbar, "lcs": (cst.c4 + k * raiz) * sigma, "lci": max(0.0, (cst.c4 - k * raiz) * sigma)},
        }
    raise ValueError(f"Tipo de carta desconocido: {tipo}")


def centro_de_limites(limites: dict) -> float:
    """Línea central de la carta de posición guardada en un diccionario `limites`."""
    if limites["tipo"] == "imr":
        return float(limites["i"]["lc"])
    if "xbar" in limites:
        return float(limites["xbar"]["lc"])
    return float(limites["x_barra"])


def calcular_carta(tipo: str, datos, **kwargs) -> dict:
    """Despacha al cálculo según el tipo. Para I-MR `datos` es una lista de valores
    individuales (o de subgrupos de tamaño 1, que se aplanan)."""
    if tipo == "xbar_r":
        return calcular_xbar_r(datos, **kwargs)
    if tipo == "xbar_s":
        return calcular_xbar_s(datos, **kwargs)
    if tipo == "imr":
        plano = [v[0] if isinstance(v, (list, tuple, np.ndarray)) else v for v in datos]
        return calcular_imr(plano, **kwargs)
    raise ValueError(f"Tipo de carta desconocido: {tipo}")


def carta_principal(resultado: dict) -> str:
    """Clave de la carta de posición (xbar o i) de un resultado."""
    return "i" if resultado["tipo"] == "imr" else "xbar"


def simular_exclusion(tipo: str, datos, excluidos_actuales: Iterable[int], excluidos_nuevos: Iterable[int],
                      **kwargs) -> dict:
    """Compara los límites antes y después de cambiar el conjunto de excluidos (Fase I).

    Devuelve los límites de ambas situaciones y los cambios Δ = después − antes, para
    mostrar el impacto antes de aplicar el recálculo.
    """
    antes = calcular_carta(tipo, datos, excluidos=list(excluidos_actuales), **kwargs)
    despues = calcular_carta(tipo, datos, excluidos=list(excluidos_nuevos), **kwargs)
    clave = carta_principal(antes)
    la, ld = antes["cartas"][clave], despues["cartas"][clave]

    def esc(v):
        return float(np.mean(v)) if isinstance(v, list) else float(v)

    return {
        "antes": {"lc": esc(la["lc"]), "lcs": esc(la["lcs"]), "lci": esc(la["lci"]), "sigma_hat": antes["sigma_hat"]},
        "despues": {"lc": esc(ld["lc"]), "lcs": esc(ld["lcs"]), "lci": esc(ld["lci"]), "sigma_hat": despues["sigma_hat"]},
        "delta": {
            "lc": esc(ld["lc"]) - esc(la["lc"]),
            "lcs": esc(ld["lcs"]) - esc(la["lcs"]),
            "lci": esc(ld["lci"]) - esc(la["lci"]),
            "sigma_hat": despues["sigma_hat"] - antes["sigma_hat"],
        },
        "senales_despues": despues["puntos_con_senal"],
    }
