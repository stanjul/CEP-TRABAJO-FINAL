/* =========================================================================
 * operario_comun.js — piezas compartidas por las pantallas del Operario
 * ("Registrar muestra" y "Cómo va el proceso"). Todo en palabras simples.
 *
 *  OPER.pintarEstado(R, V)          tarjeta de estado: color, título y qué hacer.
 *  OPER.graficar(el, R, V, alto)    gráfica simple de las últimas muestras.
 *  OPER.resumenVentana(R, V)        lista de frases cortas sobre las últimas muestras.
 *  OPER.unidadDe(V)                 unidad para mostrar ("g", "%", "fallas"…).
 *  OPER.valorCarta(V, x)            texto del estadístico graficado (con unidad).
 * Fuente de datos: GET /api/variables/{id}/operario
 * ========================================================================= */
(function () {
  "use strict";
  const { fmt, pct, esc } = CEP;
  const $ = (id) => document.getElementById(id);

  // Colores de semáforo reservados para el estado del proceso (DESIGN.md).
  const ESTADO = {
    verde: { caja: "bg-secondary-container/40", circulo: "bg-[#15803D]", icono: "check" },
    ambar: { caja: "bg-[#FEF3C7]", circulo: "bg-[#B45309]", icono: "priority_high" },
    rojo: { caja: "bg-error-container/60", circulo: "bg-[#B91C1C]", icono: "front_hand" },
    gris: { caja: "bg-surface-container-lowest", circulo: "bg-outline", icono: "school" },
  };

  const esP = (V) => ["p", "np"].includes(V.tipo_carta);
  function unidadDe(V) {
    if (V.tipo_carta === "p") return "%";
    if (V.tipo_carta === "np") return "defectuosas";
    if (V.tipo_carta === "c") return "fallas";
    if (V.tipo_carta === "u") return "fallas por unidad";
    return V.unidad || "";
  }
  /** Valor del estadístico graficado como texto (p en %, el resto con su unidad). */
  function valorCarta(V, x) {
    if (x === null || x === undefined) return "—";
    if (V.tipo_carta === "p") return pct(x, 1);
    if (V.tipo_carta === "np" || V.tipo_carta === "c") return `${fmt(x, 0)} ${unidadDe(V)}`;
    if (V.tipo_carta === "u") return `${fmt(x, 2)} ${unidadDe(V)}`;
    return `${fmt(x, V.decimales + 1)} ${V.unidad}`;
  }

  function pintarEstado(R, V) {
    const s = R.semaforo;
    const e = ESTADO[s.color] || ESTADO.gris;
    $("estado").className = `rounded-xl shadow-sm p-space-lg flex flex-col lg:flex-row lg:items-center justify-between gap-space-lg ${e.caja}`;
    $("est-circulo").className = `w-16 h-16 shrink-0 rounded-full flex items-center justify-center text-on-secondary ${e.circulo}`;
    $("est-icono").textContent = e.icono;
    $("est-titulo").textContent = s.titulo;
    $("est-que-hacer").textContent = s.que_hacer;
    const p = R.proceso;
    $("est-variable").textContent = `${p.linea || p.nombre} · ${V.nombre}${V.unidad && !CEP.esAtributos(V) ? ` (${V.unidad})` : ""}`;
  }

  /** Gráfica simple de la carta de posición (X̄, I, p, np, c o u) con las últimas 25 muestras. */
  function graficar(el, R, V, alto = 300) {
    const carta = R.carta;
    const claves = Object.keys(carta.cartas || {});
    if (carta.error || !claves.length) {
      el.innerHTML = `<div class="p-space-xl text-center flex flex-col items-center gap-space-xs">
        <span class="material-symbols-outlined text-4xl text-outline">insert_chart</span>
        <p class="font-body-md text-body-md text-on-surface-variant">${esc(carta.error || carta.mensaje || "Todavía no hay muestras.")}<br>Registra la primera muestra para ver la gráfica.</p></div>`;
      return false;
    }
    const s = carta.cartas[claves[0]];
    const attr = CEP.esAtributos(V);
    const serie = V.tipo_carta === "p"
      ? { ...s, valores: s.valores.map((x) => (x === null ? null : 100 * x)), lc: escala(s.lc), lcs: escala(s.lcs), lci: escala(s.lci), sigma: escala(s.sigma) }
      : s;
    GRAF.cartaControl(el, serie, {
      etiquetas: carta.etiquetas, excluidos: carta.excluidos || [], simple: true, ultimo: true,
      decimales: V.tipo_carta === "p" ? 1 : attr ? 2 : V.decimales + 1, unidad: unidadDe(V),
      lei: attr ? null : V.lei, les: attr ? null : V.les, alto,
      tituloX: "Número de muestra", tituloY: attr ? (V.tipo_carta === "p" ? "% defectuosas" : unidadDe(V)) : (claves[0] === "xbar" ? `Promedio de la muestra (${V.unidad})` : `Valor (${V.unidad})`),
    });
    return true;
  }
  const escala = (v) => (v === null || v === undefined ? v : Array.isArray(v) ? v.map((x) => 100 * x) : 100 * v);

  /** Frases cortas sobre las últimas muestras (lo que el operario necesita saber). */
  function resumenVentana(R, V) {
    const w = R.ventana || {};
    const items = [];
    if (!w.muestras) return [["info", "Todavía no hay muestras en esta etapa.", ""]];
    if (w.pct_dentro !== undefined) {
      items.push([w.pct_dentro >= 0.99 ? "check_circle" : "warning",
        `${pct(w.pct_dentro, w.pct_dentro >= 0.999 && w.pct_dentro < 1 ? 1 : 0)} de las unidades dentro de lo aceptado`,
        `${w.dentro} de ${w.unidades} unidades medidas`]);
    }
    if (w.promedio !== undefined && w.promedio !== null) {
      const ideal = V.objetivo ?? (V.lei !== null && V.les !== null ? (V.lei + V.les) / 2 : null);
      items.push(["straighten", `Promedio: ${fmt(w.promedio, V.decimales + 1)} ${V.unidad}`,
        ideal !== null ? `El valor ideal es ${fmt(ideal, V.decimales)} ${V.unidad}` : ""]);
    }
    if (w.pct_defectuosos !== undefined) items.push(["rule", `${pct(w.pct_defectuosos, 1)} de unidades defectuosas`, "en las últimas muestras"]);
    if (w.defectos_por_muestra !== undefined) items.push(["pest_control", `${fmt(w.defectos_por_muestra, 1)} fallas por muestra`, "en promedio"]);
    if (w.defectos_por_unidad !== undefined) items.push(["pest_control", `${fmt(w.defectos_por_unidad, 2)} fallas por unidad`, "en promedio"]);
    items.push([w.con_senal ? "warning" : "check_circle",
      w.con_senal ? `${w.con_senal} ${w.con_senal === 1 ? "muestra para revisar" : "muestras para revisar"}` : "Ninguna muestra fuera de lo normal",
      `de las últimas ${w.muestras}`]);
    return items;
  }
  function htmlResumen(items) {
    return items.map(([icono, texto, sub]) => `<li class="flex items-start gap-space-sm p-space-sm rounded-lg bg-surface-container-low">
      <span class="material-symbols-outlined text-primary-container">${icono}</span>
      <span class="flex flex-col"><span class="font-body-md text-body-md font-semibold text-on-surface">${esc(texto)}</span>
      ${sub ? `<span class="font-body-sm text-body-sm text-on-surface-variant">${esc(sub)}</span>` : ""}</span></li>`).join("");
  }

  window.OPER = { pintarEstado, graficar, resumenVentana, htmlResumen, unidadDe, valorCarta, esP };
})();
