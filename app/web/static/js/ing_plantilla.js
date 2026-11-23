/* =========================================================================
 * ing_plantilla.js — Plantilla de carga: armar el Excel paramétrico y subirlo llenado.
 * API: GET /plantillas/sugerencia, POST /plantillas/generar (blob .xlsx),
 *      POST /plantillas/revisar y /plantillas/importar (multipart).
 * ========================================================================= */
(function () {
  "use strict";
  const { api, esc, toast } = CEP;
  const $ = (id) => document.getElementById(id);
  let SUG = null;          // sugerencia del proceso elegido
  let nuevas = [];         // variables nuevas [{nombre, unidad, que, n, ...}]
  let archivo = null;      // plantilla llenada elegida

  const QUE = { medida: "La mido", defectuosos: "La clasifico buena o mala", defectos: "Cuento sus fallas" };
  const NOMBRE_TIPO = { xbar_r: "Medición", xbar_s: "Medición", imr: "Medición (de a una)", p: "Unidades defectuosas",
    np: "Unidades defectuosas", c: "Fallas por muestra", u: "Fallas por unidad" };
  const num = (t) => (String(t ?? "").trim() === "" ? null : parseFloat(String(t).replace(",", ".")));
  const entero = (t, def = 0) => { const x = parseInt(t, 10); return Number.isFinite(x) && x >= 0 ? x : def; };
  const inputCls = "h-10 rounded-lg border-outline-variant font-body-md text-body-md";

  // ------------------------------------------------------------------ Proceso y variables existentes
  function pintarProcesos(procesos, activo) {
    $("pl-proceso").innerHTML = procesos.map((p) => `<option value="${p.id}" ${p.id === activo ? "selected" : ""}>${esc(p.nombre)}${p.linea ? ` (${esc(p.linea)})` : ""}</option>`).join("")
      + '<option value="nuevo">+ Proceso nuevo…</option>';
    if (!procesos.length) $("pl-proceso").value = "nuevo";
  }

  async function cambiarProceso() {
    const nuevo = $("pl-proceso").value === "nuevo";
    $("pl-proceso-nuevo").classList.toggle("hidden", !nuevo);
    $("pl-proceso-nuevo").classList.toggle("grid", nuevo);
    SUG = nuevo ? { variables: [] } : await api(`/plantillas/sugerencia?proceso_id=${$("pl-proceso").value}`);
    if (nuevo && !nuevas.length) agregarNueva();
    pintarExistentes();
    previa();
  }

  function pintarExistentes() {
    const vs = SUG.variables;
    $("pl-existentes").innerHTML = vs.length ? vs.map((v) => `
      <tr data-id="${v.id}">
        <td class="py-space-sm pr-space-sm"><input class="w-4 h-4" data-incluir type="checkbox" ${v.fase_i_sugerida + v.fase_ii_sugerida ? "checked" : ""}/></td>
        <td class="py-space-sm pr-space-sm"><span class="font-semibold text-on-surface">${esc(v.nombre)}</span>
          <span class="block font-body-sm text-body-sm text-on-surface-variant">${NOMBRE_TIPO[v.tipo_carta]} · ${v.fase === "II" ? "monitoreando" : "conociendo el proceso"} · sigue desde la muestra #${v.siguiente_numero}</span></td>
        <td class="py-space-sm pr-space-sm"><input class="${inputCls} w-24 mx-auto block text-center" data-fase="i" min="0" type="number" value="${v.fase_i_sugerida}"/></td>
        <td class="py-space-sm"><input class="${inputCls} w-24 mx-auto block text-center" data-fase="ii" min="0" type="number" value="${v.fase_ii_sugerida}"/></td>
      </tr>`).join("")
      : `<tr><td class="py-space-sm text-on-surface-variant" colspan="4">${$("pl-proceso").value === "nuevo" ? "El proceso es nuevo: agrega sus variables abajo." : "Este proceso todavía no tiene variables."}</td></tr>`;
    $("pl-existentes").querySelectorAll("input").forEach((i) => i.addEventListener("input", previa));
  }

  // ------------------------------------------------------------------ Variables nuevas
  function agregarNueva() {
    nuevas.push({ nombre: "", unidad: "", que: "medida", n: 5, tamano_constante: true, decimales: 2, lei: "", objetivo: "", les: "",
      frecuencia_min: 60, fase_i: 25, fase_ii: 0 });
    pintarNuevas();
    previa();
    setTimeout(() => $("pl-nuevas").querySelector(`[data-nueva="${nuevas.length - 1}"] [data-campo="nombre"]`)?.focus(), 30);
  }

  function pintarNuevas() {
    $("pl-nuevas").innerHTML = nuevas.map((x, i) => {
      const medida = x.que === "medida";
      const campo = (c, etiqueta, extra = "", ancho = "") => `<label class="flex flex-col gap-1 ${ancho}"><span class="font-body-sm text-body-sm text-on-surface-variant">${etiqueta}</span>
        <input class="${inputCls}" data-campo="${c}" value="${esc(x[c])}" ${extra}/></label>`;
      return `<div class="flex flex-col gap-space-sm p-space-md rounded-lg border border-outline-variant/60 bg-surface-container-low" data-nueva="${i}">
        <div class="flex items-center justify-between gap-space-sm">
          <span class="font-body-md text-body-md font-semibold">Variable nueva ${i + 1}</span>
          <button class="h-9 px-space-sm rounded-lg text-error hover:bg-error-container font-label-md text-label-md flex items-center gap-1" data-quitar type="button">
            <span class="material-symbols-outlined text-sm">delete</span>Quitar</button>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-space-sm">
          ${campo("nombre", "Nombre", 'maxlength="120" placeholder="Ej.: Peso del pan"', "sm:col-span-2")}
          <label class="flex flex-col gap-1"><span class="font-body-sm text-body-sm text-on-surface-variant">¿Cómo se registra?</span>
            <select class="${inputCls}" data-campo="que">${Object.entries(QUE).map(([k, t]) => `<option value="${k}" ${k === x.que ? "selected" : ""}>${t}</option>`).join("")}</select></label>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-space-sm">
          ${campo("n", medida ? "Unidades por muestra" : "Unidades revisadas", 'type="number" min="1"')}
          ${campo("frecuencia_min", "Cada cuántos minutos", 'type="number" min="1"')}
          ${campo("fase_i", "Para establecer límites", 'type="number" min="0"')}
          ${campo("fase_ii", "Monitoreo", 'type="number" min="0"')}
        </div>
        ${medida ? `<div class="grid grid-cols-2 sm:grid-cols-5 gap-space-sm">
          ${campo("unidad", "Unidad", 'maxlength="30" placeholder="g, mm…"')}
          ${campo("decimales", "Decimales", 'type="number" min="0" max="6"')}
          ${campo("lei", "Mínimo aceptado", 'inputmode="decimal"')}
          ${campo("objetivo", "Valor ideal", 'inputmode="decimal"')}
          ${campo("les", "Máximo aceptado", 'inputmode="decimal"')}</div>`
        : `<label class="flex items-center gap-space-xs font-body-md text-body-md"><input class="w-4 h-4" data-campo="variable" type="checkbox" ${x.tamano_constante ? "" : "checked"}/>
            La cantidad de unidades revisadas cambia de una muestra a otra</label>`}
      </div>`;
    }).join("");
    $("pl-nuevas").querySelectorAll("[data-nueva]").forEach((caja) => {
      const i = +caja.dataset.nueva;
      caja.querySelector("[data-quitar]").onclick = () => { nuevas.splice(i, 1); pintarNuevas(); previa(); };
      caja.querySelectorAll("[data-campo]").forEach((el) => el.addEventListener(el.tagName === "SELECT" || el.type === "checkbox" ? "change" : "input", () => {
        const c = el.dataset.campo;
        if (c === "variable") nuevas[i].tamano_constante = !el.checked;
        else nuevas[i][c] = el.value;
        if (c === "que") {
          if (el.value === "defectuosos" && +nuevas[i].n < 20) nuevas[i].n = 50;
          if (el.value === "defectos" && +nuevas[i].n === 50) nuevas[i].n = 1;
          if (el.value === "medida" && +nuevas[i].n === 50) nuevas[i].n = 5;
          pintarNuevas();
        }
        previa();
      }));
    });
  }

  // ------------------------------------------------------------------ Pedido y vista previa
  function pedido() {
    const p = { lote: $("pl-op-lote").checked, operario: $("pl-op-operario").checked, observaciones: $("pl-op-observaciones").checked, variables: [] };
    if ($("pl-proceso").value === "nuevo") { p.proceso_nombre = $("pl-proc-nombre").value; p.proceso_linea = $("pl-proc-linea").value; }
    else p.proceso_id = +$("pl-proceso").value;
    if ($("pl-inicio").value) p.fecha_inicio = $("pl-inicio").value;
    $("pl-existentes").querySelectorAll("tr[data-id]").forEach((tr) => {
      if (!tr.querySelector("[data-incluir]").checked) return;
      p.variables.push({ id: +tr.dataset.id, fase_i: entero(tr.querySelector('[data-fase="i"]').value), fase_ii: entero(tr.querySelector('[data-fase="ii"]').value) });
    });
    nuevas.forEach((x) => p.variables.push({ nombre: x.nombre, unidad: x.unidad, que: x.que, n: entero(x.n, 1) || 1,
      tamano_constante: x.tamano_constante, decimales: entero(x.decimales, 2), lei: num(x.lei), objetivo: num(x.objetivo), les: num(x.les),
      frecuencia_min: entero(x.frecuencia_min, 60) || 60, fase_i: entero(x.fase_i), fase_ii: entero(x.fase_ii) }));
    return p;
  }

  /** Columnas que tendrá la hoja (mismo criterio que app/core/plantilla.columnas_de). */
  function columnas(tipo, n, unidad, op) {
    const u = unidad ? ` (${unidad})` : "";
    let cols = ["Muestra", "Fecha", "Hora"];
    if (tipo === "medida") cols = cols.concat(n === 1 ? [`Valor${u}`] : [...Array(n)].map((_, i) => `Unidad ${i + 1}${u}`), n > 1 ? ["Promedio", "Rango"] : []);
    else if (tipo === "defectuosos") cols.push("Revisadas", "Defectuosas", "% defectuosas");
    else if (tipo === "defectos_var") cols.push("Unidades revisadas", "Fallas", "Fallas por unidad");
    else cols.push("Fallas");
    if (op.lote) cols.push("Lote");
    if (op.operario) cols.push("Operario");
    if (op.observaciones) cols.push("Observaciones");
    return cols;
  }

  function previa() {
    const p = pedido();
    const porId = Object.fromEntries((SUG ? SUG.variables : []).map((v) => [v.id, v]));
    const hojas = p.variables.filter((v) => v.fase_i + v.fase_ii > 0).map((v) => {
      if (v.id) {
        const e = porId[v.id];
        const tipo = ["xbar_r", "xbar_s", "imr"].includes(e.tipo_carta) ? "medida" : ["p", "np"].includes(e.tipo_carta) ? "defectuosos" : e.tipo_carta === "u" ? "defectos_var" : "defectos";
        return { nombre: e.nombre, cols: columnas(tipo, e.tipo_carta === "imr" ? 1 : e.n, e.unidad, p), i: v.fase_i, ii: v.fase_ii, desde: e.siguiente_numero };
      }
      const tipo = v.que === "defectos" ? (v.tamano_constante ? "defectos" : "defectos_var") : v.que;
      return { nombre: v.nombre || "(sin nombre)", cols: columnas(tipo, v.n, v.unidad, p), i: v.fase_i, ii: v.fase_ii, desde: 1, nueva: true };
    });
    const total = hojas.reduce((a, h) => a + h.i + h.ii, 0);
    $("pl-resumen").textContent = hojas.length ? `${hojas.length} ${hojas.length === 1 ? "hoja" : "hojas"} de datos y ${total} muestras en total, más una hoja de instrucciones.`
      : "Elige al menos una variable con muestras.";
    $("pl-descargar").disabled = !hojas.length;
    $("pl-previa").innerHTML = hojas.map((h) => `<div class="flex flex-col gap-1">
      <div class="flex items-baseline justify-between gap-space-sm"><span class="font-body-md text-body-md font-semibold">${esc(h.nombre)}${h.nueva ? ' <span class="font-body-sm text-body-sm font-normal text-primary">(nueva)</span>' : ""}</span>
        <span class="font-body-sm text-body-sm text-on-surface-variant">muestras #${h.desde} a #${h.desde + h.i + h.ii - 1}</span></div>
      <div class="overflow-x-auto rounded border border-outline-variant/50"><table class="w-full font-label-sm text-label-sm"><thead><tr class="bg-primary-container text-on-primary">
        ${h.cols.map((c) => `<th class="px-2 py-1 font-semibold whitespace-nowrap text-left">${esc(c)}</th>`).join("")}</tr></thead>
        <tbody>${h.i ? `<tr class="bg-surface-container-high"><td class="px-2 py-1" colspan="${h.cols.length}">Para establecer los límites · ${h.i} muestras</td></tr>` : ""}
        ${h.ii ? `<tr class="bg-surface-container-high"><td class="px-2 py-1" colspan="${h.cols.length}">Monitoreo · ${h.ii} muestras</td></tr>` : ""}</tbody></table></div></div>`).join("");
  }

  // ------------------------------------------------------------------ Descarga
  async function descargar(e) {
    e.preventDefault();
    const error = $("pl-error");
    error.classList.add("hidden");
    const btn = $("pl-descargar");
    btn.disabled = true;
    try {
      const r = await fetch("/api/plantillas/generar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(pedido()) });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(Array.isArray(d.detail) ? d.detail.map((x) => x.msg).join(" · ") : d.detail || `Error ${r.status}`);
      }
      const disp = r.headers.get("content-disposition") || "";
      const m = /filename\*=UTF-8''([^;]+)/.exec(disp) || /filename="([^"]+)"/.exec(disp);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(await r.blob());
      a.download = m ? decodeURIComponent(m[1]) : "CEP_plantilla.xlsx";
      a.click();
      toast("Plantilla descargada. Llénala en Excel y súbela en el paso 2.");
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    } finally { btn.disabled = false; }
  }

  // ------------------------------------------------------------------ Subida: revisar e importar
  async function enviar(ruta, extra = {}) {
    const fd = new FormData();
    fd.append("archivo", archivo);
    Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
    return api(`/plantillas/${ruta}`, { method: "POST", body: fd });
  }

  async function elegirArchivo(f) {
    if (!f) return;
    archivo = f;
    const caja = $("pl-informe");
    caja.classList.remove("hidden"); caja.classList.add("flex");
    caja.innerHTML = '<p class="font-body-md text-body-md text-on-surface-variant">Revisando el archivo…</p>';
    try { pintarInforme(await enviar("revisar")); }
    catch (e) {
      caja.innerHTML = `<div class="flex items-start gap-space-sm p-space-md rounded-lg bg-error-container text-on-error-container">
        <span class="material-symbols-outlined">error</span><p class="font-body-md text-body-md">${esc(e.message)}</p></div>`;
    }
  }

  function pintarInforme(r) {
    const tarjetas = r.variables.map((v) => {
      const chips = [`<span class="px-2 py-0.5 rounded bg-primary-fixed/60 font-label-sm text-label-sm">${v.nueva ? "Variable nueva: se creará" : v.fase === "II" ? "En monitoreo" : "Conociendo el proceso"}</span>`];
      const datos = [[v.a_cargar, "se cargarán"], [v.ya_cargadas, "ya estaban cargadas"], [v.otra_fase, "quedan para después"], [v.vacias, "vacías"], [v.errores.length, "con errores"]]
        .filter(([k]) => k).map(([k, t]) => `<span><b>${k}</b> ${t}</span>`).join(" · ");
      const lista = (items, cls, icono) => items.length ? `<ul class="flex flex-col gap-1">${items.slice(0, 15).map((x) => `<li class="flex items-start gap-space-xs ${cls} font-body-sm text-body-sm">
          <span class="material-symbols-outlined text-base">${icono}</span><span>${esc(x.texto)}</span></li>`).join("")}${items.length > 15 ? `<li class="font-body-sm text-body-sm text-on-surface-variant">… y ${items.length - 15} más</li>` : ""}</ul>` : "";
      return `<article class="flex flex-col gap-space-sm p-space-md rounded-lg border border-outline-variant/60">
        <div class="flex flex-wrap items-center justify-between gap-space-sm"><h3 class="font-headline-sm text-headline-sm font-bold">${esc(v.nombre)}</h3>${chips.join("")}</div>
        <p class="font-body-md text-body-md text-on-surface">${datos || "Sin muestras escritas todavía."}</p>
        ${lista(v.errores, "text-error", "error")}${lista(v.avisos, "text-[#B45309]", "warning")}</article>`;
    }).join("");
    const hayNuevas = r.variables.some((v) => v.nueva && v.a_cargar);
    $("pl-informe").innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-space-sm">
        <div class="flex flex-col"><span class="font-headline-sm text-headline-sm font-bold">Informe de revisión · ${esc(archivo.name)}</span>
          <span class="font-body-md text-body-md text-on-surface-variant">${r.total_cargar} ${r.total_cargar === 1 ? "muestra lista" : "muestras listas"} para cargar${r.total_errores ? ` · ${r.total_errores} con errores (no se cargan; corrígelas en el Excel y vuelve a subirlo)` : ""}.</span></div>
        <div class="flex gap-space-sm">
          <button class="h-12 px-space-md rounded-lg bg-surface-container-low hover:bg-surface-container font-label-md text-label-md font-semibold" id="pl-cancelar" type="button">Cancelar</button>
          <button class="h-12 px-space-lg rounded-lg bg-primary hover:bg-primary-container text-on-primary font-label-lg text-label-lg font-bold flex items-center gap-space-xs disabled:opacity-50" id="pl-cargar" type="button" ${r.total_cargar ? "" : "disabled"}>
            <span class="material-symbols-outlined">cloud_upload</span>Cargar ${r.total_cargar} ${r.total_cargar === 1 ? "muestra" : "muestras"}</button>
        </div>
      </div>
      ${hayNuevas ? '<p class="font-body-sm text-body-sm text-on-surface-variant">Al cargar se crearán las variables nuevas (y el proceso, si es nuevo). Queda registrado en el historial de cambios.</p>' : ""}
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-space-md">${tarjetas}</div>`;
    $("pl-cancelar").onclick = limpiarSubida;
    $("pl-cargar").onclick = cargar;
  }

  function limpiarSubida() {
    archivo = null;
    $("pl-archivo").value = "";
    $("pl-informe").classList.add("hidden");
    $("pl-informe").classList.remove("flex");
  }

  async function cargar() {
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    const btn = $("pl-cargar");
    btn.disabled = true;
    try {
      const r = await enviar("importar", { usuario, crear_nuevas: "true" });
      toast(`Se cargaron ${r.total} ${r.total === 1 ? "muestra" : "muestras"}.`);
      $("pl-informe").innerHTML = `<div class="flex flex-col gap-space-sm p-space-md rounded-lg bg-[#E7F6EC]">
        <span class="font-headline-sm text-headline-sm font-bold text-[#15803D]">Carga terminada: ${r.total} ${r.total === 1 ? "muestra" : "muestras"}</span>
        <ul class="flex flex-col gap-1 font-body-md text-body-md">${r.variables.map((v) => `<li>${esc(v.nombre)}: ${v.cargadas} cargadas${v.nueva ? " (variable creada)" : ""}
          ${v.id ? ` · <a class="text-primary underline" href="${CEP.conVariable("/ingenieria/variables", v.id)}">ver gráfica</a>` : ""}</li>`).join("")}</ul>
        <span class="font-body-sm text-body-sm text-on-surface-variant">Huella del archivo (SHA-256): ${esc(r.sha256.slice(0, 16))}… · Puedes seguir llenando la misma plantilla y volver a subirla.</span></div>`;
      archivo = null;
      $("pl-archivo").value = "";
    } catch (e) { toast(e.message, "error"); btn.disabled = false; }
  }

  // ------------------------------------------------------------------ Inicio
  async function iniciar(ctx) {
    pintarProcesos(ctx.procesos, ctx.proceso ? ctx.proceso.id : null);
    $("pl-proceso").onchange = cambiarProceso;
    ["pl-proc-nombre", "pl-proc-linea", "pl-op-lote", "pl-op-operario", "pl-op-observaciones"].forEach((id) => $(id).addEventListener("input", previa));
    $("pl-agregar").onclick = agregarNueva;
    $("pl-form").addEventListener("submit", descargar);
    const ahora = new Date(); ahora.setMinutes(0, 0, 0);
    $("pl-inicio").value = new Date(ahora - ahora.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    $("pl-archivo").addEventListener("change", (e) => elegirArchivo(e.target.files[0]));
    const zona = $("pl-zona");
    ["dragover", "dragenter"].forEach((t) => zona.addEventListener(t, (e) => { e.preventDefault(); zona.classList.add("bg-primary-fixed/20"); }));
    zona.addEventListener("dragleave", () => zona.classList.remove("bg-primary-fixed/20"));
    zona.addEventListener("drop", (e) => { e.preventDefault(); zona.classList.remove("bg-primary-fixed/20"); elegirArchivo(e.dataTransfer.files[0]); });
    await cambiarProceso();
  }

  CEP.arrancar(iniciar);
})();
