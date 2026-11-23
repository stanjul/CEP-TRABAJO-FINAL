"""Informe del proceso en PDF con LaTeX (pdflatex), pensado para lectores no expertos.

El informe **solo describe** los datos: estado general en una frase, hallazgos, indicadores con
su significado, la gráfica de control, el cumplimiento de la especificación, el plan de
muestreo, las alertas y (según los módulos elegidos) lotes e historial de cambios. No incluye
recomendaciones. Usa la fuente predeterminada de LaTeX (Latin Modern).

Entrada: el mismo diccionario `contenido` que `reportes.construir_pdf` (lo arma la API), con
la clave opcional "plan" = salida de `servicios.plan_muestreo(...)["actual"]`.

    construir_pdf_latex(contenido) -> bytes   # lanza ErrorLatex si no hay LaTeX o falla
    generar_tex(contenido, carpeta) -> str    # .tex completo (y escribe las figuras PNG)
    disponible() -> dict                       # ¿hay pdflatex? ¿es MiKTeX?
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from . import figuras
from .reglas import explicar

PLANTILLAS = Path(__file__).resolve().parent / "plantillas"
TIPOS_ATRIBUTOS = ("p", "np", "c", "u")


class ErrorLatex(RuntimeError):
    """No hay LaTeX instalado o la compilación falló (el llamador usa el PDF de respaldo)."""


# ---------------------------------------------------------------------------
# Escape de texto para LaTeX
# ---------------------------------------------------------------------------

_ESPECIALES = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
               "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
_UNICODE = {
    "σ": r"$\sigma$", "δ": r"$\delta$", "Δ": r"$\Delta$", "α": r"$\alpha$", "β": r"$\beta$", "μ": r"$\mu$",
    "τ": r"$\tau$", "λ": r"$\lambda$", "≥": r"$\geq$", "≤": r"$\leq$", "±": r"$\pm$", "≈": r"$\approx$",
    "→": r"$\rightarrow$", "−": "-", "√": r"$\surd$", "·": r"\textperiodcentered{}", "…": r"\dots{}",
    "×": r"$\times$", "²": r"\textsuperscript{2}", "³": r"\textsuperscript{3}", "°": r"\textdegree{}",
    "€": r"\texteuro{}", "<": r"\textless{}", ">": r"\textgreater{}", "|": r"\textbar{}",
    **{chr(0x2080 + i): rf"\textsubscript{{{i}}}" for i in range(10)},
}
_COMBINANTES = {"̄": r"\bar", "̂": r"\hat"}  # X̄, σ̂
_SEGUROS = set("—–‘’“”«»¡¿")


def esc(texto) -> str:
    """Escapa un texto para LaTeX (caracteres especiales, letras griegas, X̄, σ̂, subíndices)."""
    if texto is None:
        return "—"
    s = str(texto)
    salida: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        siguiente = s[i + 1] if i + 1 < len(s) else ""
        if siguiente in _COMBINANTES:
            base = _UNICODE.get(ch, ch).strip("$")
            salida.append(f"${_COMBINANTES[siguiente]}{{{base}}}$")
            i += 2
            continue
        if ch in _ESPECIALES:
            salida.append(_ESPECIALES[ch])
        elif ch in _UNICODE:
            salida.append(_UNICODE[ch])
        elif ord(ch) < 0x250 or ch in _SEGUROS:
            salida.append(ch)
        elif ch in ("̄", "̂"):
            pass
        # Cualquier otro símbolo (emojis, ⚠, ✓…) se omite para no romper la compilación.
        i += 1
    return "".join(salida)


# ---------------------------------------------------------------------------
# Formato de números y fechas (coma decimal, como la interfaz)
# ---------------------------------------------------------------------------

def _num(x, d: int = 2) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{float(x):,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _pct(x, d: int = 1) -> str:
    return "—" if x is None else f"{_num(100 * float(x), d)} %"


def _pct_auto(x) -> str:
    """Porcentaje con más decimales cuando es muy chico (0,0003 %)."""
    if x is None:
        return "—"
    return _pct(x, 4 if 0 < x < 0.0001 else 3 if x < 0.001 else 2)


def _fecha(iso, con_hora: bool = True) -> str:
    if not iso:
        return "—"
    try:
        f = datetime.fromisoformat(str(iso))
    except ValueError:
        return str(iso)
    return f.strftime("%d/%m/%Y %H:%M" if con_hora else "%d/%m/%Y")


def _ultimo(v):
    return v[-1] if isinstance(v, list) else v


def _n(cantidad: int, singular: str, plural: str) -> str:
    """'1 muestra', '3 muestras'."""
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def _base_capacidad(contenido: dict) -> str:
    """Aclaración cuando el estudio de capacidad usa la Fase I porque la Fase II tiene pocas muestras."""
    cap, carta, v = contenido.get("capacidad"), contenido.get("carta"), contenido["variable"]
    if not cap or not carta or v["fase"] != "II":
        return ""
    if cap.get("k_subgrupos") != len(carta.get("subgrupos") or []):
        return (" Como la etapa de monitoreo todavía tiene menos de 20 muestras, se usaron las muestras con las que se "
                "fijaron los límites (Fase I).")
    return ""


# ---------------------------------------------------------------------------
# Contenido del informe (todo en palabras, solo descriptivo)
# ---------------------------------------------------------------------------

def _unidad_carta(v: dict) -> tuple[str, bool, int]:
    """(unidad a mostrar, es porcentaje, decimales) del estadístico graficado."""
    t = v["tipo_carta"]
    if t == "p":
        return "%", True, 1
    if t in ("np", "c"):
        return "unidades" if t == "np" else "fallas", False, 1
    if t == "u":
        return "fallas por unidad", False, 2
    return v.get("unidad") or "", False, v.get("decimales", 2) + 1


def _valor_carta(v: dict, x) -> str:
    unidad, es_pct, d = _unidad_carta(v)
    if x is None:
        return "—"
    return _pct(x, 1) if es_pct else f"{_num(x, d)} {unidad}".strip()


def _estado(contenido: dict) -> dict:
    """Estado general en una frase (color reservado para el estado del proceso)."""
    carta = contenido.get("carta")
    cap = contenido.get("capacidad")
    v = contenido["variable"]
    if not carta:
        return {"color": "neutro", "fondo": "fondoneutro", "titulo": "Todavía no hay datos suficientes",
                "texto": "Aún no se registraron muestras suficientes para describir el comportamiento del proceso."}
    if not carta.get("subgrupos"):
        congelados = (carta.get("limites_congelados") or {}).get("m_usados")
        return {"color": "neutro", "fondo": "fondoneutro", "titulo": "Todavía no hay muestras en esta etapa",
                "texto": "La etapa de monitoreo (Fase II) aún no tiene muestras. Los límites normales ya están fijados"
                         + (f" con {congelados} muestras de la Fase I." if congelados else ".")}
    senales = len(carta.get("puntos_con_senal") or [])
    fase = "Etapa de conocimiento del proceso (Fase I): los límites normales todavía pueden ajustarse." \
        if v["fase"] == "I" else "Etapa de monitoreo (Fase II): las muestras se comparan con límites fijos."
    nivel_cap = cap["veredicto"]["nivel"] if cap else None
    if senales:
        rojo = v["fase"] == "II"
        return {"color": "rojo" if rojo else "ambar", "fondo": "fondorojo" if rojo else "fondoambar",
                "titulo": "Se observaron muestras fuera de lo normal",
                "texto": f"{senales} {'muestra quedó' if senales == 1 else 'muestras quedaron'} fuera del comportamiento "
                         f"habitual del proceso. {fase}"}
    if nivel_cap == "no_capaz":
        return {"color": "rojo", "fondo": "fondorojo", "titulo": "El proceso es estable, pero no cumple lo que acepta el cliente",
                "texto": f"No hubo muestras fuera de lo normal, pero la variación del proceso es mayor que la que permite la "
                         f"especificación. {fase}"}
    if nivel_cap == "marginal":
        return {"color": "ambar", "fondo": "fondoambar", "titulo": "El proceso es estable y cumple con poco margen",
                "texto": f"No hubo muestras fuera de lo normal; el proceso cumple la especificación, pero con poco margen. {fase}"}
    extra = " y cumple con lo que acepta el cliente" if nivel_cap == "capaz" else ""
    return {"color": "verde", "fondo": "fondoverde", "titulo": f"El proceso se mantuvo estable{extra}",
            "texto": f"No hubo muestras fuera de lo normal en el período analizado. {fase}"}


def _muestras_revisar(contenido: dict) -> list[list[str]]:
    """Filas (muestra, fecha, valor, explicación) de las muestras con señal."""
    carta = contenido["carta"]
    v = contenido["variable"]
    claves = list(carta["cartas"])
    principal = carta["cartas"][claves[0]]
    textos: dict[int, list[str]] = {}
    for clave, serie in carta["cartas"].items():
        dispersion = clave in ("r", "s", "mr")
        for viol in serie["violaciones"]:
            t = ("Las unidades de la muestra son demasiado distintas entre sí: la variación aumentó."
                 if dispersion else viol.get("explicacion") or explicar(viol["regla"], viol.get("lado")))
            lista = textos.setdefault(viol["indice"], [])
            if t not in lista:
                lista.append(t)
    filas = []
    etiquetas = carta.get("etiquetas") or []
    subgrupos = carta.get("subgrupos") or []
    for i in sorted(textos):
        sg = subgrupos[i] if i < len(subgrupos) else {}
        filas.append([esc(f"#{etiquetas[i] if i < len(etiquetas) else i + 1}"), esc(_fecha(sg.get("timestamp"))),
                      esc(_valor_carta(v, principal["valores"][i])), esc(" ".join(textos[i]))])
    return filas


def _indicadores(contenido: dict) -> list[list[str]]:
    v = contenido["variable"]
    carta = contenido.get("carta")
    cap = contenido.get("capacidad")
    u = v.get("unidad") or ""
    d = v.get("decimales", 2)
    filas = []
    if carta:
        sgs = carta.get("subgrupos") or []
        unidades = sum(len(s.get("valores") or []) for s in sgs) if v["tipo_carta"] not in TIPOS_ATRIBUTOS else None
        filas.append(["Muestras analizadas", f"{len(sgs)}" + (f" ({_n(unidades, 'unidad', 'unidades')})" if unidades else ""),
                      "Fase I: período usado para conocer el proceso." if carta["fase"] == "I"
                      else "Fase II: monitoreo con límites fijos."])
        principal = carta["cartas"][next(iter(carta["cartas"]))]
        filas.append(["Promedio habitual", _valor_carta(v, _ultimo(principal["lc"])),
                      "Valor central alrededor del cual varía el proceso."])
        filas.append(["Límites normales", f"{_valor_carta(v, _ultimo(principal['lci']))} a {_valor_carta(v, _ultimo(principal['lcs']))}",
                      "Entre estos valores varía el proceso cuando no ocurre nada fuera de lo común."])
    if v["tipo_carta"] not in TIPOS_ATRIBUTOS and (v.get("lei") is not None or v.get("les") is not None):
        partes = []
        if v.get("lei") is not None:
            partes.append(f"mín. {_num(v['lei'], d)}")
        if v.get("les") is not None:
            partes.append(f"máx. {_num(v['les'], d)}")
        filas.append(["Valores aceptados", f"{' y '.join(partes)} {u}".strip(), "Lo que exige el cliente, la norma o el plano."])
    if cap:
        ob = cap["observado"]
        dentro = cap["N"] - ob["fuera"]
        filas.append(["Unidades dentro de lo aceptado", f"{_pct(dentro / cap['N'], 1)} ({dentro} de {cap['N']})",
                      "Proporción de unidades del estudio de capacidad que cumplió la especificación."])
        filas.append(["Capacidad real (Cpk)", _num(cap["indices"]["cpk"], 2),
                      "Se considera capaz de cumplir la especificación desde 1,33."])
    alarmas = contenido.get("alarmas") or []
    if alarmas:
        resueltas = sum(a["estado"] == "resuelta" for a in alarmas)
        filas.append(["Alertas registradas", f"{len(alarmas)} ({resueltas} resueltas)", "Avisos generados por muestras fuera de lo normal o reportados a mano."])
    return filas


def resumen_pantalla(contenido: dict) -> dict:
    """Estado, hallazgos e indicadores en texto plano (vista previa de la pantalla Reportes)."""
    carta = contenido.get("carta") if contenido.get("carta") and contenido["carta"].get("cartas") else None
    c = {**contenido, "carta": carta}
    return {"estado": _estado(c), "hallazgos": _hallazgos_texto(c), "indicadores": _indicadores(c)}


def _hallazgos(contenido: dict) -> list[str]:
    return [esc(h) for h in _hallazgos_texto(contenido)]


def _hallazgos_texto(contenido: dict) -> list[str]:
    """Frases descriptivas (sin recomendaciones)."""
    v = contenido["variable"]
    carta = contenido.get("carta")
    cap = contenido.get("capacidad")
    out = []
    if carta:
        sgs = carta.get("subgrupos") or []
        if sgs:
            ini, fin = _fecha(sgs[0].get("timestamp"), False), _fecha(sgs[-1].get("timestamp"), False)
            cuando = f"el {ini}" if ini == fin else f"entre el {ini} y el {fin}"
            out.append(f"Se analizaron {_n(len(sgs), 'muestra tomada', 'muestras tomadas')} {cuando}"
                       f"{' (etapa de monitoreo)' if carta['fase'] == 'II' else ''}.")
        senales = carta.get("puntos_con_senal") or []
        if not sgs:
            out.append("La etapa de monitoreo todavía no tiene muestras registradas.")
        elif senales:
            et = carta.get("etiquetas") or []
            nums = ", ".join(f"#{et[i]}" for i in senales[:8] if i < len(et)) + ("…" if len(senales) > 8 else "")
            out.append(f"{len(senales)} {'muestra quedó' if len(senales) == 1 else 'muestras quedaron'} fuera de lo normal ({nums}).")
        else:
            out.append("Ninguna muestra quedó fuera de lo normal.")
        if carta.get("excluidos"):
            k = len(carta["excluidos"])
            out.append(f"{_n(k, 'muestra fue excluida', 'muestras fueron excluidas')} del cálculo por una causa identificada.")
        if v["tipo_carta"] in ("p", "np"):
            lc = _ultimo(carta["cartas"][v["tipo_carta"]]["lc"])
            out.append(f"En promedio, el {_pct(lc / (v['n'] if v['tipo_carta'] == 'np' else 1), 1)} de las unidades revisadas fue defectuoso.")
        elif v["tipo_carta"] in ("c", "u"):
            lc = _ultimo(carta["cartas"][v["tipo_carta"]]["lc"])
            out.append(f"En promedio hubo {_num(lc, 2)} fallas {'por muestra' if v['tipo_carta'] == 'c' else 'por unidad'}.")
    if cap:
        ob = cap["observado"]
        out.append(f"En el estudio de capacidad ({_n(cap['N'], 'unidad medida', 'unidades medidas')}), el "
                   f"{_pct((cap['N'] - ob['fuera']) / cap['N'], 1)} estuvo dentro de lo aceptado "
                   f"({cap['N'] - ob['fuera']} de {cap['N']}).{_base_capacidad(contenido)}")
        out.append(f"Con el promedio y la variabilidad actuales se espera que el {_pct_auto(cap['ppm_esperado']['total'])} "
                   f"del producto quede fuera de especificación.")
        cpk = _num(cap["indices"]["cpk"], 2)
        out.append({"capaz": f"Cpk = {cpk}: el proceso es capaz de cumplir la especificación (se considera capaz desde 1,33).",
                    "marginal": f"Cpk = {cpk}: el proceso cumple la especificación con poco margen (entre 1,00 y 1,33).",
                    "no_capaz": f"Cpk = {cpk}: el proceso no es capaz de cumplir la especificación (menor que 1,00)."}
                   [cap["veredicto"]["nivel"]])
    alarmas = contenido.get("alarmas") or []
    if alarmas:
        abiertas = sum(a["estado"] != "resuelta" for a in alarmas)
        total = _n(len(alarmas), "alerta", "alertas")
        if abiertas:
            out.append(f"Se registró {total} y sigue sin resolver." if len(alarmas) == 1 else
                       f"Se registraron {total}; {abiertas} {'sigue' if abiertas == 1 else 'siguen'} sin resolver.")
        else:
            out.append(f"Se registró {total} y está resuelta." if len(alarmas) == 1 else
                       f"Se registraron {total} y todas están resueltas.")
    return out


def _seccion_carta(contenido: dict, carpeta: Path) -> dict:
    carta = contenido["carta"]
    v = contenido["variable"]
    unidad, es_pct, d = _unidad_carta(v)
    clave = next(iter(carta["cartas"]))
    attr = v["tipo_carta"] in TIPOS_ATRIBUTOS
    titulo_y = {"xbar": f"Promedio de la muestra ({unidad})", "i": f"Valor ({unidad})", "p": "% de unidades defectuosas",
                "np": "Unidades defectuosas", "c": "Fallas por muestra", "u": "Fallas por unidad"}.get(clave, unidad)
    (carpeta / "carta.png").write_bytes(figuras.carta_simple(
        carta["cartas"][clave], carta.get("etiquetas"), None if attr else v.get("lei"), None if attr else v.get("les"),
        d, unidad, es_pct, carta.get("excluidos", []), titulo_y))
    punto = {"xbar": f"el promedio de una muestra de {v['n']} unidades", "i": "el valor de una unidad",
             "p": "el porcentaje de unidades defectuosas de una muestra", "np": "la cantidad de unidades defectuosas de una muestra",
             "c": "la cantidad de fallas de una muestra", "u": "las fallas por unidad de una muestra"}.get(clave, "una muestra")
    n = len(carta.get("etiquetas") or [])
    excluidas = len(carta.get("excluidos") or [])
    return {
        "intro": esc("La gráfica muestra la única muestra del período." if n == 1 else
                     f"La gráfica muestra las {n} muestras del período, en el orden en que se tomaron."),
        "punto": esc(punto), "con_espec": not attr and (v.get("lei") is not None or v.get("les") is not None),
        "revisar": _muestras_revisar(contenido),
        "excluidas": esc(f"Las muestras marcadas con «x» ({excluidas}) se excluyeron del cálculo de los límites por una "
                         "causa identificada.") if excluidas else "",
    }


def _seccion_capacidad(contenido: dict, carpeta: Path) -> dict:
    cap = contenido["capacidad"]
    v = contenido["variable"]
    d = v.get("decimales", 2)
    (carpeta / "histograma.png").write_bytes(figuras.histograma_simple(
        cap["histograma"], cap.get("lei"), cap.get("les"), cap.get("objetivo"),
        f"{v['nombre']} ({v.get('unidad') or ''})".replace(" ()", ""), d))
    pe, ob = cap["ppm_esperado"], cap["observado"]
    tabla = []
    if cap.get("lei") is not None:
        tabla.append([f"Por debajo del mínimo ({_num(cap['lei'], d)})", _pct_auto(pe["bajo_lei"]), _num(1e6 * pe["bajo_lei"], 1),
                      f"{ob['bajo_lei']} de {cap['N']}"])
    if cap.get("les") is not None:
        tabla.append([f"Por encima del máximo ({_num(cap['les'], d)})", _pct_auto(pe["sobre_les"]), _num(1e6 * pe["sobre_les"], 1),
                      f"{ob['sobre_les']} de {cap['N']}"])
    tabla.append(["Total", _pct_auto(pe["total"]), _num(pe["ppm"], 1), f"{ob['fuera']} de {cap['N']}"])
    c = cap["indices"]
    indices = []
    if c.get("cp") is not None:
        indices.append(["Capacidad potencial (Cp)", _num(c["cp"], 2), "Qué tan holgada es la especificación frente a la variación, "
                                                                     "si el proceso estuviera centrado."])
    indices.append(["Capacidad real (Cpk)", _num(c["cpk"], 2), "Igual que Cp, pero teniendo en cuenta dónde está centrado el "
                                                               "proceso. Se considera capaz desde 1,33."])
    if c.get("cpu") is not None:
        indices.append(["Hacia el máximo (Cpu)", _num(c["cpu"], 2), "Margen entre el promedio y el valor máximo aceptado."])
    if c.get("cpl") is not None:
        indices.append(["Hacia el mínimo (Cpl)", _num(c["cpl"], 2), "Margen entre el promedio y el valor mínimo aceptado."])
    origen = "fijada por el ingeniero" if cap.get("metodo_sigma") == "fijada" else "estimada con las muestras"
    return {
        "intro": esc(f"Se compararon {_n(cap['N'], 'unidad medida', 'unidades medidas')} con los valores que acepta el cliente. "
                     f"La variabilidad usada (σ = {_num(cap['sigma_dentro'], d + 1)} {v.get('unidad') or ''}) fue {origen}."
                     f"{_base_capacidad(contenido)}"),
        "tabla": [[esc(x) for x in fila] for fila in tabla],
        "indices": [[esc(x) for x in fila] for fila in indices],
    }


def _seccion_supuestos(contenido: dict) -> dict:
    sup = contenido["supuestos"]
    n, ind, r = sup["normalidad"], sup["independencia"], sup["rachas"]
    sw = n["pruebas"]["shapiro_wilk"]
    lb = ind.get("ljung_box") or {}
    filas = [
        ["¿Los datos siguen una distribución normal (en forma de campana)?",
         "Sí, son compatibles" if not sw["rechaza_h0"] else "No",
         f"Shapiro-Wilk, p = {_num(sw['p_valor'], 3)}"],
    ]
    if lb:
        filas.append(["¿Cada valor es independiente del anterior?", "Sí" if not lb["rechaza_h0"] else "No",
                      f"Ljung-Box, p = {_num(lb['p_valor'], 3)}; Durbin-Watson d = {_num(ind['durbin_watson']['d'], 2)}"])
    filas.append(["¿Los valores se reparten al azar alrededor de la mediana?", "Sí" if r["p_valor"] >= n["alfa"] else "No",
                  f"Prueba de rachas, p = {_num(r['p_valor'], 3)}"])
    filas.append(["¿Hay una tendencia en el tiempo?", "No" if not r["tendencia"]["hay_tendencia"] else "Sí",
                  f"τ de Kendall, p = {_num(r['tendencia']['p_valor'], 3)}"])
    return {"intro": esc("Las gráficas de control y los índices de capacidad suponen ciertas condiciones de los datos. "
                         "Se verificaron con pruebas estadísticas:"),
            "filas": [[esc(x) for x in f] for f in filas]}


def _seccion_plan(contenido: dict) -> dict | None:
    plan = contenido.get("plan")
    if not plan:
        return None
    v = contenido["variable"]
    n = 1 if v["tipo_carta"] == "imr" else v["n"]
    f = v["frecuencia_min"]
    cada = f"cada {f // 60} horas" if f % 60 == 0 and f > 60 else "cada hora" if f == 60 else f"cada {f} minutos"
    textos = [t for t in (plan["textos"].get("carga"), plan["textos"].get("deteccion"), plan["textos"].get("falsa_alarma")) if t]
    return {"intro": esc(f"Se toma una muestra de {n} {'unidad' if n == 1 else 'unidades'} {cada}, con límites a "
                         f"{_num(v['k_sigma'], 1)} σ. Con este plan:"),
            "textos": [esc(t) for t in textos]}


def _alertas(contenido: dict) -> list[list[str]]:
    filas = []
    estados = {"abierta": "Sin revisar", "en_investigacion": "En revisión", "resuelta": "Resuelta"}
    for a in contenido.get("alarmas") or []:
        notas = estados.get(a["estado"], a["estado"])
        if a.get("causa"):
            notas += f". Causa: {a['causa']}"
        if a.get("accion"):
            notas += f". Acción: {a['accion']}"
        filas.append([esc(_fecha(a["creada"])), esc(f"#{a['subgrupo_numero']}" if a.get("subgrupo_numero") else "—"),
                      esc(a.get("explicacion") or a["descripcion"]), esc(notas)])
    return filas


PARAMETROS = {
    "alta": "Alta de la variable", "fase": "Etapa (Fase)", "limites": "Límites normales", "n": "Unidades por muestra",
    "frecuencia_min": "Frecuencia (minutos)", "k_sigma": "Ancho de los límites (σ)", "sigma_monitoreo": "σ fijada",
    "lei": "Mínimo aceptado", "les": "Máximo aceptado", "objetivo": "Valor ideal", "tipo_carta": "Tipo de gráfica",
    "estimador_sigma": "Cálculo de σ", "reglas": "Reglas de alerta", "nombre": "Nombre", "unidad": "Unidad",
    "decimales": "Decimales", "subgrupos archivados": "Muestras archivadas",
}


def _valor_historial(x) -> str:
    """Valores del historial legibles: los objetos (límites, configuración) no se vuelcan como JSON."""
    if x is None or x == "":
        return "—"
    s = str(x)
    if s.startswith(("{", "[")):
        return "(detalle en la aplicación)"
    return s if len(s) <= 40 else s[:37] + "…"


def _historial(contenido: dict) -> list[list[str]]:
    filas = []
    for h in contenido.get("historial") or []:
        p = h["parametro"]
        nombre = PARAMETROS.get(p) or (p.replace("anulación subgrupo", "Muestra anulada").replace("exclusion subgrupo", "Muestra excluida"))
        cambio = f"{_valor_historial(h.get('valor_anterior'))} → {_valor_historial(h.get('valor_nuevo'))}"
        filas.append([esc(_fecha(h["fecha"])), esc(h["usuario"]), esc(nombre), esc(cambio), esc(h.get("justificacion") or "—")])
    return filas


def _tecnico(contenido: dict) -> dict | None:
    carta = contenido.get("carta")
    if not carta:
        return None
    v = contenido["variable"]
    _, es_pct, d = _unidad_carta(v)
    nombres = {"xbar": "Promedios (X̄)", "r": "Rangos (R)", "s": "Desviaciones (S)", "i": "Individuales (I)",
               "mr": "Rangos móviles (MR)", "p": "Fracción defectuosa (p)", "np": "Defectuosas (np)", "c": "Fallas (c)",
               "u": "Fallas por unidad (u)"}
    fmt = (lambda x: _pct(x, 2)) if es_pct else (lambda x: _num(x, d + 1))
    filas = [[esc(nombres.get(k, k)), esc(fmt(_ultimo(s["lci"]))), esc(fmt(_ultimo(s["lc"]))), esc(fmt(_ultimo(s["lcs"])))]
             for k, s in carta["cartas"].items()]
    sigma = carta.get("sigma_hat")
    nota = (f"Límites a {_num(v.get('k_sigma', 3.0), 1)} σ. " + (f"σ = {_num(sigma, d + 2)} ({carta.get('estimador') or ''}). " if sigma else "")
            + ("Límites variables: se muestra el de la última muestra. " if isinstance(carta["cartas"][next(iter(carta['cartas']))]["lcs"], list) else ""))
    return {"limites": filas, "nota": esc(nota.strip())}


GLOSARIO = [
    ("Muestra", "Grupo de unidades que se revisa al mismo tiempo (o una sola unidad)."),
    ("Límites normales (de control)", "Rango dentro del cual varía el proceso cuando no ocurre nada fuera de lo común. "
                                      "Se calculan con los datos del propio proceso."),
    ("Valores aceptados (especificación)", "Lo que exige el cliente, la norma o el plano. No dependen del proceso."),
    ("Fase I y Fase II", "En la Fase I se conoce el proceso y se calculan los límites; en la Fase II esos límites "
                         "quedan fijos y cada muestra nueva se compara con ellos."),
    ("Cp y Cpk", "Índices de capacidad: comparan la variación del proceso con lo que permite la especificación. "
                 "Valores de 1,33 o más indican un proceso capaz."),
    ("Piezas por millón (ppm)", "Cantidad esperada de unidades fuera de especificación por cada millón producido."),
    ("Falsa alarma", "Aviso que aparece aunque el proceso esté bien; ocurre ocasionalmente por azar."),
    ("σ (sigma)", "Medida de cuánto varían los valores del proceso alrededor del promedio."),
]


def datos_plantilla(contenido: dict, carpeta: Path) -> dict:
    """Arma el diccionario que completa la plantilla (y escribe las figuras en `carpeta`)."""
    m = set(contenido.get("modulos") or [])
    v, p = contenido["variable"], contenido["proceso"]
    carta = contenido.get("carta") if contenido.get("carta") and contenido["carta"].get("cartas") else None
    contenido = {**contenido, "carta": carta}
    sgs = (carta or {}).get("subgrupos") or []
    periodo = f"{_fecha(sgs[0].get('timestamp'), False)} al {_fecha(sgs[-1].get('timestamp'), False)}" if sgs else "Sin muestras"
    titulos = {"integral": "Informe del proceso", "capacidad": "Informe de capacidad del proceso",
               "control": "Informe de control del proceso", "auditoria": "Informe de cambios y alertas"}
    estado = _estado(contenido)
    return {
        "titulo": esc(titulos.get(contenido.get("plantilla"), "Informe del proceso")),
        "proceso": esc(p["nombre"] + (f" ({p['linea']})" if p.get("linea") else "")),
        "variable": esc(f"{v['nombre']}" + (f" ({v['unidad']})" if v.get("unidad") and v["tipo_carta"] not in TIPOS_ATRIBUTOS else "")),
        "fecha": esc(contenido.get("fecha", "")), "folio": esc(contenido.get("folio", "")),
        "usuario": esc(contenido.get("usuario", "")), "periodo": esc(periodo),
        "estado": {**estado, "titulo": esc(estado["titulo"]), "texto": esc(estado["texto"])},
        "hallazgos": _hallazgos(contenido) if "resumen" in m else [],
        "indicadores": [[esc(x) for x in f] for f in _indicadores(contenido)] if "resumen" in m else [],
        "carta": _seccion_carta(contenido, carpeta) if carta and sgs and ({"cartas", "resumen"} & m) else None,
        "capacidad": _seccion_capacidad(contenido, carpeta) if contenido.get("capacidad") and "capacidad" in m else None,
        "supuestos": _seccion_supuestos(contenido) if contenido.get("supuestos") and "supuestos" in m else None,
        "plan": _seccion_plan(contenido) if "diseno" in m else None,
        "alertas": _alertas(contenido) if "alarmas" in m else None,
        "lotes": [[esc(l["codigo"]), esc(_fecha(l["fecha"], False)), esc(l["N"]), esc(l["n"]), esc(l["c"]), esc(l["defectos"]),
                   esc(str(l["dictamen"]).capitalize())]  # ACEPTADO / RECHAZADO → Aceptado / Rechazado
                  for l in (contenido.get("lotes") or [])] if "muestreo" in m else [],
        "historial": _historial(contenido) if "auditoria" in m else None,
        "tecnico": _tecnico(contenido) if carta and ({"cartas", "resumen"} & m) else None,
        "glosario": [(esc(a), esc(b)) for a, b in GLOSARIO],
    }


def _entorno() -> Environment:
    return Environment(loader=FileSystemLoader(PLANTILLAS), block_start_string="<%", block_end_string="%>",
                       variable_start_string="<<", variable_end_string=">>", comment_start_string="<#",
                       comment_end_string="#>", undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True,
                       autoescape=False)


def generar_tex(contenido: dict, carpeta: Path) -> str:
    """Devuelve el código LaTeX del informe y escribe las figuras PNG en `carpeta`."""
    return _entorno().get_template("reporte.tex").render(**datos_plantilla(contenido, Path(carpeta)))


# ---------------------------------------------------------------------------
# Compilación
# ---------------------------------------------------------------------------

def disponible() -> dict:
    """¿Hay pdflatex? (CEP_SIN_LATEX=1 lo desactiva, para pruebas del respaldo)."""
    if os.environ.get("CEP_SIN_LATEX") == "1":
        return {"pdflatex": None, "miktex": False}
    ruta = shutil.which("pdflatex")
    miktex = False
    if ruta:
        try:
            miktex = "MiKTeX" in subprocess.run([ruta, "--version"], capture_output=True, text=True, timeout=30).stdout
        except (OSError, subprocess.SubprocessError):
            ruta = None
    return {"pdflatex": ruta, "miktex": miktex}


def construir_pdf_latex(contenido: dict, timeout: int = 180) -> bytes:
    """Compila el informe con pdflatex (dos pasadas para «Página x de y») y devuelve el PDF.

    En MiKTeX se pasa --disable-installer para que, si faltara un paquete, falle en lugar de
    abrir una ventana pidiendo instalarlo (el servidor quedaría esperando).
    """
    info = disponible()
    if not info["pdflatex"]:
        raise ErrorLatex("No se encontró pdflatex (instale MiKTeX o TeX Live).")
    with tempfile.TemporaryDirectory(prefix="cep_latex_") as tmp:
        carpeta = Path(tmp)
        (carpeta / "informe.tex").write_text(generar_tex(contenido, carpeta), encoding="utf-8")
        cmd = [info["pdflatex"], "-interaction=nonstopmode", "-halt-on-error", "-file-line-error"]
        if info["miktex"]:
            cmd.append("--disable-installer")
        cmd.append("informe.tex")
        for _ in range(2):
            try:
                r = subprocess.run(cmd, cwd=carpeta, capture_output=True, timeout=timeout)
            except subprocess.TimeoutExpired as e:
                raise ErrorLatex("LaTeX tardó demasiado en compilar.") from e
            if r.returncode != 0:
                log = r.stdout.decode("utf-8", "replace")
                errores = [l for l in log.splitlines() if l.startswith("!") or ".tex:" in l][:5]
                raise ErrorLatex("Error de LaTeX: " + (" | ".join(errores) or log[-500:]))
        return (carpeta / "informe.pdf").read_bytes()
