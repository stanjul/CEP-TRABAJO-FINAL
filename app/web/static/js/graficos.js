/* =========================================================================
 * graficos.js — gráficos Plotly con la paleta y las convenciones del diseño Stitch.
 *
 * Cartas de control (DESIGN.md):  LC sólida petróleo, LCS/LCI rojas, LES/LEI grises punteadas;
 * puntos normales con relleno blanco; los que violan reglas en rojo con anillo; excluidos
 * como "x" gris. Las curvas con varias series (OC, ARL) usan la paleta categórica validada
 * en orden fijo, siempre con leyenda y tooltip.
 * ========================================================================= */
(function () {
  "use strict";

  const C = {
    tinta: "#0b1c30", tinta2: "#40484b", tenue: "#70787c", grilla: "#e5eeff", superficie: "#ffffff",
    dato: "#003441", lc: "#0f4c5c", control: "#ba1a1a", espec: "#70787c", alarma: "#ba1a1a",
    alarmaFondo: "#ffdad6", ok: "#086a5f", zonaA: "rgba(186,26,26,0.05)", zonaB: "rgba(8,106,95,0.04)",
    barra: "#0f4c5c", curva: "#ba1a1a",
  };
  // Paleta categórica (validada: CVD ΔE ≥ 9, normal ΔE ≥ 27). Orden fijo, nunca rotar.
  const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#6250d6"];
  const FUENTE = { family: "Montserrat, sans-serif", size: 10, color: C.tinta2 };

  const CONFIG = { displayModeBar: false, responsive: true, locale: "es" };

  function layoutBase(extra = {}) {
    return {
      margin: { l: 56, r: 92, t: 10, b: 34 },
      paper_bgcolor: C.superficie, plot_bgcolor: C.superficie,
      separators: ",.",  // coma decimal y punto de miles, como el resto de la interfaz
      font: FUENTE, showlegend: false, hovermode: "closest",
      hoverlabel: { bgcolor: "#213145", bordercolor: "#213145", font: { family: "Montserrat, sans-serif", size: 11, color: "#eaf1ff" } },
      xaxis: { gridcolor: C.grilla, zeroline: false, linecolor: "#c0c8cb", tickfont: FUENTE, ...(extra.xaxis || {}) },
      yaxis: { gridcolor: C.grilla, zeroline: false, linecolor: "#c0c8cb", tickfont: FUENTE, ...(extra.yaxis || {}) },
      ...Object.fromEntries(Object.entries(extra).filter(([k]) => !["xaxis", "yaxis"].includes(k))),
    };
  }

  const fmt = (x, d) => (x === null || x === undefined ? "—" : Number(x).toFixed(d).replace(".", ","));
  const esLista = (v) => Array.isArray(v);
  const valorEn = (v, i) => (esLista(v) ? v[i] : v);

  /** Línea horizontal (o escalonada si el límite varía por punto) con etiqueta a la derecha. */
  function lineaRef(xs, valor, { color, ancho = 1.5, guion = "solid", texto, d }) {
    if (valor === null || valor === undefined) return [];
    const varia = esLista(valor);
    const y = varia ? valor : xs.map(() => valor);
    const traza = {
      x: xs, y, mode: "lines", type: "scatter", hoverinfo: "skip",
      line: { color, width: ancho, dash: guion, shape: varia ? "hvh" : "linear" },
    };
    const ultimo = y[y.length - 1];
    const anot = {
      xref: "paper", x: 1.005, y: ultimo, xanchor: "left", yanchor: "middle", showarrow: false,
      text: `${texto} ${fmt(ultimo, d)}`, font: { ...FUENTE, color, size: 10 },
    };
    return [traza, anot];
  }

  /**
   * Carta de control.
   * serie: {nombre, valores, lc, lcs, lci, sigma, violaciones}
   * op: {etiquetas, excluidos(índices), lei, les, decimales, unidad, zonas, alto, ultimo, alHacerClic,
   *      simple}
   * simple = true (vista Operario): rótulos en palabras, franja normal sombreada entre los límites
   * de control y "!" en lugar del código de regla.
   */
  function cartaControl(el, serie, op = {}) {
    const d = op.decimales ?? 3;
    const R = op.simple
      ? { lcs: "Límite sup.", lc: "Promedio", lci: "Límite inf.", les: "Máx. aceptado", lei: "Mín. aceptado" }
      : { lcs: "LCS", lc: "LC", lci: "LCI", les: "LES", lei: "LEI" };
    const n = serie.valores.length;
    // En un eje de categorías Plotly interpreta una x numérica como posición: se usan textos.
    const xs = (op.etiquetas || serie.valores.map((_, i) => i + 1)).map(String);
    const malos = new Map();
    (serie.violaciones || []).forEach((v) => {
      if (!malos.has(v.indice)) malos.set(v.indice, []);
      malos.get(v.indice).push(v.regla);
    });
    const excl = new Set(op.excluidos || []);
    const trazas = [];
    const anots = [];
    const formas = [];

    // Zonas A y B (±1σ…±3σ) sombreadas como rectángulos del layout (solo con límites constantes).
    if (op.zonas && !esLista(serie.lc) && serie.sigma && !esLista(serie.sigma) && n) {
      const lc = serie.lc, s = serie.sigma;
      [[2, 3, C.zonaA], [1, 2, C.zonaB]].forEach(([a, b, col]) => {
        [1, -1].forEach((lado) => formas.push({
          type: "rect", xref: "paper", yref: "y", x0: 0, x1: 1, y0: lc + lado * a * s, y1: lc + lado * b * s,
          fillcolor: col, line: { width: 0 }, layer: "below",
        }));
      });
    }
    // Franja "normal" entre los límites de control (vista simple, límites constantes).
    if (op.simple && !esLista(serie.lcs) && !esLista(serie.lci) && serie.lcs !== null && serie.lci !== null) {
      formas.push({ type: "rect", xref: "paper", yref: "y", x0: 0, x1: 1, y0: serie.lci, y1: serie.lcs,
        fillcolor: "rgba(15,76,92,0.07)", line: { width: 0 }, layer: "below" });
    }
    const xsLim = n ? xs : [0, 1];
    [
      [serie.lcs, { color: C.control, ancho: 2, texto: R.lcs, d }],
      [serie.lc, { color: C.lc, ancho: 2, texto: R.lc, d }],
      [serie.lci, { color: C.control, ancho: 2, texto: R.lci, d }],
      [op.les, { color: C.espec, ancho: 1.5, guion: "dash", texto: R.les, d }],
      [op.lei, { color: C.espec, ancho: 1.5, guion: "dash", texto: R.lei, d }],
    ].forEach(([valor, estilo]) => {
      const [t, a] = lineaRef(xsLim, valor, estilo);
      if (t) { trazas.push(t); anots.push(a); }
    });

    // Polilínea de datos (sin los excluidos para no sugerir continuidad).
    const yLinea = serie.valores.map((v, i) => (excl.has(i) ? null : v));
    trazas.push({ x: xs, y: yLinea, type: "scatter", mode: "lines", line: { color: C.dato, width: 2 }, hoverinfo: "skip", connectgaps: true });

    const texto = serie.valores.map((v, i) => {
      const reglas = malos.get(i);
      const extra = op.textoPunto ? op.textoPunto(i) : "";
      if (op.simple) {
        return `<b>Muestra #${xs[i]}</b><br>${fmt(v, d)} ${op.unidad || ""}` + (reglas ? '<br><span style="color:#ffdad6">⚠ Revisar esta muestra</span>' : "") + extra;
      }
      return `<b>Subgrupo #${xs[i]}</b><br>${serie.nombre} = ${fmt(v, d)} ${op.unidad || ""}`
        + `<br>LCS ${fmt(valorEn(serie.lcs, i), d)} · LCI ${fmt(valorEn(serie.lci, i), d)}`
        + (reglas ? `<br><span style="color:#ffdad6">⚠ ${reglas.join(", ")}</span>` : "")
        + (excl.has(i) ? "<br>Excluido (causa asignable)" : "") + extra;
    });
    const colorBorde = serie.valores.map((_, i) => (excl.has(i) ? C.tenue : malos.has(i) ? C.alarma : C.dato));
    const colorRelleno = serie.valores.map((_, i) => (excl.has(i) ? C.superficie : malos.has(i) ? C.alarmaFondo : C.superficie));
    const tam = serie.valores.map((_, i) => (malos.has(i) ? 11 : 8));
    const simbolo = serie.valores.map((_, i) => (excl.has(i) ? "x-thin-open" : "circle"));
    if (op.ultimo && n) { colorRelleno[n - 1] = C.lc; tam[n - 1] = 12; colorBorde[n - 1] = malos.has(n - 1) ? C.alarma : "#ffffff"; }
    trazas.push({
      x: xs, y: serie.valores, type: "scatter", mode: "markers", text: texto, hovertemplate: "%{text}<extra></extra>",
      marker: { size: tam, color: colorRelleno, symbol: simbolo, line: { color: colorBorde, width: 2 } },
      customdata: serie.valores.map((_, i) => i),
    });
    // Etiqueta de regla sobre los puntos con señal (selectiva, no en todos los puntos).
    malos.forEach((reglas, i) => anots.push({
      x: xs[i], y: serie.valores[i], yshift: 14, showarrow: false, text: op.simple ? "<b>!</b>" : reglas[0],
      font: { family: "Montserrat, sans-serif", size: 9, color: C.alarma },
    }));

    const layout = layoutBase({
      height: op.alto || 260, annotations: anots, shapes: formas,
      ...(op.simple ? { margin: { l: 56, r: 150, t: 10, b: 34 } } : {}),
      xaxis: { title: { text: op.tituloX || "", font: FUENTE }, type: "category", tickmode: "auto", nticks: 14 },
      yaxis: { title: { text: op.tituloY || "", font: FUENTE } },
    });
    Plotly.react(el, trazas, layout, CONFIG);
    if (op.alHacerClic) {
      el.removeAllListeners && el.removeAllListeners("plotly_click");
      el.on("plotly_click", (e) => {
        const p = e.points.find((q) => q.customdata !== undefined);
        if (p) op.alHacerClic(p.customdata);
      });
    }
  }

  /** Histograma (bordes/cuentas del servidor) + curva normal + LEI/LES/objetivo. */
  function histograma(el, h, op = {}) {
    const centros = h.cuentas.map((_, i) => (h.bordes[i] + h.bordes[i + 1]) / 2);
    const ancho = h.bordes[1] - h.bordes[0];
    const d = op.decimales ?? 2;
    const trazas = [
      { x: centros, y: h.cuentas, type: "bar", width: ancho * 0.92, marker: { color: "rgba(15,76,92,0.55)", line: { color: C.lc, width: 1 } },
        hovertemplate: `[%{customdata}]<br>Frecuencia: %{y}<extra></extra>`,
        customdata: h.cuentas.map((_, i) => `${fmt(h.bordes[i], d)} – ${fmt(h.bordes[i + 1], d)}`) },
      { x: h.curva_x, y: h.curva_y, type: "scatter", mode: "lines", line: { color: C.curva, width: 2 }, hoverinfo: "skip" },
    ];
    const formas = [];
    const anots = [];
    [[op.lei, "LEI", C.espec], [op.les, "LES", C.espec], [h.media, "X̄", C.lc], [op.objetivo, "T", "#264191"]].forEach(([x, t, col]) => {
      if (x === null || x === undefined) return;
      formas.push({ type: "line", xref: "x", yref: "paper", x0: x, x1: x, y0: 0, y1: 1,
        line: { color: col, width: t === "X̄" ? 2 : 1.5, dash: t === "LEI" || t === "LES" ? "dash" : "solid" } });
      // X̄ arriba del gráfico; T (objetivo) un renglón más abajo para que no se superpongan.
      anots.push({ x, xref: "x", yref: "paper", y: t === "T" ? 0.96 : 1, yanchor: t === "T" ? "top" : "bottom",
        xanchor: t === "T" ? "left" : "center", showarrow: false, text: `${t} ${fmt(x, d)}`, font: { ...FUENTE, color: col } });
    });
    Plotly.react(el, trazas, layoutBase({
      height: op.alto || 280, bargap: 0.04, shapes: formas, annotations: anots,
      margin: { l: 48, r: 16, t: 22, b: 36 },
      xaxis: { title: { text: op.tituloX || "", font: FUENTE } }, yaxis: { title: { text: "Frecuencia", font: FUENTE } },
    }), CONFIG);
  }

  /** Q-Q normal con recta de referencia y bandas del 95 %. */
  function qq(el, q, op = {}) {
    const z = q.teoricos;
    const recta = z.map((v) => q.recta.intercepto + q.recta.pendiente * v);
    const trazas = [
      { x: z.concat([...z].reverse()), y: q.banda_sup.concat([...q.banda_inf].reverse()), fill: "toself",
        fillcolor: "rgba(15,76,92,0.08)", line: { width: 0 }, mode: "lines", hoverinfo: "skip", type: "scatter" },
      { x: z, y: q.banda_sup, mode: "lines", line: { color: C.lc, width: 1, dash: "dash" }, hoverinfo: "skip", type: "scatter" },
      { x: z, y: q.banda_inf, mode: "lines", line: { color: C.lc, width: 1, dash: "dash" }, hoverinfo: "skip", type: "scatter" },
      { x: z, y: recta, mode: "lines", line: { color: C.dato, width: 2 }, hoverinfo: "skip", type: "scatter" },
      { x: z, y: q.ordenados, mode: "markers", type: "scatter", marker: { size: op.mini ? 5 : 7, color: C.superficie, line: { color: C.ok, width: 1.5 } },
        hovertemplate: "z = %{x:.2f}<br>x = %{y:.3f}<extra></extra>" },
    ];
    Plotly.react(el, trazas, layoutBase({
      height: op.alto || 300, margin: { l: 52, r: 12, t: 8, b: 38 },
      xaxis: { title: { text: op.mini ? "" : "Cuantil teórico N(0,1)", font: FUENTE } },
      yaxis: { title: { text: op.mini ? "" : op.tituloY || "Dato observado", font: FUENTE } },
    }), CONFIG);
  }

  /** Correlograma ACF con bandas ±z/√N. */
  function acf(el, a, op = {}) {
    const colores = a.r.map((r) => (Math.abs(r) > a.banda ? C.alarma : C.lc));
    const trazas = [
      { x: a.rezagos, y: a.r, type: "bar", width: 0.45, marker: { color: colores }, hovertemplate: "k = %{x}<br>r_k = %{y:.3f}<extra></extra>" },
    ];
    const formas = [a.banda, -a.banda].map((b) => ({ type: "line", xref: "paper", x0: 0, x1: 1, y0: b, y1: b, line: { color: C.control, width: 1.5, dash: "dash" } }));
    formas.push({ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: C.tenue, width: 1 } });
    const rango = Math.max(a.banda * 1.6, ...a.r.map(Math.abs)) * 1.1;
    Plotly.react(el, trazas, layoutBase({
      height: op.alto || 240, shapes: formas, margin: { l: 52, r: 60, t: 8, b: 36 },
      annotations: [{ xref: "paper", x: 1.01, y: a.banda, xanchor: "left", showarrow: false, text: `+${a.banda.toFixed(3)}`, font: { ...FUENTE, color: C.control } },
                    { xref: "paper", x: 1.01, y: -a.banda, xanchor: "left", showarrow: false, text: `−${a.banda.toFixed(3)}`, font: { ...FUENTE, color: C.control } }],
      xaxis: { title: { text: "Rezago k", font: FUENTE }, dtick: 1 }, yaxis: { range: [-rango, rango], title: { text: "r_k", font: FUENTE } },
    }), CONFIG);
  }

  /**
   * Curvas genéricas (OC, AOQ, ATI, ARL). series: [{nombre, x, y, guion}] con colores en orden
   * fijo de la paleta categórica. op: {tituloX, tituloY, formatoX, formatoY, refs:[{x|y, texto}], logY}
   */
  function curvas(el, series, op = {}) {
    const trazas = series.map((s, i) => ({
      x: s.x, y: s.y, name: s.nombre, type: "scatter", mode: "lines",
      line: { color: s.color || SERIES[i % SERIES.length], width: 2, dash: s.guion || "solid" },
      hovertemplate: `${s.nombre}<br>${op.etiquetaX || "x"} = %{x${op.formatoX || ""}}<br>${op.etiquetaY || "y"} = %{y${op.formatoY || ""}}<extra></extra>`,
    }));
    (op.puntos || []).forEach((p) => trazas.push({
      x: [p.x], y: [p.y], type: "scatter", mode: "markers+text", text: [p.texto], textposition: p.posicion || "top right",
      textfont: { ...FUENTE, color: C.tinta }, marker: { size: 9, color: p.color || C.tinta, line: { color: C.superficie, width: 2 } },
      hoverinfo: "skip", showlegend: false,
    }));
    const formas = (op.refs || []).map((r) => r.x !== undefined
      ? { type: "line", xref: "x", yref: "paper", x0: r.x, x1: r.x, y0: 0, y1: 1, line: { color: r.color || C.tenue, width: 1, dash: "dot" } }
      : { type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: r.y, y1: r.y, line: { color: r.color || C.tenue, width: 1, dash: "dot" } });
    Plotly.react(el, trazas, layoutBase({
      height: op.alto || 320, shapes: formas, showlegend: series.length > 1, hovermode: "x unified",
      legend: { orientation: "h", x: 0, y: 1.12, font: { family: "Montserrat, sans-serif", size: 11, color: C.tinta2 } },
      margin: { l: 60, r: 20, t: series.length > 1 ? 34 : 10, b: 40 },
      xaxis: { title: { text: op.tituloX || "", font: FUENTE }, tickformat: op.tickX || "" },
      yaxis: { title: { text: op.tituloY || "", font: FUENTE }, tickformat: op.tickY || "", type: op.logY ? "log" : "linear", rangemode: "tozero" },
    }), CONFIG);
  }

  /** Barras simples (p. ej. histograma de longitudes de corrida). */
  function barras(el, x, y, op = {}) {
    Plotly.react(el, [{ x, y, type: "bar", marker: { color: op.color || "rgba(15,76,92,0.6)", line: { color: C.lc, width: 1 } },
      hovertemplate: `${op.etiquetaX || "x"} = %{x}<br>${op.etiquetaY || "y"} = %{y}<extra></extra>` }],
    layoutBase({ height: op.alto || 220, margin: { l: 48, r: 12, t: 8, b: 36 }, bargap: 0.08,
      xaxis: { title: { text: op.tituloX || "", font: FUENTE } }, yaxis: { title: { text: op.tituloY || "", font: FUENTE } } }), CONFIG);
  }

  window.GRAF = { cartaControl, histograma, qq, acf, curvas, barras, COLORES: C, SERIES };
})();
