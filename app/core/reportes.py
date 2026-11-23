"""Reportes: conclusiones preliminares generadas por reglas y armado de PDF / Excel.

1. `generar_conclusiones` recibe los diccionarios que producen los demás módulos del core y
   devuelve ``[{"seccion", "nivel", "texto"}]`` con nivel "ok" | "advertencia" | "critico".
   Son reglas simples y explícitas (no inferencia automática): un borrador que el ingeniero
   revisa antes de emitir el informe.

2. `construir_pdf(contenido)` y `construir_excel(contenido)` arman los archivos a partir de un
   diccionario de contenido (lo prepara la API desde la base de datos):

    {
      "folio", "plantilla", "titulo", "fecha", "usuario",
      "proceso": {...}, "variable": {...}, "modulos": ["resumen", "cartas", ...],
      "sintesis_proceso": [{variable, unidad, especificacion, tipo, fase, media, s, cpk, estado}],
      "carta": resultado del core + "etiquetas" + "subgrupos" (o None),
      "limites_congelados": {...} | None, "capacidad": {...} | None, "supuestos": {...} | None,
      "diseno": {"resumen": {...}, "curva": {...}} | None,
      "alarmas": [...], "exclusiones": [...], "historial": [...], "lotes": [...],
      "conclusiones": [...],
    }

   Las secciones se incluyen según `modulos` y según haya datos para ellas.
"""

from __future__ import annotations

import io
from pathlib import Path

from .reglas import CATALOGO

MODULOS = ("resumen", "cartas", "alarmas", "capacidad", "supuestos", "diseno", "muestreo", "auditoria")
PLANTILLAS = {
    "integral": ("Informe Integral de Control Estadístico del Proceso", list(MODULOS)),
    "capacidad": ("Estudio de Capacidad y Validación de Supuestos", ["resumen", "capacidad", "supuestos"]),
    "control": ("Resumen de Control en Proceso (Cartas Shewhart)", ["resumen", "cartas", "alarmas"]),
    "auditoria": ("Historial de Cambios y Trazabilidad", ["resumen", "alarmas", "auditoria"]),
}
NOMBRES_CARTA = {"xbar_r": "X̄-R", "xbar_s": "X̄-S", "imr": "I-MR", "p": "p", "np": "np", "c": "c", "u": "u"}


def _c(seccion: str, nivel: str, texto: str) -> dict:
    return {"seccion": seccion, "nivel": nivel, "texto": texto}


def conclusiones_carta(res: dict) -> list[dict]:
    """Estado de control a partir de un resultado de carta (variables o atributos).

    Si el resultado trae `etiquetas` (nombre o número real de cada punto, p. ej. en Fase II
    los subgrupos 20…25) se usan para citar los subgrupos; si no, se numeran desde 1.
    """
    salida = []
    etiquetas = res.get("etiquetas")
    viol = [v for c in res["cartas"].values() for v in c["violaciones"]]
    nombre = {"xbar_r": "X̄-R", "xbar_s": "X̄-S", "imr": "I-MR"}.get(res["tipo"], res["tipo"])
    if not viol:
        salida.append(_c("control", "ok", f"Carta {nombre} (Fase {res['fase']}): sin señales de causas especiales; "
                                          "el proceso se considera bajo control estadístico."))
        return salida
    por_regla: dict[str, set] = {}
    for v in viol:
        por_regla.setdefault(v["regla"], set()).add(v["indice"])

    def nombre_punto(i: int) -> str:
        return str(etiquetas[i]) if etiquetas and i < len(etiquetas) else str(i + 1)

    detalles = "; ".join(
        f"{r} ({CATALOGO[r].nombre}) en subgrupo(s) {', '.join(nombre_punto(i) for i in sorted(p)[:8])}"
        + ("…" if len(p) > 8 else "")
        for r, p in sorted(por_regla.items())
    )
    nivel = "critico" if any(CATALOGO[r].severidad == "critica" for r in por_regla) else "advertencia"
    salida.append(_c("control", nivel, f"Carta {nombre} (Fase {res['fase']}): proceso fuera de control. {detalles}."))
    if res["fase"] == "I":
        salida.append(_c("control", "advertencia",
                         "Investigue las causas asignables, excluya los subgrupos justificados y recalcule "
                         "los límites antes de congelarlos para la Fase II."))
    else:
        salida.append(_c("control", "advertencia",
                         "Registre la causa y la acción correctiva de cada alarma; si el proceso cambió de "
                         "forma permanente, vuelva a la Fase I para reestimar los límites."))
    return salida


def conclusiones_capacidad(cap: dict) -> list[dict]:
    """Interpretación de los índices de capacidad."""
    cpk = cap["indices"]["cpk"]
    v = cap["veredicto"]
    nivel = {"capaz": "ok", "marginal": "advertencia", "no_capaz": "critico"}[v["nivel"]]
    salida = [_c("capacidad", nivel, f"{v['texto']}. Fracción no conforme esperada: "
                                     f"{cap['ppm_esperado']['ppm']:.1f} ppm.")]
    cp = cap["indices"]["cp"]
    if cp is not None and cp - cpk > 0.2:
        salida.append(_c("capacidad", "advertencia",
                         f"Cp = {cp:.2f} es bastante mayor que Cpk = {cpk:.2f}: el proceso está descentrado; "
                         "centrar la media mejoraría la capacidad sin reducir la variabilidad."))
    for adv in cap.get("advertencias", []):
        salida.append(_c("capacidad", "advertencia", adv))
    return salida


def conclusiones_supuestos(diag: dict) -> list[dict]:
    """Interpretación de la validación de supuestos."""
    salida = []
    norm = diag["normalidad"]
    ad = norm["pruebas"]["anderson_darling"]
    if norm["es_normal"]:
        salida.append(_c("supuestos", "ok", f"No se rechaza la normalidad (Anderson-Darling A² = {ad['estadistico']:.3f}, "
                                            f"p = {ad['p_valor']:.3f})."))
    else:
        txt = f"Se rechaza la normalidad (Anderson-Darling p = {ad['p_valor']:.4f})."
        bc = diag.get("box_cox", {})
        if bc.get("aplicable") and bc.get("recomendar_transformar"):
            txt += f" Considere la transformación de Box-Cox con λ̂ = {bc['lambda']:.2f}."
        salida.append(_c("supuestos", "advertencia", txt + " Los índices de capacidad pueden estar sesgados."))
    ind = diag["independencia"]
    if ind["es_independiente"]:
        salida.append(_c("supuestos", "ok", f"Sin evidencia de autocorrelación (Ljung-Box p = {ind['ljung_box']['p_valor']:.3f}, "
                                            f"DW = {ind['durbin_watson']['d']:.2f})."))
    else:
        salida.append(_c("supuestos", "advertencia",
                         "Hay autocorrelación en los datos: los límites de Shewhart generarían falsas alarmas. "
                         "Considere ampliar el intervalo de muestreo o usar un modelo de series de tiempo."))
    rch = diag["rachas"]
    if not rch["es_aleatorio"]:
        salida.append(_c("supuestos", "advertencia", f"Patrón no aleatorio: {rch['patron'].lower()}"
                                                     + (" con tendencia temporal." if rch["tendencia"]["hay_tendencia"] else ".")))
    return salida


def conclusiones_arl(d: dict) -> list[dict]:
    """Interpretación del diseño de la carta X̄."""
    nivel = "ok" if d["arl1"] <= 3 else ("advertencia" if d["arl1"] <= 10 else "critico")
    return [_c("diseno", nivel,
               f"Con k = {d['k']}, n = {d['n']} y h = {d['h']} h, un corrimiento de {d['delta']}σ se detecta en "
               f"promedio en {d['arl1']:.2f} muestras (ATS = {d['ats1']:.2f} h); falsa alarma cada "
               f"{d['arl0']:.0f} muestras (ATS0 = {d['ats0']:.0f} h).")]


def conclusiones_muestreo(curv: dict) -> list[dict]:
    """Interpretación de un plan de muestreo de aceptación."""
    salida = []
    if "en_aql" in curv:
        a = curv["en_aql"]
        salida.append(_c("muestreo", "ok" if a["alfa_real"] <= 0.05 else "advertencia",
                         f"Plan n = {curv['n']}, c = {curv['c']}: lotes con p = AQL = {a['p']:.2%} se aceptan con "
                         f"probabilidad {a['pa']:.1%} (riesgo del productor α = {a['alfa_real']:.1%})."))
    if "en_ltpd" in curv:
        b = curv["en_ltpd"]
        salida.append(_c("muestreo", "ok" if b["beta_real"] <= 0.10 else "advertencia",
                         f"Lotes con p = LTPD = {b['p']:.2%} se aceptan con probabilidad {b['pa']:.1%} "
                         f"(riesgo del consumidor β = {b['beta_real']:.1%})."))
    if "aoql" in curv:
        salida.append(_c("muestreo", "ok", f"Con inspección rectificadora la calidad de salida nunca supera, en promedio, "
                                           f"AOQL = {curv['aoql']['valor']:.3%} (en p = {curv['aoql']['p']:.2%})."))
    return salida


def generar_conclusiones(carta: dict | None = None, capacidad: dict | None = None, supuestos: dict | None = None,
                         diseno: dict | None = None, muestreo: dict | None = None) -> list[dict]:
    """Une las conclusiones de todas las secciones disponibles y agrega una síntesis."""
    salida: list[dict] = []
    if carta:
        salida += conclusiones_carta(carta)
    if supuestos:
        salida += conclusiones_supuestos(supuestos)
    if capacidad:
        if carta and carta.get("puntos_con_senal"):
            capacidad = {**capacidad, "advertencias": [*capacidad.get("advertencias", []),
                         "Los índices se calcularon con un proceso que presenta señales fuera de control."]}
        salida += conclusiones_capacidad(capacidad)
    if diseno:
        salida += conclusiones_arl(diseno)
    if muestreo:
        salida += conclusiones_muestreo(muestreo)
    criticos = sum(c["nivel"] == "critico" for c in salida)
    advert = sum(c["nivel"] == "advertencia" for c in salida)
    if criticos:
        sintesis = _c("sintesis", "critico", f"Se requieren acciones: {criticos} hallazgo(s) crítico(s) y {advert} advertencia(s).")
    elif advert:
        sintesis = _c("sintesis", "advertencia", f"Proceso aceptable con observaciones: {advert} advertencia(s) a revisar.")
    else:
        sintesis = _c("sintesis", "ok", "Todos los análisis son satisfactorios.")
    return [sintesis, *salida]


# ===========================================================================
# Utilidades de formato compartidas por PDF y Excel
# ===========================================================================

def _f(x, d: int = 3) -> str:
    """Número con d decimales (coma decimal) o '—'."""
    if x is None:
        return "—"
    try:
        return f"{float(x):,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    except (TypeError, ValueError):
        return str(x)


def _pct(x, d: int = 2) -> str:
    return "—" if x is None else _f(100 * float(x), d) + " %"


def _ultimo(v):
    return v[-1] if isinstance(v, list) else v


def _filas_capacidad(cap: dict, d: int) -> list[list[str]]:
    c = cap["indices"]
    return [
        ["Índice", "Valor"],
        ["Potencial (Cp)", _f(c["cp"], 2)],
        ["Real (Cpk)", _f(c["cpk"], 2)],
        ["Lado superior (Cpu)", _f(c["cpu"], 2)],
        ["Lado inferior (Cpl)", _f(c["cpl"], 2)],
        ["σ usada" + (" (fijada por el ingeniero)" if cap.get("metodo_sigma") == "fijada" else ""), _f(cap["sigma_dentro"], d + 1)],
        ["Fracción no conforme esperada", f"{_pct(cap['ppm_esperado']['total'], 3)} ({_f(cap['ppm_esperado']['ppm'], 1)} ppm)"],
        ["Fuera de especificación observado", f"{cap['observado']['fuera']} de {cap['N']}"],
    ]


def _filas_supuestos(sup: dict) -> list[list[str]]:
    n, ind, r = sup["normalidad"], sup["independencia"], sup["rachas"]
    p = n["pruebas"]
    fila = lambda nombre, est, pv, ok: [nombre, est, _f(pv, 4), "No se rechaza" if ok else "Se rechaza"]
    return [
        ["Prueba", "Estadístico", "p-valor", f"H0 (α = {n['alfa']})"],
        fila("Shapiro-Wilk (normalidad)", f"W = {_f(p['shapiro_wilk']['estadistico'], 4)}", p["shapiro_wilk"]["p_valor"], not p["shapiro_wilk"]["rechaza_h0"]),
        fila("Anderson-Darling (normalidad)", f"A² = {_f(p['anderson_darling']['estadistico'], 3)}", p["anderson_darling"]["p_valor"], not p["anderson_darling"]["rechaza_h0"]),
        fila("Lilliefors (normalidad)", f"D = {_f(p['lilliefors']['estadistico'], 4)}", p["lilliefors"]["p_valor"], not p["lilliefors"]["rechaza_h0"]),
        fila(f"Ljung-Box k={ind['ljung_box']['rezago']} (independencia)", f"Q = {_f(ind['ljung_box']['Q'], 2)}", ind["ljung_box"]["p_valor"], not ind["ljung_box"]["rechaza_h0"]),
        ["Durbin-Watson", f"d = {_f(ind['durbin_watson']['d'], 3)}", "—", ind["durbin_watson"]["interpretacion"]],
        fila("Rachas (mediana)", f"Z = {_f(r['Z'], 2)}", r["p_valor"], r["p_valor"] >= n["alfa"]),
        fila("Tendencia (τ de Kendall)", f"τ = {_f(r['tendencia']['tau_kendall'], 3)}", r["tendencia"]["p_valor"], not r["tendencia"]["hay_tendencia"]),
    ]


def _filas_limites(carta: dict, d: int) -> list[list[str]]:
    filas = [["Carta", "LCI", "LC", "LCS", "Puntos con señal"]]
    for clave, s in carta["cartas"].items():
        filas.append([s["nombre"], _f(_ultimo(s["lci"]), d), _f(_ultimo(s["lc"]), d), _f(_ultimo(s["lcs"]), d),
                      str(len({v["indice"] for v in s["violaciones"]}))])
    return filas


def _filas_subgrupos(carta: dict, d: int) -> list[list]:
    """Tabla de subgrupos (para Excel completa; en el PDF solo los que tienen señal)."""
    claves = list(carta["cartas"])
    viol = {}
    for c in carta["cartas"].values():
        for v in c["violaciones"]:
            viol.setdefault(v["indice"], set()).add(v["regla"])
    filas = []
    for i, sg in enumerate(carta.get("subgrupos", [])):
        fila = [sg["numero"], sg["timestamp"] if isinstance(sg["timestamp"], str) else str(sg["timestamp"]), sg["fase"]]
        fila += [carta["cartas"][k]["valores"][i] for k in claves]
        fila += [", ".join(sorted(viol.get(i, []))), "Sí" if sg.get("excluido") else "", sg.get("causa_exclusion") or ""]
        filas.append(fila)
    return filas


def _secciones(contenido: dict) -> list[str]:
    m = set(contenido.get("modulos") or MODULOS)
    sec = []
    if "resumen" in m:
        sec.append("resumen")
    if "cartas" in m and contenido.get("carta") and contenido["carta"].get("cartas"):
        sec.append("cartas")
    if "alarmas" in m:
        sec.append("alarmas")
    if "capacidad" in m and contenido.get("capacidad"):
        sec.append("capacidad")
    if "supuestos" in m and contenido.get("supuestos"):
        sec.append("supuestos")
    if "diseno" in m and contenido.get("diseno"):
        sec.append("diseno")
    if "muestreo" in m and contenido.get("lotes"):
        sec.append("muestreo")
    if "auditoria" in m:
        sec.append("auditoria")
    return sec


# ===========================================================================
# PDF (reportlab)
# ===========================================================================

def _registrar_fuentes() -> tuple[str, str, str]:
    """Registra DejaVu (incluida en matplotlib) para tener σ, ≥, Δ, subíndices y acentos."""
    import matplotlib
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    ruta = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    nombres = {"CEP": "DejaVuSans.ttf", "CEP-Negrita": "DejaVuSans-Bold.ttf", "CEP-Mono": "DejaVuSansMono.ttf"}
    for nombre, archivo in nombres.items():
        if nombre not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(nombre, str(ruta / archivo)))
    return "CEP", "CEP-Negrita", "CEP-Mono"


def construir_pdf(contenido: dict) -> bytes:
    """Arma el informe PDF (A4) con encabezado, dictamen, tablas, gráficos y conclusiones."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    from . import figuras

    normal, negrita, mono = _registrar_fuentes()
    PETROLEO, TINTA, TENUE = colors.HexColor("#0f4c5c"), colors.HexColor("#0b1c30"), colors.HexColor("#70787c")
    FONDO_CAB, CEBRA = colors.HexColor("#dce9ff"), colors.HexColor("#f8f9ff")
    est = {
        "titulo": ParagraphStyle("t", fontName=negrita, fontSize=15, leading=19, textColor=TINTA),
        "h2": ParagraphStyle("h2", fontName=negrita, fontSize=11, leading=14, textColor=PETROLEO, spaceBefore=8, spaceAfter=4, keepWithNext=1),
        "p": ParagraphStyle("p", fontName=normal, fontSize=8.5, leading=11.5, textColor=TINTA, alignment=TA_LEFT),
        "chico": ParagraphStyle("c", fontName=normal, fontSize=7.5, leading=10, textColor=TENUE),
        "celda": ParagraphStyle("cel", fontName=normal, fontSize=7.5, leading=9.5, textColor=TINTA),
    }
    v, pr = contenido["variable"], contenido["proceso"]
    d = int(v.get("decimales", 2)) + 1
    ancho_util = A4[0] - 30 * mm

    def tabla(filas, anchos=None, alinear_der=()):
        datos = [[Paragraph(str(c), est["celda"]) if isinstance(c, str) and len(c) > 28 else c for c in f] for f in filas]
        t = Table(datos, colWidths=anchos, repeatRows=1)
        estilo = [("FONTNAME", (0, 0), (-1, -1), normal), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                  ("FONTNAME", (0, 0), (-1, 0), negrita), ("BACKGROUND", (0, 0), (-1, 0), FONDO_CAB),
                  ("TEXTCOLOR", (0, 0), (-1, -1), TINTA), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                  ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#c0c8cb")),
                  ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        for i in range(2, len(filas), 2):
            estilo.append(("BACKGROUND", (0, i), (-1, i), CEBRA))
        for col in alinear_der:
            estilo.append(("ALIGN", (col, 1), (col, -1), "RIGHT"))
        t.setStyle(TableStyle(estilo))
        return t

    def imagen(png: bytes, alto_mm: float):
        img = Image(io.BytesIO(png))
        escala = ancho_util / img.drawWidth
        img.drawWidth, img.drawHeight = ancho_util, img.drawHeight * escala
        if img.drawHeight > alto_mm * mm:
            f = alto_mm * mm / img.drawHeight
            img.drawWidth, img.drawHeight = img.drawWidth * f, img.drawHeight * f
        return img

    hist = []
    # ---- Encabezado
    cab = Table([[Paragraph(f"<font color='#ffffff'><b>CEP</b> · Control Estadístico de Procesos</font>", est["p"]),
                  Paragraph(f"<font color='#ffffff'>FOLIO <b>{contenido['folio']}</b></font>", est["p"])]],
                colWidths=[ancho_util * 0.62, ancho_util * 0.38])
    cab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PETROLEO), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                             ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    hist += [cab, Spacer(1, 6), Paragraph(contenido["titulo"], est["titulo"]),
             Paragraph(f"{pr.get('planta') or ''} — {pr['nombre']} · Variable: <b>{v['nombre']}</b> ({v['unidad']}) · "
                       f"Carta {NOMBRES_CARTA.get(v['tipo_carta'], v['tipo_carta'])}, n = {v['n']}, Fase {v['fase']} · "
                       f"Configuración v{v.get('version', 1)}", est["p"]),
             Paragraph(f"Emitido: {contenido['fecha']} · Elaborado por: {contenido['usuario']}", est["chico"]), Spacer(1, 6)]

    # ---- Dictamen (síntesis de las conclusiones)
    sint = next((c for c in contenido["conclusiones"] if c["seccion"] == "sintesis"), None)
    if sint:
        fondo = {"ok": "#d7f5ec", "advertencia": "#fef3c7", "critico": "#fee2e2"}[sint["nivel"]]
        tinta = {"ok": "#15803d", "advertencia": "#b45309", "critico": "#b91c1c"}[sint["nivel"]]
        rotulo = {"ok": "PROCESO CONFORME", "advertencia": "PROCESO CON OBSERVACIONES", "critico": "ACCIÓN REQUERIDA"}[sint["nivel"]]
        cpk = contenido.get("capacidad", {}) or {}
        cpk_txt = _f(cpk["indices"]["cpk"], 2) if cpk else "—"
        caja = Table([[Paragraph(f"<font color='{tinta}'><b>{rotulo}</b></font><br/>{sint['texto']}", est["p"]),
                       Paragraph(f"<font color='{tinta}' size='7'>Cpk</font><br/><font color='{tinta}' size='16'><b>{cpk_txt}</b></font>", ParagraphStyle("cpk", parent=est["p"], leading=20))]],
                     colWidths=[ancho_util * 0.8, ancho_util * 0.2])
        caja.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fondo)),
                                  ("BOX", (0, 0), (-1, -1), 1.2, colors.HexColor(tinta)), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                  ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        hist += [caja, Spacer(1, 4)]

    secciones = _secciones(contenido)
    n_sec = 0

    def h2(texto):
        nonlocal n_sec
        n_sec += 1
        return Paragraph(f"{['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'][n_sec - 1]}. {texto}", est["h2"])

    if "resumen" in secciones:
        hist.append(h2("Síntesis de variables del proceso y conclusiones"))
        filas = [["Variable", "Unidad", "Especificación", "Carta", "Fase", "Media / LC", "Desv. (s)", "Cpk", "Estado"]]
        for s in contenido.get("sintesis_proceso", []):
            filas.append([s["variable"], s["unidad"], s["especificacion"], s["tipo"], s["fase"], s["media"], s["s"], s["cpk"], s["estado"]])
        hist.append(tabla(filas, alinear_der=(5, 6, 7)))
        hist.append(Spacer(1, 4))
        marca = {"ok": "✔", "advertencia": "▲", "critico": "✖"}
        for c in contenido["conclusiones"]:
            if c["seccion"] != "sintesis":
                hist.append(Paragraph(f"{marca[c['nivel']]} <b>{c['seccion'].capitalize()}:</b> {c['texto']}", est["p"]))
        hist.append(Paragraph("Conclusiones preliminares generadas por reglas: deben ser revisadas por el responsable de calidad.", est["chico"]))

    carta = contenido.get("carta")
    if "cartas" in secciones:
        hist.append(h2(f"Cartas de control — Fase {carta['fase']}"))
        png = figuras.carta_control(carta, carta.get("etiquetas"), None if v["tipo_dato"] == "atributos" else v.get("lei"),
                                    None if v["tipo_dato"] == "atributos" else v.get("les"), d)
        hist += [imagen(png, 105), Spacer(1, 3), tabla(_filas_limites(carta, d), alinear_der=(1, 2, 3, 4))]
        lc = contenido.get("limites_congelados")
        txt = (f"Límites congelados el {str(lc['creado'])[:16].replace('T', ' ')} con {lc['m_usados']} subgrupos por {lc['usuario']}."
               if lc else "Límites provisionales estimados en la Fase I.")
        if carta.get("sigma_hat"):
            txt += f" σ̂ = {_f(carta['sigma_hat'], d + 1)} ({carta.get('estimador', '')})."
        hist.append(Paragraph(txt, est["chico"]))
        excl = contenido.get("exclusiones") or []
        if excl:
            hist.append(Paragraph("<b>Subgrupos excluidos por causa asignable</b>", est["p"]))
            hist.append(tabla([["Subgrupo", "Causa asignable", "Acción correctiva"]] +
                              [[f"#{e['numero']}", e.get("causa_exclusion") or "—", e.get("accion_exclusion") or "—"] for e in excl],
                              [20 * mm, ancho_util * 0.45, ancho_util * 0.45 - 20 * mm]))

    if "alarmas" in secciones:
        hist.append(h2("Violaciones de reglas y seguimiento de alarmas"))
        al = contenido.get("alarmas") or []
        if al:
            hist.append(tabla([["Fecha", "Subg.", "Regla", "Estado", "Causa", "Acción", "Usuario"]] +
                              [[str(a["creada"])[:16].replace("T", " "), a.get("subgrupo_numero") or "—", a["regla"], a["estado"],
                                a.get("causa") or "—", a.get("accion") or "—", a.get("usuario") or "—"] for a in al[:60]],
                              [29 * mm, 13 * mm, 13 * mm, 22 * mm, ancho_util * 0.24, ancho_util * 0.24, None]))
        else:
            hist.append(Paragraph("No se registraron alarmas en el período.", est["p"]))

    cap = contenido.get("capacidad")
    if "capacidad" in secciones:
        hist.append(h2("Capacidad del proceso"))
        hist.append(Paragraph(f"{cap['veredicto']['texto']}. N = {cap['N']} observaciones en {cap.get('k_subgrupos', '—')} subgrupos; "
                              f"LEI = {_f(cap['lei'], d - 1)}, LES = {_f(cap['les'], d - 1)}, nivel sigma ≈ {_f(cap['nivel_sigma'], 2)}σ.",
                              est["p"]))
        bloque = [tabla(_filas_capacidad(cap, d), alinear_der=(1,))]
        if cap.get("histograma"):
            bloque.append(imagen(figuras.histograma(cap["histograma"], cap["lei"], cap["les"], cap.get("objetivo"),
                                                    f"{v['nombre']} ({v['unidad']})"), 70))
        hist.append(KeepTogether(bloque))

    sup = contenido.get("supuestos")
    if "supuestos" in secciones:
        hist.append(h2("Validación de supuestos"))
        hist.append(tabla(_filas_supuestos(sup), [ancho_util * 0.38, ancho_util * 0.22, ancho_util * 0.15, ancho_util * 0.25], alinear_der=(2,)))
        hist.append(imagen(figuras.qq_y_acf(sup["qq"], sup["independencia"]["acf"]), 68))
        bc = sup.get("box_cox") or {}
        if bc.get("aplicable"):
            hist.append(Paragraph(f"Box-Cox: λ̂ = {_f(bc['lambda'], 2)}, IC 95 % [{_f(bc['ic'][0], 2)}, {_f(bc['ic'][1], 2)}] — "
                                  f"{'se recomienda transformar' if bc['recomendar_transformar'] else 'no se recomienda transformar'}.", est["chico"]))

    dis = contenido.get("diseno")
    if "diseno" in secciones:
        r = dis["resumen"]
        hist.append(h2("Diseño de la carta: ARL y ATS"))
        hist.append(tabla([["k", "n", "h (horas)", "δ (σ)", "α", "β", "ARL₀", "ARL₁", "ATS₁ (h)"],
                           [_f(r["k"], 2), str(r["n"]), _f(r["h"], 3), _f(r["delta"], 2), _f(r["alfa"], 4), _f(r["beta"], 4),
                            _f(r["arl0"], 1), _f(r["arl1"], 3), _f(r["ats1"], 3)]], alinear_der=tuple(range(9))))
        cur = dis["curva"]
        series = [{"nombre": f"n = {k}", "x": cur["deltas"], "y": s["arl"]} for k, s in cur["series"].items()]
        hist.append(imagen(figuras.curvas(series, "Corrimiento δ (σ)", "ARL₁ (log)", log_y=True, referencias=[r["delta"]]), 62))

    if "muestreo" in secciones:
        hist.append(h2("Muestreo de aceptación — lotes inspeccionados"))
        hist.append(tabla([["Lote", "Fecha", "N", "n", "c", "d", "p̂", "Dictamen"]] +
                          [[l["codigo"], str(l["fecha"])[:16].replace("T", " "), str(l["N"]), str(l["n"]), str(l["c"]),
                            str(l["defectos"]), _pct(l["p_hat"]), l["dictamen"]] for l in contenido["lotes"][:40]], alinear_der=(2, 3, 4, 5, 6)))

    if "auditoria" in secciones:
        hist.append(h2("Historial de cambios (trazabilidad)"))
        hc = contenido.get("historial") or []
        hist.append(tabla([["Fecha", "Usuario", "Parámetro", "Anterior", "Nuevo", "Justificación", "Versión"]] +
                          [[str(h["fecha"])[:16].replace("T", " "), h["usuario"], h["parametro"], (h["valor_anterior"] or "—")[:40],
                            (h["valor_nuevo"] or "—")[:40], h["justificacion"] or "—", f"v{h['version']} #{h['hash'][:7]}"] for h in hc[:60]],
                          [22 * mm, 22 * mm, 24 * mm, 26 * mm, 26 * mm, None, 20 * mm]))

    # ---- Firmas (sin firma digital: espacio para firma manuscrita)
    firmas = Table([["", ""], [Paragraph(f"Elaborado por: {contenido['usuario']}", est["chico"]),
                               Paragraph("Revisado / aprobado por:", est["chico"])]], colWidths=[ancho_util / 2] * 2, rowHeights=[18 * mm, None])
    firmas.setStyle(TableStyle([("LINEBELOW", (0, 0), (0, 0), 0.6, TENUE), ("LINEBELOW", (1, 0), (1, 0), 0.6, TENUE),
                                ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12)]))
    hist += [Spacer(1, 10), KeepTogether([Paragraph("Validación", est["h2"]), firmas])]

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont(normal, 7)
        canvas.setFillColor(TENUE)
        canvas.drawString(15 * mm, 10 * mm, f"{contenido['folio']} · {pr['nombre']} · {v['nombre']}")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=16 * mm,
                            title=contenido["titulo"], author=contenido["usuario"], subject=f"CEP — {v['nombre']}")
    doc.build(hist, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()


# ===========================================================================
# Excel (openpyxl)
# ===========================================================================

def construir_excel(contenido: dict) -> bytes:
    """Libro Excel con una hoja por sección (tablas con datos numéricos reales) y los gráficos."""
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImagen
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    from . import figuras

    v, pr = contenido["variable"], contenido["proceso"]
    d = int(v.get("decimales", 2)) + 1
    cab_fill = PatternFill("solid", fgColor="DCE9FF")
    titulo_font = Font(bold=True, size=14, color="0B1C30")
    negrita = Font(bold=True)
    wb = Workbook()

    def hoja(nombre, filas, titulo=None, anchos=None):
        ws = wb.create_sheet(nombre) if wb.active.title != "Sheet" else wb.active
        if ws.title == "Sheet":
            ws.title = nombre
        fila0 = 1
        if titulo:
            ws.cell(1, 1, titulo).font = titulo_font
            fila0 = 3
        for i, f in enumerate(filas):
            for j, val in enumerate(f):
                c = ws.cell(fila0 + i, j + 1, val)
                if i == 0:
                    c.font, c.fill = negrita, cab_fill
                if isinstance(val, float):
                    c.number_format = "0." + "0" * min(6, d + 1)
        for j in range(max((len(f) for f in filas), default=0)):
            letra = get_column_letter(j + 1)
            ws.column_dimensions[letra].width = (anchos[j] if anchos and j < len(anchos) else
                                                 min(60, max(10, max(len(str(f[j])) if j < len(f) else 0 for f in filas) + 2)))
        if filas:
            ws.freeze_panes = ws.cell(fila0 + 1, 1)
        return ws

    # Resumen
    filas = [["Campo", "Valor"], ["Folio", contenido["folio"]], ["Informe", contenido["titulo"]], ["Fecha", contenido["fecha"]],
             ["Elaborado por", contenido["usuario"]], ["Proceso", pr["nombre"]], ["Planta / línea", f"{pr.get('planta') or ''} {pr.get('linea') or ''}"],
             ["Variable", f"{v['nombre']} ({v['unidad']})"], ["Carta", NOMBRES_CARTA.get(v["tipo_carta"], v["tipo_carta"])],
             ["n", v["n"]], ["Fase", v["fase"]], ["LEI", v.get("lei")], ["Objetivo", v.get("objetivo")], ["LES", v.get("les")],
             ["Reglas activas", ", ".join(v.get("reglas", []))], ["Versión de configuración", v.get("version")]]
    ws = hoja("Resumen", filas, contenido["titulo"], [28, 80])
    fila = len(filas) + 5
    ws.cell(fila, 1, "Conclusiones preliminares (generadas por reglas)").font = negrita
    for i, c in enumerate(contenido["conclusiones"], start=1):
        ws.cell(fila + i, 1, c["nivel"].upper())
        celda = ws.cell(fila + i, 2, c["texto"])
        celda.alignment = Alignment(wrap_text=True, vertical="top")

    if contenido.get("sintesis_proceso"):
        hoja("Sintesis proceso", [["Variable", "Unidad", "Especificación", "Carta", "Fase", "Media / LC", "Desv. (s)", "Cpk", "Estado"]] +
             [[s["variable"], s["unidad"], s["especificacion"], s["tipo"], s["fase"], s["media"], s["s"], s["cpk"], s["estado"]]
              for s in contenido["sintesis_proceso"]])

    secciones = _secciones(contenido)
    carta = contenido.get("carta")
    imagenes: list[tuple[str, bytes]] = []
    if "cartas" in secciones:
        claves = list(carta["cartas"])
        hoja("Subgrupos", [["Subgrupo", "Fecha", "Fase", *[carta["cartas"][k]["nombre"] for k in claves], "Reglas violadas", "Excluido", "Causa"]]
             + _filas_subgrupos(carta, d))
        lim = _filas_limites(carta, d)
        ws = hoja("Limites", lim)
        if carta.get("constantes"):
            ws.cell(len(lim) + 3, 1, "Constantes (Montgomery, Ap. VI)").font = negrita
            for i, (k, val) in enumerate(carta["constantes"].items()):
                ws.cell(len(lim) + 4 + i, 1, k)
                ws.cell(len(lim) + 4 + i, 2, val)
        imagenes.append(("Carta de control", figuras.carta_control(carta, carta.get("etiquetas"),
                                                                   None if v["tipo_dato"] == "atributos" else v.get("lei"),
                                                                   None if v["tipo_dato"] == "atributos" else v.get("les"), d)))
    if "alarmas" in secciones:
        hoja("Alarmas", [["Fecha", "Subgrupo", "Regla", "Carta", "Severidad", "Estado", "Descripción", "Causa", "Acción", "Usuario"]] +
             [[str(a["creada"]), a.get("subgrupo_numero"), a["regla"], a.get("carta"), a["severidad"], a["estado"], a["descripcion"],
               a.get("causa"), a.get("accion"), a.get("usuario")] for a in contenido.get("alarmas") or []])
    cap = contenido.get("capacidad")
    if "capacidad" in secciones:
        c = cap["indices"]
        hoja("Capacidad", [["Índice", "Valor"],
                           ["Cp", c["cp"]], ["Cpk", c["cpk"]], ["Cpu", c["cpu"]], ["Cpl", c["cpl"]],
                           ["σ usada", cap["sigma_dentro"]], ["Método de σ", cap.get("metodo_sigma")],
                           ["Fracción no conforme esperada", cap["ppm_esperado"]["total"]],
                           ["ppm esperado", cap["ppm_esperado"]["ppm"]],
                           ["Fuera de especificación observados", cap["observado"]["fuera"]],
                           ["N", cap["N"]], ["Media", cap["media"]],
                           ["Desviación estándar de los datos (s)", cap["desviacion_estandar"]],
                           ["Veredicto", cap["veredicto"]["texto"]]])
        if cap.get("histograma"):
            imagenes.append(("Histograma de capacidad", figuras.histograma(cap["histograma"], cap["lei"], cap["les"], cap.get("objetivo"),
                                                                           f"{v['nombre']} ({v['unidad']})")))
    sup = contenido.get("supuestos")
    if "supuestos" in secciones:
        ws = hoja("Supuestos", _filas_supuestos(sup))
        base = len(_filas_supuestos(sup)) + 3
        ws.cell(base, 1, "ACF").font = negrita
        ws.cell(base + 1, 1, "Rezago k").font = negrita
        ws.cell(base + 1, 2, "r_k").font = negrita
        for i, (k, r) in enumerate(zip(sup["independencia"]["acf"]["rezagos"], sup["independencia"]["acf"]["r"])):
            ws.cell(base + 2 + i, 1, k)
            ws.cell(base + 2 + i, 2, r)
        imagenes.append(("Q-Q y ACF", figuras.qq_y_acf(sup["qq"], sup["independencia"]["acf"])))
    dis = contenido.get("diseno")
    if "diseno" in secciones:
        cur = dis["curva"]
        claves = list(cur["series"])
        hoja("Diseno ARL", [["δ (σ)", *[f"ARL n={k}" for k in claves], *[f"ATS n={k} (h)" for k in claves]]] +
             [[dl, *[cur["series"][k]["arl"][i] for k in claves], *[cur["series"][k]["ats"][i] for k in claves]]
              for i, dl in enumerate(cur["deltas"])])
    if "muestreo" in secciones:
        hoja("Lotes", [["Lote", "Fecha", "N", "n", "c", "d", "p estimado", "Dictamen", "Usuario"]] +
             [[l["codigo"], str(l["fecha"]), l["N"], l["n"], l["c"], l["defectos"], l["p_hat"], l["dictamen"], l.get("usuario")]
              for l in contenido["lotes"]])
    if "auditoria" in secciones:
        hoja("Historial", [["Fecha", "Usuario", "Parámetro", "Valor anterior", "Valor nuevo", "Justificación", "Versión", "SHA-256"]] +
             [[str(h["fecha"]), h["usuario"], h["parametro"], h["valor_anterior"], h["valor_nuevo"], h["justificacion"], h["version"], h["hash"]]
              for h in contenido.get("historial") or []])

    if imagenes:
        ws = wb.create_sheet("Graficos")
        fila = 1
        for titulo, png in imagenes:
            ws.cell(fila, 1, titulo).font = negrita
            img = XLImagen(io.BytesIO(png))
            img.width, img.height = img.width * 0.55, img.height * 0.55
            ws.add_image(img, f"A{fila + 1}")
            fila += int(img.height / 20) + 4

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
