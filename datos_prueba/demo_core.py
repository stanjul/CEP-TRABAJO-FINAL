"""Demostración en consola de la Fase 1 (lógica estadística sin interfaz).

Uso:  .venv\\Scripts\\python.exe datos_prueba\\demo_core.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8")

from app.core import (capacidad, datos, diseno_arl, graficos_atributos as ga,  # noqa: E402
                      graficos_variables as gv, muestreo_aceptacion as ma, supuestos)
from app.core.reportes import generar_conclusiones  # noqa: E402

CARPETA = Path(__file__).resolve().parent


def titulo(t: str) -> None:
    print(f"\n{'=' * 70}\n{t}\n{'=' * 70}")


def main() -> None:
    titulo("1. DATOS — proceso_simulado.csv")
    df = datos.leer_tabla(CARPETA / "proceso_simulado.csv")
    mapeo = datos.sugerir_mapeo(df)
    print("Mapeo sugerido:", mapeo)
    prep = datos.preparar_dataset(df, mapeo)
    sub = [g["valores"] for g in prep["subgrupos"]]
    d = prep["descriptivos"]
    print(f"N = {d['N']}  k = {d['k_subgrupos']}  x̄ = {d['media']:.3f}  s = {d['s']:.3f}  "
          f"R̄ = {d['r_barra']:.3f}  σ̂(R̄/d2) = {d['sigma_r_d2']:.3f}")

    titulo("2. VARIABLES — Fase I con subgrupos 1–19, Fase II con 20–25")
    base = gv.calcular_xbar_r(sub[:19])
    lx, lr = base["limites"]["xbar"], base["limites"]["r"]
    print(f"X̄: LC = {lx['lc']:.3f}  LCS = {lx['lcs']:.3f}  LCI = {lx['lci']:.3f}")
    print(f"R : LC = {lr['lc']:.3f}  LCS = {lr['lcs']:.3f}  LCI = {lr['lci']:.3f}")
    print("Señales en Fase I:", base["puntos_con_senal"] or "ninguna")
    f2 = gv.calcular_xbar_r(sub[19:], limites=base["limites"])
    f2["etiquetas"] = list(range(20, 26))  # número real de cada subgrupo de la Fase II
    for v in f2["cartas"]["xbar"]["violaciones"]:
        print(f"  Fase II · subgrupo {20 + v['indice']}: {v['regla']} — {v['descripcion']}")

    titulo("3. ATRIBUTOS — Montgomery, jugo de naranja (carta p)")
    p = ga.calcular_p([12, 15, 8, 10, 4, 7, 16, 9, 14, 10, 5, 6, 17, 12, 22, 8, 10, 5, 13, 11, 20, 18, 24, 15, 9, 12,
                       7, 13, 9, 6], 50, reglas=["N1"])
    c = p["cartas"]["p"]
    print(f"p̄ = {c['lc']:.4f}  LCS = {c['lcs']:.4f}  LCI = {c['lci']:.4f}  (libro: 0.2313 / 0.4102 / 0.0524)")
    print("Muestras fuera:", [i + 1 for i in p["puntos_con_senal"]], "(libro: 15 y 23)")

    titulo("4. SUPUESTOS — subgrupos 1–19")
    todos = [v for g in sub[:19] for v in g]
    diag = supuestos.diagnostico(todos)
    n = diag["normalidad"]["pruebas"]
    print(f"Shapiro-Wilk p = {n['shapiro_wilk']['p_valor']:.3f}  Anderson-Darling p = {n['anderson_darling']['p_valor']:.3f}")
    print(f"Ljung-Box p = {diag['independencia']['ljung_box']['p_valor']:.3f}  DW = {diag['independencia']['durbin_watson']['d']:.3f}"
          f"  Rachas p = {diag['rachas']['p_valor']:.3f}  → apto Shewhart: {diag['apto_shewhart']}")

    titulo("5. CAPACIDAD — subgrupos 1–19, especificación 495–505 g")
    cap = capacidad.analizar_capacidad(sub[:19], 495, 505, 500)
    cp = cap["indices"]
    print(f"Cp = {cp['cp']:.2f}  Cpk = {cp['cpk']:.2f}  Cpu = {cp['cpu']:.2f}  Cpl = {cp['cpl']:.2f}")
    print(f"Fracción no conforme esperada = {100 * cap['ppm_esperado']['total']:.4f} %  "
          f"({cap['ppm_esperado']['ppm']:.2f} ppm)")
    print("Veredicto:", cap["veredicto"]["texto"])

    titulo("6. DISEÑO — k = 3, n = 5, h = 0.25 h, δ = 1.5")
    dis = diseno_arl.diseno(3, 5, 0.25, 1.5)
    sim = diseno_arl.simular_arl(3, 5, 1.5, replicas=3000)
    print(f"β = {dis['beta']:.4f}  ARL0 = {dis['arl0']:.1f}  ARL1 = {dis['arl1']:.3f}  ATS1 = {dis['ats1']:.3f} h")
    print(f"Monte Carlo: ARL1 ≈ {sim['arl_simulado']:.3f}  IC95 = [{sim['ic95'][0]:.3f}, {sim['ic95'][1]:.3f}]")

    titulo("7. MUESTREO — Montgomery n = 89, c = 2, N = 10 000")
    cur = ma.curvas(89, 2, 10_000, aql=0.01, ltpd=0.06)
    print(f"Pa(0.01) = {ma.prob_aceptacion(0.01, 89, 2):.4f} (libro 0.9397)  AOQ = {ma.aoq(0.01, 89, 2, 10_000):.4f}  "
          f"ATI = {ma.ati(0.01, 89, 2, 10_000):.0f} (libro 687)  AOQL = {cur['aoql']['valor']:.4f}")
    plan = ma.disenar_plan(0.01, 0.06, 0.05, 0.10)
    print(f"Diseño exacto (AQL 1 %, LTPD 6 %, α 5 %, β 10 %): n = {plan['n']}, c = {plan['c']}")

    titulo("8. CONCLUSIONES (generadas por reglas)")
    for cnc in generar_conclusiones(carta=f2, capacidad=cap, supuestos=diag, diseno=dis, muestreo=cur):
        print(f"[{cnc['nivel'].upper():11}] {cnc['texto']}")


if __name__ == "__main__":
    main()
