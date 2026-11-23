/* =========================================================================
 * ing_reportes.js — Módulo 8: plantilla + módulos → vista previa A4, generación PDF/Excel,
 * historial con descarga y verificación SHA-256.
 * API: /reportes/plantillas, /reportes/vista-previa, /reportes/generar, /reportes, /reportes/{id}/...
 * ========================================================================= */
(function () {
  "use strict";
  const { api, fmt, pct, esc, toast, fechaHora } = CEP;
  const $ = (id) => document.getElementById(id);
  let V, PLANT, zoom = 1;

  const plantilla = () => document.querySelector('input[name="plantilla"]:checked').value;
  const modulos = () => [...document.querySelectorAll("[data-modulo]")].filter((c) => c.checked).map((c) => c.dataset.modulo);
  const pedido = (formato) => ({ variable_id: V.id, plantilla: plantilla(), modulos: modulos(), formato, usuario: CEP.usuario() || null });

  function marcarModulosDePlantilla() {
    const activos = PLANT.plantillas[plantilla()].modulos;
    document.querySelectorAll("[data-modulo]").forEach((c) => (c.checked = activos.includes(c.dataset.modulo)));
  }

  // ------------------------------------------------------------------ Vista previa
  async function previsualizar() {
    const papel = $("report-paper");
    papel.innerHTML = '<p class="text-center text-outline py-space-xl">Generando vista previa…</p>';
    let c;
    try { c = await api("/reportes/vista-previa", { json: pedido("pdf") }); }
    catch (e) { papel.innerHTML = `<p class="text-error p-space-lg">${esc(e.message)}</p>`; return; }
    // Refleja la primera página del PDF (mismos textos, calculados en app/core/reporte_latex.py).
    const v = c.variable, pr = c.proceso, inf = c.informe;
    const est = { verde: "bg-[#E7F6EC] text-[#15803D]", ambar: "bg-[#FEF3C7] text-[#B45309]",
      rojo: "bg-[#FDE8E8] text-[#B91C1C]", neutro: "bg-surface-container text-on-surface-variant" }[inf.estado.color];
    const titulos = { integral: "Informe del proceso", capacidad: "Informe de capacidad del proceso",
      control: "Informe de control del proceso", auditoria: "Informe de cambios y alertas" };
    const conResumen = c.modulos.includes("resumen");
    const sgs = (c.carta && c.carta.subgrupos) || [];
    const conCarta = c.carta && sgs.length > 0 && (c.modulos.includes("cartas") || conResumen);
    const periodo = sgs.length ? `${CEP.fecha(sgs[0].timestamp)} al ${CEP.fecha(sgs[sgs.length - 1].timestamp)}` : "Sin muestras";
    papel.innerHTML = `
      <div class="border-t-4 border-primary-container pt-space-sm flex flex-col gap-1">
        <h2 class="font-headline-lg text-headline-lg font-bold text-on-surface">${titulos[c.plantilla] || "Informe del proceso"}</h2>
        <span class="font-body-lg text-body-lg text-on-surface-variant">${esc(pr.nombre)}${pr.linea ? ` (${esc(pr.linea)})` : ""} · ${esc(v.nombre)}</span>
      </div>
      <dl class="grid grid-cols-2 gap-x-space-lg gap-y-1 font-body-sm text-body-sm">
        <div class="flex gap-space-sm"><dt class="text-outline w-28">Fecha del informe</dt><dd>${esc(c.fecha)}</dd></div>
        <div class="flex gap-space-sm"><dt class="text-outline w-24">Folio</dt><dd>${esc(c.folio)}</dd></div>
        <div class="flex gap-space-sm"><dt class="text-outline w-28">Período analizado</dt><dd>${esc(periodo)}</dd></div>
        <div class="flex gap-space-sm"><dt class="text-outline w-24">Generado por</dt><dd>${esc(c.usuario)}</dd></div>
      </dl>
      <div class="p-space-md rounded ${est}">
        <p class="font-headline-sm text-headline-sm font-bold">${esc(inf.estado.titulo)}</p>
        <p class="font-body-md text-body-md text-on-surface">${esc(inf.estado.texto)}</p>
      </div>
      ${conResumen && inf.hallazgos.length ? `<div class="flex flex-col gap-space-xs">
        <h3 class="font-headline-sm text-headline-sm font-bold text-primary-container">En pocas palabras</h3>
        <ul class="list-disc pl-space-lg flex flex-col gap-1 font-body-md text-body-md">${inf.hallazgos.map((h) => `<li>${esc(h)}</li>`).join("")}</ul></div>` : ""}
      ${conResumen && inf.indicadores.length ? `<div class="flex flex-col gap-space-xs">
        <h3 class="font-headline-sm text-headline-sm font-bold text-primary-container">Indicadores principales</h3>
        <table class="w-full font-body-sm text-body-sm"><thead><tr class="border-y border-on-surface"><th class="py-1 text-left">Indicador</th>
          <th class="py-1 text-left">Valor</th><th class="py-1 text-left">Qué significa</th></tr></thead>
          <tbody>${inf.indicadores.map(([a, b, d]) => `<tr class="align-top"><td class="py-1 pr-2">${esc(a)}</td><td class="py-1 pr-2 font-bold">${esc(b)}</td>
            <td class="py-1 text-on-surface-variant">${esc(d)}</td></tr>`).join("")}</tbody></table></div>` : ""}
      ${conCarta ? `<div class="flex flex-col gap-space-xs">
        <h3 class="font-headline-sm text-headline-sm font-bold text-primary-container">Cómo se comportó el proceso</h3>
        <div class="grafico" id="prev-carta"></div></div>` : ""}
      <p class="mt-auto pt-space-sm border-t border-outline-variant/50 font-body-sm text-body-sm text-outline">
        Vista previa de la primera página. El PDF completo incluye ${c.modulos.length} sección(es), glosario y anexo técnico; solo describe los datos, sin recomendaciones.</p>`;
    if (conCarta) {
      const k = Object.keys(c.carta.cartas)[0];
      const s = c.carta.cartas[k];
      const esP = v.tipo_carta === "p";
      const x100 = (y) => (y === null || y === undefined ? y : Array.isArray(y) ? y.map((z) => 100 * z) : 100 * y);
      const serie = esP ? { ...s, valores: s.valores.map((y) => (y === null ? null : 100 * y)), lc: x100(s.lc), lcs: x100(s.lcs), lci: x100(s.lci) } : s;
      const attr = CEP.esAtributos(v);
      GRAF.cartaControl($("prev-carta"), serie, { etiquetas: c.carta.etiquetas, excluidos: c.carta.excluidos, alto: 230, simple: true,
        decimales: esP ? 1 : attr ? 2 : v.decimales + 1, lei: attr ? null : v.lei, les: attr ? null : v.les, tituloX: "Número de muestra" });
    }
  }

  // ------------------------------------------------------------------ Generación e historial
  async function generar(formato, boton) {
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    if (!modulos().length) return toast("Seleccione al menos un módulo.", "aviso");
    const original = boton.innerHTML;
    boton.disabled = true;
    boton.innerHTML = '<span class="material-symbols-outlined animate-spin">refresh</span>Generando…';
    try {
      const r = await api("/reportes/generar", { json: { ...pedido(formato), usuario } });
      if (r.motor === "reportlab") {
        toast(`${r.nombre_archivo} generado con el formato de respaldo (no se pudo usar LaTeX: ${r.aviso}).`, "aviso");
      } else {
        toast(`${r.nombre_archivo} generado${r.motor === "latex" ? " con LaTeX" : ""} (${fmt(r.tamano_bytes / 1024, 0)} KB).`);
      }
      window.location.href = `/api/reportes/${r.id}/descargar`;
      await cargarHistorial();
    } catch (e) { toast(e.message, "error"); }
    boton.disabled = false;
    boton.innerHTML = original;
  }

  async function cargarHistorial() {
    const lista = await api(`/reportes?variable_id=${V.id}`);
    $("hist-resumen").textContent = lista.length ? `Últimos ${lista.length} informes de «${V.nombre}»` : "Aún no se generaron reportes para esta variable";
    $("tabla-reportes").innerHTML = lista.map((r) => `<tr class="hover:bg-surface-container-low">
      <td class="py-2 px-space-sm font-label-md text-label-md font-bold text-primary">${esc(r.nombre_archivo)}</td>
      <td class="py-2 px-space-sm font-body-sm text-body-sm">${esc(r.titulo)}</td>
      <td class="py-2 px-space-sm"><span class="px-1.5 py-0.5 rounded font-label-sm text-label-sm font-bold ${r.formato === "pdf" ? "bg-error-container text-on-error-container" : "bg-secondary-container text-on-secondary-container"}">${r.formato.toUpperCase()}</span></td>
      <td class="py-2 px-space-sm text-right font-label-md text-label-md">${fmt(r.tamano_bytes / 1024, 0)} KB</td>
      <td class="py-2 px-space-sm font-label-sm text-label-sm">${fechaHora(r.fecha)}</td>
      <td class="py-2 px-space-sm font-body-sm text-body-sm">${esc(r.usuario || "—")}</td>
      <td class="py-2 px-space-sm font-label-sm text-label-sm"><span title="${esc(r.sha256)}">#${esc(r.sha256.slice(0, 12))}…</span></td>
      <td class="py-2 px-space-sm text-center whitespace-nowrap">
        <a class="p-1 rounded hover:bg-surface-container inline-flex" href="/api/reportes/${r.id}/descargar" title="Descargar"><span class="material-symbols-outlined text-primary">download</span></a>
        <button class="p-1 rounded hover:bg-surface-container inline-flex" data-verificar="${r.id}" title="Verificar integridad (SHA-256)" type="button"><span class="material-symbols-outlined text-secondary">verified</span></button></td></tr>`).join("")
      || '<tr><td class="py-space-md px-space-sm text-outline" colspan="8">Sin reportes.</td></tr>';
    $("tabla-reportes").querySelectorAll("[data-verificar]").forEach((b) => (b.onclick = async () => {
      try {
        const r = await api(`/reportes/${b.dataset.verificar}/verificar`);
        toast(r.integro ? "Integridad verificada: el archivo no fue modificado." : "¡El archivo fue modificado después de generarse!", r.integro ? "ok" : "error");
      } catch (e) { toast(e.message, "error"); }
    }));
  }

  function pintarAlcance(ctx) {
    $("alc-proceso").textContent = ctx.proceso.nombre;
    $("alc-linea").textContent = `${ctx.proceso.planta || ""} ${ctx.proceso.linea ? "· " + ctx.proceso.linea : ""}`;
    $("alc-variable").textContent = `${V.nombre} (${V.unidad})`;
    $("alc-espec").textContent = V.lei !== null || V.les !== null ? `LEI ${V.lei ?? "—"} · Objetivo ${V.objetivo ?? "—"} · LES ${V.les ?? "—"}` : `Carta ${CEP.NOMBRES_CARTA[V.tipo_carta]} (sin especificaciones)`;
    api(`/variables/${V.id}/subgrupos`).then((todos) => {
      const sgs = todos.filter((s) => s.fase !== "anulado");  // las anuladas no cuentan como datos
      $("alc-datos").textContent = `${sgs.length} subgrupos · n = ${V.n}`;
      $("alc-periodo").textContent = sgs.length ? `${CEP.fecha(sgs[0].timestamp)} – ${CEP.fecha(sgs[sgs.length - 1].timestamp)}` : "Sin datos";
    });
  }

  async function iniciar(ctx) {
    V = ctx.variable;
    if (!V) return;
    PLANT = await api("/reportes/plantillas");
    if (!PLANT.latex) {
      $("motor-pdf").textContent = "LaTeX no está instalado en este equipo: el PDF se genera con el formato de respaldo (reportlab). "
        + "Para el informe con LaTeX instale MiKTeX (ver docs/INSTALACION.md).";
      $("motor-pdf").className = "font-body-sm text-body-sm text-[#B45309] bg-[#FEF3C7] p-space-xs rounded";
    }
    pintarAlcance(ctx);
    marcarModulosDePlantilla();
    document.querySelectorAll('input[name="plantilla"]').forEach((r) => (r.onchange = () => { marcarModulosDePlantilla(); previsualizar(); }));
    document.querySelectorAll("[data-modulo]").forEach((c) => (c.onchange = previsualizar));
    $("btn-todos").onclick = () => {
      const marcar = !modulos().length;
      document.querySelectorAll("[data-modulo]").forEach((c) => (c.checked = marcar));
      $("btn-todos").textContent = marcar ? "Desmarcar todo" : "Marcar todo";
      previsualizar();
    };
    $("btn-previa").onclick = previsualizar;
    document.querySelectorAll("[data-formato]").forEach((b) => (b.onclick = () => generar(b.dataset.formato, b)));
    $("zoom-in").onclick = () => { zoom = Math.min(1.3, zoom + 0.1); $("report-paper").style.transform = `scale(${zoom})`; $("zoom-txt").textContent = `Escala: ${Math.round(zoom * 100)} %`; };
    $("zoom-out").onclick = () => { zoom = Math.max(0.6, zoom - 0.1); $("report-paper").style.transform = `scale(${zoom})`; $("zoom-txt").textContent = `Escala: ${Math.round(zoom * 100)} %`; };
    await previsualizar();
    await cargarHistorial();
  }

  CEP.arrancar(iniciar);
})();
