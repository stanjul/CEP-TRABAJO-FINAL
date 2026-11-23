"""Genera los archivos de ejemplo de datos_prueba/.

Uso (desde la raíz del proyecto):
    .venv\\Scripts\\python.exe datos_prueba\\generar_datos.py

Archivos generados:
- proceso_simulado.csv / .xlsx   25 subgrupos × n = 5 (formato largo), peso neto en g.
                                 μ0 = 500 g, σ = 1 g; desde el subgrupo 20 la media se corre
                                 +1.5σ (μ1 = 501.5 g). Especificación 495–505 g.
- proceso_simulado_ancho.csv     mismos datos en formato ancho (M1…M5).
- proceso_con_faltantes.csv      versión con 3 faltantes y 2 atípicos para probar la limpieza.
- montgomery_anillos.csv         anillos de pistón (X̄-R / X̄-S), formato ancho.
- montgomery_prestamos.csv       costos de préstamos (I-MR).
- montgomery_jugo_p.csv          latas de jugo (carta p / np).
- montgomery_circuitos_c.csv     circuitos impresos (carta c).
- montgomery_computadoras_u.csv  computadoras (carta u).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.core.graficos_variables import calcular_xbar_r  # noqa: E402
from app import ejemplos_montgomery as dm  # noqa: E402

DESTINO = Path(__file__).resolve().parent
MU0, SIGMA, N, K, INICIO_CORRIMIENTO, DELTA = 500.0, 1.0, 5, 25, 20, 1.5
SEMILLA = 2024


def simular(semilla: int) -> np.ndarray:
    """Subgrupos ~ N(μ, σ) con μ = μ0 hasta el subgrupo 19 y μ0 + δσ desde el 20."""
    rng = np.random.default_rng(semilla)
    medias = np.where(np.arange(1, K + 1) >= INICIO_CORRIMIENTO, MU0 + DELTA * SIGMA, MU0)
    return np.round(rng.normal(medias[:, None], SIGMA, size=(K, N)), 2)


def proceso_simulado() -> pd.DataFrame:
    datos = simular(SEMILLA)
    # Verificación: los subgrupos 1–19 (base de Fase I) no deben dar señales con sus propios límites,
    # y el corrimiento debe detectarse contra esos límites a partir del subgrupo 20.
    base = calcular_xbar_r(datos[: INICIO_CORRIMIENTO - 1].tolist())
    assert base["puntos_con_senal"] == [], "la semilla produce señales en la base"
    fase2 = calcular_xbar_r(datos[INICIO_CORRIMIENTO - 1:].tolist(), limites=base["limites"])
    assert fase2["puntos_con_senal"], "el corrimiento no se detecta"

    inicio = datetime(2026, 11, 20, 6, 0)
    operarios = ["OP-104", "OP-088", "OP-219"]
    filas = []
    for i, sub in enumerate(datos, start=1):
        t = inicio + timedelta(minutes=15 * (i - 1))
        for j, v in enumerate(sub, start=1):
            filas.append({
                "timestamp": (t + timedelta(seconds=15 * (j - 1))).isoformat(timespec="seconds"),
                "subgrupo": i,
                "muestra": j,
                "peso_neto_g": float(v),
                "operario": operarios[(i - 1) // 9],
                "lote": "ENV-2026-001" if i < INICIO_CORRIMIENTO else "ENV-2026-002",
            })
    return pd.DataFrame(filas)


def main() -> None:
    largo = proceso_simulado()
    largo.to_csv(DESTINO / "proceso_simulado.csv", index=False)
    largo.to_excel(DESTINO / "proceso_simulado.xlsx", index=False, sheet_name="Mediciones")

    ancho = largo.pivot(index="subgrupo", columns="muestra", values="peso_neto_g")
    ancho.columns = [f"M{c}" for c in ancho.columns]
    ancho.insert(0, "Fecha", largo.groupby("subgrupo")["timestamp"].first())
    ancho.reset_index().rename(columns={"subgrupo": "Subgrupo"}).to_csv(DESTINO / "proceso_simulado_ancho.csv", index=False)

    sucio = largo.copy()
    sucio["peso_neto_g"] = sucio["peso_neto_g"].astype(object)
    for fila in (7, 33, 61):
        sucio.loc[fila, "peso_neto_g"] = None
    sucio.loc[12, "peso_neto_g"] = 512.4  # atípico (error de digitación)
    sucio.loc[48, "peso_neto_g"] = 450.0  # atípico (balanza sin tara)
    sucio.to_csv(DESTINO / "proceso_con_faltantes.csv", index=False)

    an = pd.DataFrame(dm.ANILLOS, columns=[f"M{i}" for i in range(1, 6)])
    an.insert(0, "Subgrupo", range(1, len(an) + 1))
    an.to_csv(DESTINO / "montgomery_anillos.csv", index=False)
    pd.DataFrame({"semana": range(1, 21), "costo": dm.PRESTAMOS}).to_csv(DESTINO / "montgomery_prestamos.csv", index=False)
    pd.DataFrame({"muestra": range(1, 31), "defectuosos": dm.JUGO_DEFECTUOSOS, "tamano": dm.JUGO_N}).to_csv(
        DESTINO / "montgomery_jugo_p.csv", index=False)
    pd.DataFrame({"muestra": range(1, 27), "defectos": dm.CIRCUITOS}).to_csv(
        DESTINO / "montgomery_circuitos_c.csv", index=False)
    pd.DataFrame({"muestra": range(1, 21), "defectos": dm.COMPUTADORAS, "unidades": dm.COMPUTADORAS_N}).to_csv(
        DESTINO / "montgomery_computadoras_u.csv", index=False)
    print("Archivos generados en", DESTINO)


if __name__ == "__main__":
    main()
