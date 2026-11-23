"""Reglas de detección de causas especiales (Nelson / Western Electric).

Todas las reglas trabajan sobre el valor estandarizado de cada punto:

    z_i = (x_i − LC_i) / σ_i

donde σ_i es la desviación estándar del estadístico graficado (por ejemplo σ/√n en la carta
X̄, o √(p̄(1−p̄)/n_i) en la carta p). Con esto las mismas reglas sirven para cartas con
límites constantes o variables. Las zonas son:

    Zona C: |z| ≤ 1      Zona B: 1 < |z| ≤ 2      Zona A: 2 < |z| ≤ 3

Numeración (Nelson, 1984), la misma que usa la pantalla de Configuración:

    N1  1 punto fuera de los límites de control (LCS/LCI).
    N2  9 puntos consecutivos del mismo lado de la LC.
    N3  6 puntos consecutivos crecientes o decrecientes.
    N4  14 puntos consecutivos alternando arriba/abajo.
    N5  2 de 3 puntos consecutivos en zona A o más allá (mismo lado).
    N6  4 de 5 puntos consecutivos en zona B o más allá (mismo lado).
    N7  15 puntos consecutivos en zona C (estratificación, varianza muy baja).
    N8  8 puntos consecutivos fuera de la zona C (a ambos lados: mezcla).
    WE4 8 puntos consecutivos del mismo lado de la LC (variante Western Electric).

Conjunto Western Electric clásico (Western Electric Handbook, 1956): N1, N5, N6, WE4.

Convenciones de implementación:
- Los puntos excluidos (o con valor faltante) no participan: las rachas se evalúan sobre la
  subsecuencia de puntos incluidos y los índices se devuelven en la numeración original.
- Un punto exactamente sobre la LC rompe las rachas de N2/WE4; un empate (diferencia 0)
  rompe las de N3 y N4.
- En N5 y N6 el punto que completa el patrón debe ser uno de los que están en la zona, de
  modo que la señal se atribuye al subgrupo nuevo.
- Se reporta una violación por cada punto en el que el patrón se cumple. El campo
  `inicio` indica si es el primer punto de una secuencia de violaciones consecutivas de esa
  regla; la API lo usa para no generar alarmas repetidas mientras una racha continúa.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class Regla:
    """Descripción de una regla del catálogo."""

    id: str
    nombre: str
    condicion: str
    severidad: str  # "critica" | "advertencia" | "alerta"
    alfa_aprox: float  # tasa de falsa alarma aproximada por punto (referencial)
    # Explicación para personas no expertas (vista Operario). {lado} se reemplaza por
    # "por encima" / "por debajo" cuando la regla tiene un lado.
    simple: str = ""

    def a_dict(self) -> dict:
        return asdict(self)


CATALOGO: dict[str, Regla] = {
    "N1": Regla("N1", "Punto fuera de límites", "1 punto fuera de LCS/LCI (más allá de 3σ)", "critica", 0.0027,
                "Un valor quedó {lado} de los límites normales del proceso."),
    "N2": Regla("N2", "Desplazamiento", "9 puntos consecutivos del mismo lado de la LC", "advertencia", 0.0039,
                "Los últimos 9 valores quedaron todos {lado} del promedio: el proceso parece haberse corrido."),
    "N3": Regla("N3", "Tendencia", "6 puntos consecutivos crecientes o decrecientes", "advertencia", 0.0028,
                "Los últimos 6 valores {tendencia} uno tras otro: hay una tendencia."),
    "N4": Regla("N4", "Oscilación", "14 puntos consecutivos alternando arriba y abajo", "alerta", 0.0046,
                "14 valores seguidos suben y bajan alternadamente: puede haber dos máquinas, turnos u operarios mezclados."),
    "N5": Regla("N5", "Zona A", "2 de 3 puntos consecutivos más allá de 2σ (mismo lado)", "critica", 0.0030,
                "2 de los últimos 3 valores quedaron muy cerca del límite, {lado} del promedio."),
    "N6": Regla("N6", "Zona B", "4 de 5 puntos consecutivos más allá de 1σ (mismo lado)", "alerta", 0.0053,
                "4 de los últimos 5 valores quedaron alejados del promedio, {lado}."),
    "N7": Regla("N7", "Estratificación", "15 puntos consecutivos dentro de ±1σ (zona C)", "alerta", 0.0033,
                "15 valores seguidos quedaron demasiado pegados al promedio: conviene revisar cómo se está midiendo."),
    "N8": Regla("N8", "Mezcla", "8 puntos consecutivos fuera de ±1σ (a ambos lados)", "alerta", 0.0001,
                "8 valores seguidos quedaron lejos del promedio, a uno y otro lado: puede haber producto de dos fuentes mezclado."),
    "WE4": Regla("WE4", "Racha (WE)", "8 puntos consecutivos del mismo lado de la LC", "advertencia", 0.0078,
                 "Los últimos 8 valores quedaron todos {lado} del promedio: el proceso parece haberse corrido."),
}


def explicar(regla: str, lado: str | None = None) -> str:
    """Explicación en palabras simples de una violación (lado "+" arriba, "-" abajo)."""
    r = CATALOGO.get(regla)
    if r is None:
        return ""
    lado_txt = {"+": "por encima", "-": "por debajo"}.get(lado or "", "fuera")
    tendencia = {"+": "subieron", "-": "bajaron"}.get(lado or "", "subieron o bajaron")
    if regla == "N2" or regla == "WE4":
        lado_txt = {"+": "por encima", "-": "por debajo"}.get(lado or "", "del mismo lado")
    return r.simple.format(lado=lado_txt, tendencia=tendencia)

PRESETS: dict[str, list[str]] = {
    "nelson": ["N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8"],
    "western_electric": ["N1", "N5", "N6", "WE4"],
}

# Para cartas de dispersión (R, S, MR) solo tiene sentido la regla de punto fuera de límites:
# sus distribuciones son asimétricas y las zonas ±1σ/±2σ no tienen la interpretación normal.
REGLAS_DISPERSION = ["N1"]


def _como_arreglo(valor, m: int) -> np.ndarray:
    """Convierte un escalar o secuencia en un arreglo float de largo m."""
    arr = np.asarray(valor, dtype=float)
    if arr.ndim == 0:
        return np.full(m, float(arr))
    if arr.shape[0] != m:
        raise ValueError("Los límites por punto deben tener el mismo largo que los valores.")
    return arr


def _racha_mismo_signo(signos: np.ndarray, j: int, largo: int) -> int:
    """Devuelve +1/−1 si los `largo` signos que terminan en j son todos iguales y no nulos."""
    if j + 1 < largo:
        return 0
    ventana = signos[j - largo + 1 : j + 1]
    if np.all(ventana > 0):
        return 1
    if np.all(ventana < 0):
        return -1
    return 0


def evaluar_reglas(
    valores: Sequence[float],
    lc,
    lcs,
    lci,
    sigma,
    reglas: Iterable[str],
    incluidos: Sequence[bool] | None = None,
) -> list[dict]:
    """Evalúa las reglas activas sobre una serie de puntos de una carta de control.

    Parámetros
    ----------
    valores : estadístico graficado en cada punto (X̄ᵢ, Rᵢ, pᵢ, …).
    lc, lcs, lci : línea central y límites; escalar o un valor por punto.
    sigma : desviación estándar del estadístico (define las zonas); escalar o por punto.
    reglas : ids del catálogo a evaluar (p. ej. PRESETS["nelson"]).
    incluidos : máscara de puntos que participan (False = excluido de la evaluación).

    Devuelve una lista de diccionarios ``{regla, indice, puntos, lado, inicio, descripcion}``
    ordenada por índice, donde `indice` es el punto que completa el patrón y `puntos` son
    todos los puntos que lo forman.
    """
    x_all = np.asarray(valores, dtype=float)
    m_all = x_all.shape[0]
    lc_a, lcs_a, lci_a, sg_a = (_como_arreglo(v, m_all) for v in (lc, lcs, lci, sigma))

    mascara = np.ones(m_all, dtype=bool) if incluidos is None else np.asarray(incluidos, dtype=bool).copy()
    mascara &= ~np.isnan(x_all)
    idx = np.flatnonzero(mascara)  # índices originales de la subsecuencia
    if idx.size == 0:
        return []

    x = x_all[idx]
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(sg_a[idx] > 0, (x - lc_a[idx]) / sg_a[idx], 0.0)
    signos = np.sign(np.round(z, 12))
    dif = np.sign(np.round(np.diff(z), 12))  # dif[j-1] = signo(z_j − z_{j−1})
    m = x.size
    reglas = [r for r in reglas if r in CATALOGO]
    salida: list[dict] = []

    def agregar(regla: str, j: int, puntos_locales: list[int], lado: int | None) -> None:
        salida.append(
            {
                "regla": regla,
                "indice": int(idx[j]),
                "puntos": [int(idx[p]) for p in puntos_locales],
                "lado": None if not lado else ("+" if lado > 0 else "-"),
                "descripcion": CATALOGO[regla].condicion,
                "explicacion": explicar(regla, None if not lado else ("+" if lado > 0 else "-")),
            }
        )

    for regla in reglas:
        for j in range(m):
            if regla == "N1":
                if x[j] > lcs_a[idx[j]] or x[j] < lci_a[idx[j]]:
                    agregar(regla, j, [j], 1 if x[j] > lcs_a[idx[j]] else -1)
            elif regla in ("N2", "WE4"):
                largo = 9 if regla == "N2" else 8
                lado = _racha_mismo_signo(signos, j, largo)
                if lado:
                    agregar(regla, j, list(range(j - largo + 1, j + 1)), lado)
            elif regla == "N3":
                if j >= 5:
                    d = dif[j - 5 : j]
                    if np.all(d > 0) or np.all(d < 0):
                        agregar(regla, j, list(range(j - 5, j + 1)), int(d[0]))
            elif regla == "N4":
                if j >= 13:
                    d = dif[j - 13 : j]
                    if np.all(d != 0) and np.all(d[1:] * d[:-1] < 0):
                        agregar(regla, j, list(range(j - 13, j + 1)), None)
            elif regla in ("N5", "N6"):
                largo, umbral, minimo = (3, 2.0, 2) if regla == "N5" else (5, 1.0, 4)
                if j + 1 >= largo:
                    ventana = z[j - largo + 1 : j + 1]
                    for lado in (1, -1):
                        en_zona = lado * ventana > umbral
                        if lado * z[j] > umbral and en_zona.sum() >= minimo:
                            pts = [j - largo + 1 + p for p in np.flatnonzero(en_zona)]
                            agregar(regla, j, pts, lado)
            elif regla == "N7":
                if j >= 14 and np.all(np.abs(z[j - 14 : j + 1]) <= 1.0):
                    agregar(regla, j, list(range(j - 14, j + 1)), None)
            elif regla == "N8":
                if j >= 7 and np.all(np.abs(z[j - 7 : j + 1]) > 1.0):
                    agregar(regla, j, list(range(j - 7, j + 1)), None)

    # Marca de inicio: primera violación de una secuencia consecutiva (en la subsecuencia).
    posicion = {int(i): p for p, i in enumerate(idx)}
    ultimas: dict[str, int] = {}
    salida.sort(key=lambda v: (v["indice"], v["regla"]))
    for v in salida:
        p = posicion[v["indice"]]
        previo = ultimas.get(v["regla"])
        v["inicio"] = v["regla"] == "N1" or previo is None or previo != p - 1
        ultimas[v["regla"]] = p
    return salida


def puntos_con_senal(violaciones: list[dict]) -> list[int]:
    """Índices (ordenados, sin repetir) de los puntos que completan alguna violación."""
    return sorted({v["indice"] for v in violaciones})


def catalogo() -> list[dict]:
    """El catálogo como lista de diccionarios, para la interfaz."""
    return [r.a_dict() for r in CATALOGO.values()]
