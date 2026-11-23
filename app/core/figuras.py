"""Figuras estáticas (PNG) para los reportes PDF y Excel, con matplotlib sin interfaz.

Usa la misma paleta que la interfaz (DESIGN.md de Stitch): LC petróleo, LCS/LCI rojo,
especificaciones gris punteado, puntos con señal en rojo. Cada función devuelve los bytes PNG.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # sin ventanas: se dibuja en memoria
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401  (formateadores con coma decimal)
import numpy as np  # noqa: E402

C = {"dato": "#003441", "lc": "#0f4c5c", "control": "#ba1a1a", "espec": "#70787c", "grilla": "#e5eeff",
     "barra": "#5f8f9b", "curva": "#ba1a1a", "ok": "#086a5f"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#6250d6"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": "#c0c8cb", "axes.labelcolor": "#40484b",
    "xtick.color": "#40484b", "ytick.color": "#40484b", "axes.grid": True, "grid.color": C["grilla"],
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
})


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _escalar(v, m):
    a = np.asarray(v, dtype=float)
    return np.full(m, float(a)) if a.ndim == 0 else a


def _panel_carta(ax, serie: dict, etiquetas, excluidos=(), lei=None, les=None, decimales=3, titulo=""):
    """Dibuja una carta de control en un eje (límites constantes o escalonados)."""
    y = np.array([np.nan if v is None else v for v in serie["valores"]], dtype=float)
    m = y.size
    x = np.arange(m)
    for clave, color, ancho, estilo, nombre in (("lcs", C["control"], 1.4, "-", "LCS"), ("lc", C["lc"], 1.4, "-", "LC"),
                                                ("lci", C["control"], 1.4, "-", "LCI")):
        val = _escalar(serie[clave], m) if m else np.array([serie[clave]] * 2, dtype=float)
        xs = x if m else np.array([0, 1])
        ax.step(xs, val, where="mid", color=color, lw=ancho, ls=estilo)
        ax.annotate(f"{nombre} {val[-1]:.{decimales}f}", (1.0, val[-1]), xycoords=("axes fraction", "data"),
                    xytext=(4, 0), textcoords="offset points", va="center", fontsize=7, color=color)
    for valor, nombre in ((les, "LES"), (lei, "LEI")):
        if valor is not None:
            ax.axhline(valor, color=C["espec"], lw=1, ls="--")
            ax.annotate(f"{nombre} {valor:.{decimales}f}", (1.0, valor), xycoords=("axes fraction", "data"),
                        xytext=(4, 0), textcoords="offset points", va="center", fontsize=7, color=C["espec"])
    if m:
        excl = set(excluidos)
        senal = {v["indice"] for v in serie["violaciones"]}
        incl = [i for i in range(m) if i not in excl]
        ax.plot(incl, y[incl], color=C["dato"], lw=1.2, zorder=2)
        normales = [i for i in incl if i not in senal]
        ax.scatter(normales, y[normales], s=16, facecolor="white", edgecolor=C["dato"], lw=1.2, zorder=3)
        malos = [i for i in incl if i in senal]
        ax.scatter(malos, y[malos], s=30, facecolor="#ffdad6", edgecolor=C["control"], lw=1.5, zorder=4)
        if excl:
            ex = sorted(excl)
            ax.scatter(ex, y[ex], s=24, marker="x", color=C["espec"], zorder=4)
        paso = max(1, m // 12)
        ax.set_xticks(x[::paso])
        ax.set_xticklabels([str(e) for e in list(etiquetas)[::paso]])
    ax.set_title(titulo, loc="left", fontsize=9, color="#0b1c30", fontweight="bold")


def carta_control(resultado: dict, etiquetas=None, lei=None, les=None, decimales=3) -> bytes:
    """Carta de control completa (1 o 2 paneles: posición y dispersión) del resultado del core."""
    claves = list(resultado["cartas"])
    etiquetas = etiquetas or list(range(1, len(resultado["cartas"][claves[0]]["valores"]) + 1))
    filas = len(claves)
    fig, ejes = plt.subplots(filas, 1, figsize=(7.2, 2.6 if filas == 1 else 4.4), sharex=True,
                             gridspec_kw={"height_ratios": [3, 2][:filas]})
    ejes = np.atleast_1d(ejes)
    nombres = {"xbar": "Carta X̄ (medias)", "i": "Carta I (individuales)", "r": "Carta R (rangos)",
               "s": "Carta S (desviaciones)", "mr": "Carta MR (rangos móviles)", "p": "Carta p (fracción defectuosa)",
               "np": "Carta np", "c": "Carta c (defectos)", "u": "Carta u (defectos por unidad)"}
    for k, (clave, ax) in enumerate(zip(claves, ejes)):
        _panel_carta(ax, resultado["cartas"][clave], etiquetas, resultado.get("excluidos", []),
                     lei if k == 0 else None, les if k == 0 else None, decimales, nombres.get(clave, clave))
    ejes[-1].set_xlabel("Subgrupo")
    fig.subplots_adjust(right=0.86)
    return _png(fig)


def _coma(x: float, d: int) -> str:
    """Número con coma decimal (como en la interfaz)."""
    return f"{x:.{d}f}".replace(".", ",")


def carta_simple(serie: dict, etiquetas, lei=None, les=None, decimales=3, unidad="", porcentaje=False,
                 excluidos=(), titulo_y="") -> bytes:
    """Carta de control para lectores no expertos (reporte LaTeX): un solo panel, rótulos en
    palabras ("Límite superior", "Promedio", "Máx. aceptado"), franja normal sombreada entre los
    límites de control, coma decimal y "!" sobre las muestras con señal.
    Con `porcentaje=True` los valores (fracciones) se muestran como %."""
    f = 100.0 if porcentaje else 1.0
    y = np.array([np.nan if v is None else f * v for v in serie["valores"]], dtype=float)
    m = y.size
    x = np.arange(m)
    lcs, lc, lci = (_escalar(serie[k], max(m, 1)) * f for k in ("lcs", "lc", "lci"))
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    xs = x if m else np.array([0])
    ax.fill_between(xs, lci, lcs, step="mid", color=C["lc"], alpha=0.08, lw=0)
    rotulos = (("Límite superior", lcs, C["control"]), ("Promedio", lc, C["lc"]), ("Límite inferior", lci, C["control"]))
    for nombre, val, color in rotulos:
        ax.step(xs, val, where="mid", color=color, lw=1.4)
        ax.annotate(f"{nombre} {_coma(val[-1], decimales)}", (1.0, val[-1]), xycoords=("axes fraction", "data"),
                    xytext=(4, 0), textcoords="offset points", va="center", fontsize=7, color=color)
    for valor, nombre in ((les, "Máx. aceptado"), (lei, "Mín. aceptado")):
        if valor is not None:
            ax.axhline(valor, color=C["espec"], lw=1, ls="--")
            ax.annotate(f"{nombre} {_coma(valor, decimales)}", (1.0, valor), xycoords=("axes fraction", "data"),
                        xytext=(4, 0), textcoords="offset points", va="center", fontsize=7, color=C["espec"])
    if m:
        excl = set(excluidos)
        senal = {v["indice"] for v in serie["violaciones"]}
        incl = [i for i in range(m) if i not in excl and not np.isnan(y[i])]
        ax.plot(incl, y[incl], color=C["dato"], lw=1.2, zorder=2)
        normales = [i for i in incl if i not in senal]
        ax.scatter(normales, y[normales], s=16, facecolor="white", edgecolor=C["dato"], lw=1.2, zorder=3)
        malos = [i for i in incl if i in senal]
        ax.scatter(malos, y[malos], s=34, facecolor="#ffdad6", edgecolor=C["control"], lw=1.5, zorder=4)
        for i in malos:
            ax.annotate("!", (i, y[i]), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=9,
                        fontweight="bold", color=C["control"])
        if excl:
            ex = sorted(excl)
            ax.scatter(ex, y[ex], s=24, marker="x", color=C["espec"], zorder=4)
        paso = max(1, m // 12)
        ax.set_xticks(x[::paso])
        ax.set_xticklabels([str(e) for e in list(etiquetas)[::paso]])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _coma(v, max(0, decimales - 1))))
    ax.set_xlabel("Número de muestra")
    ax.set_ylabel(titulo_y or unidad)
    fig.subplots_adjust(right=0.80)
    return _png(fig)


def histograma_simple(hist: dict, lei=None, les=None, objetivo=None, etiqueta_x="", decimales=2) -> bytes:
    """Histograma para lectores no expertos: rótulos en palabras y coma decimal."""
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    bordes = np.asarray(hist["bordes"])
    ax.bar((bordes[:-1] + bordes[1:]) / 2, hist["cuentas"], width=np.diff(bordes) * 0.92, color=C["barra"],
           edgecolor=C["lc"], lw=0.6)
    ax.plot(hist["curva_x"], hist["curva_y"], color=C["curva"], lw=1.4)
    # El promedio se rotula a la derecha de su línea y el ideal a la izquierda, para que no se
    # superpongan cuando están cerca.
    media = hist["media"]
    ideal_izq = objetivo is None or objetivo <= media
    marcas = ((lei, "Mín. aceptado", C["espec"], "--", 1.0, "left"), (les, "Máx. aceptado", C["espec"], "--", 1.0, "left"),
              (media, "Promedio", C["lc"], "-", 0.93, "left" if ideal_izq else "right"),
              (objetivo, "Ideal", "#264191", ":", 0.93, "right" if ideal_izq else "left"))
    for valor, nombre, color, estilo, altura, lado in marcas:
        if valor is not None:
            ax.axvline(valor, color=color, ls=estilo, lw=1.3)
            ax.annotate(nombre, (valor, altura), xycoords=("data", "axes fraction"), xytext=(3 if lado == "left" else -3, 2),
                        textcoords="offset points", ha=lado, fontsize=7, color=color)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _coma(v, decimales)))
    ax.set_ylabel("Cantidad de unidades")
    ax.set_xlabel(etiqueta_x)
    return _png(fig)


def histograma(hist: dict, lei=None, les=None, objetivo=None, etiqueta_x="") -> bytes:
    """Histograma con curva normal ajustada y líneas LEI/LES/media."""
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    bordes = np.asarray(hist["bordes"])
    ax.bar((bordes[:-1] + bordes[1:]) / 2, hist["cuentas"], width=np.diff(bordes) * 0.92, color=C["barra"],
           edgecolor=C["lc"], lw=0.6)
    ax.plot(hist["curva_x"], hist["curva_y"], color=C["curva"], lw=1.6)
    for valor, nombre, color, estilo in ((lei, "LEI", C["espec"], "--"), (les, "LES", C["espec"], "--"),
                                         (hist["media"], "X̄", C["lc"], "-"), (objetivo, "T", "#264191", ":")):
        if valor is not None:
            ax.axvline(valor, color=color, ls=estilo, lw=1.3)
            # T se rotula un renglón más abajo para no superponerse con X̄.
            ax.annotate(nombre, (valor, 0.93 if nombre == "T" else 1.0), xycoords=("data", "axes fraction"),
                        xytext=(3 if nombre == "T" else 0, 2), textcoords="offset points",
                        ha="left" if nombre == "T" else "center", fontsize=7, color=color)
    ax.set_ylabel("Frecuencia")
    ax.set_xlabel(etiqueta_x)
    return _png(fig)


def qq_y_acf(qq: dict, acf: dict) -> bytes:
    """Q-Q normal con bandas 95 % y correlograma ACF, lado a lado."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.6))
    z = np.asarray(qq["teoricos"])
    a1.fill_between(z, qq["banda_inf"], qq["banda_sup"], color=C["lc"], alpha=0.10, lw=0)
    a1.plot(z, qq["recta"]["intercepto"] + qq["recta"]["pendiente"] * z, color=C["dato"], lw=1.4)
    a1.scatter(z, qq["ordenados"], s=8, facecolor="white", edgecolor=C["ok"], lw=0.8)
    a1.set_title("Q-Q normal (bandas 95 %)", loc="left", fontsize=9, fontweight="bold")
    a1.set_xlabel("Cuantil teórico N(0,1)")
    r = np.asarray(acf["r"])
    colores = [C["control"] if abs(v) > acf["banda"] else C["lc"] for v in r]
    a2.bar(acf["rezagos"], r, color=colores, width=0.5)
    for b in (acf["banda"], -acf["banda"]):
        a2.axhline(b, color=C["control"], ls="--", lw=1)
    a2.axhline(0, color=C["espec"], lw=0.8)
    a2.set_title("ACF (bandas ±1.96/√N)", loc="left", fontsize=9, fontweight="bold")
    a2.set_xlabel("Rezago k")
    fig.tight_layout()
    return _png(fig)


def curvas(series: list[dict], titulo_x: str, titulo_y: str, log_y=False, referencias=()) -> bytes:
    """Curvas genéricas (ARL vs δ, OC…). series: [{nombre, x, y}] con la paleta categórica en orden fijo."""
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    for i, s in enumerate(series):
        ax.plot(s["x"], s["y"], color=SERIES[i % len(SERIES)], lw=1.8, label=s["nombre"])
    for x in referencias:
        ax.axvline(x, color=C["control"], ls=":", lw=1)
    if log_y:
        ax.set_yscale("log")
    ax.set_xlabel(titulo_x)
    ax.set_ylabel(titulo_y)
    if len(series) > 1:
        ax.legend(frameon=False, fontsize=7, ncol=len(series), loc="upper right")
    return _png(fig)
