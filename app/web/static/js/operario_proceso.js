/* =========================================================================
 * operario_proceso.js — "Cómo va el proceso" (Operario): gráfica grande con guía de lectura,
 * resumen de las últimas muestras y muestras para revisar, todo en palabras simples.
 * API: GET /variables/{id}/operario (se refresca cada 30 s)
 * ========================================================================= */
(function () {
  "use strict";
  const { api, fmt, hora, esc } = CEP;
  const $ = (id) => document.getElementById(id);
  let V, R;

  function guia() {
    const attr = CEP.esAtributos(V);
    const d = V.decimales;
    const items = [
      ["scatter_plot", attr ? "Cada punto es una muestra: muestra cuántas defectuosas o fallas tuvo." : (V.tipo_carta === "imr"
        ? "Cada punto es una unidad medida." : `Cada punto es el promedio de una muestra de ${V.n} unidades.`)],
      ["horizontal_rule", "La línea del medio es el promedio habitual del proceso."],
      ["select", "La franja sombreada, entre las dos líneas rojas, es la zona normal. Si un punto sale de ahí, aparece una alerta."],
    ];
    if (!attr && (V.lei !== null || V.les !== null)) {
      const partes = [];
      if (V.lei !== null) partes.push(`mínimo ${fmt(V.lei, d)}`);
      if (V.les !== null) partes.push(`máximo ${fmt(V.les, d)}`);
      items.push(["straighten", `Las líneas punteadas grises son los valores que acepta el cliente (${partes.join(" y ")} ${V.unidad}).`]);
    }
    items.push(["priority_high", "Un punto rojo con «!» es una muestra para revisar: abajo se explica por qué."]);
    if (V.fase === "I") items.push(["school", "Todavía se está conociendo el proceso: la zona normal puede cambiar hasta que el ingeniero la fije."]);
    $("guia").innerHTML = items.map(([i, t]) => `<li class="flex items-start gap-space-sm">
      <span class="material-symbols-outlined text-primary-container">${i}</span><span>${esc(t)}</span></li>`).join("");
  }

  /** Muestras con señal en la ventana, explicadas en palabras (la más reciente primero). */
  function paraRevisar() {
    const carta = R.carta;
    const lista = [];
    Object.entries(carta.cartas || {}).forEach(([clave, c]) => {
      const dispersion = ["r", "s", "mr"].includes(clave);
      (c.violaciones || []).filter((x) => x.inicio).forEach((x) => {
        const sg = (carta.subgrupos || [])[x.indice];
        const texto = dispersion ? "Las unidades de esta muestra son demasiado distintas entre sí: la variación aumentó." : x.explicacion;
        lista.push({ indice: x.indice, numero: carta.etiquetas[x.indice], cuando: sg ? hora(sg.timestamp) : "", texto });
      });
    });
    lista.sort((a, b) => b.indice - a.indice);
    $("para-revisar").innerHTML = lista.length ? lista.slice(0, 10).map((x) => `<li class="flex items-start gap-space-sm p-space-sm rounded-lg bg-surface-container-low">
        <span class="material-symbols-outlined text-error">priority_high</span>
        <span class="flex flex-col"><span class="font-body-md text-body-md font-semibold text-on-surface">Muestra #${x.numero}${x.cuando ? ` · ${x.cuando}` : ""}</span>
        <span class="font-body-sm text-body-sm text-on-surface-variant">${esc(x.texto)}</span></span></li>`).join("")
      : `<li class="flex items-center gap-space-sm p-space-sm rounded-lg bg-surface-container-low">
          <span class="material-symbols-outlined text-[#15803D]">check_circle</span>
          <span class="font-body-md text-body-md text-on-surface-variant">Ninguna muestra fuera de lo normal en las últimas ${(carta.etiquetas || []).length}.</span></li>`;
  }

  async function refrescar() {
    R = await api(`/variables/${V.id}/operario`);
    V = R.variable;
    OPER.pintarEstado(R, V);
    const n = (R.carta.etiquetas || []).length;
    $("graf-titulo").textContent = n > 1 ? `Últimas ${n} muestras` : n === 1 ? "Primera muestra" : "Últimas muestras";
    OPER.graficar($("graf-1"), R, V, 400);
    $("resumen-ventana").innerHTML = OPER.htmlResumen(OPER.resumenVentana(R, V));
    guia();
    paraRevisar();
    $("aside-frecuencia").textContent = CEP.cadaCuanto(V.frecuencia_min);
    const seg = R.segundos_para_muestra;
    $("aside-proxima").textContent = R.estado_muestreo === "fuera_de_turno" ? "Fuera de turno: no hay muestras pendientes."
      : R.estado_muestreo === "sin_mas_muestras" ? "No quedan muestras en este turno."
        : seg >= 0 ? `Próxima muestra en ${Math.ceil(seg / 60)} min (#${R.proximo_numero}).`
          : `La muestra #${R.proximo_numero} está atrasada.`;
  }

  CEP.arrancar(async (ctx) => {
    if (!ctx.variable) return;
    V = ctx.variable;
    await refrescar();
    setInterval(() => refrescar().catch(() => {}), 30000);
  });
})();
