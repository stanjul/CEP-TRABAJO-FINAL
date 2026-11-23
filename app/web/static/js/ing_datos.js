/* =========================================================================
 * ing_datos.js — Módulo 1: carga de CSV/Excel, mapeo de columnas, subgrupos, limpieza,
 * descriptivos e importación a una variable (Fase I).
 * API: /api/datos/analizar → /api/datos/preparar → /api/datos/importar | /api/datos/exportar
 * ========================================================================= */
(function () {
  "use strict";
  const { api, fmt, esc, toast } = CEP;
  const $ = (id) => document.getElementById(id);

  const ROLES = {
    fecha: "Fecha y hora del muestreo", subgrupo: "Identificador de subgrupo", muestra: "Posición dentro del subgrupo",
    valor: "Variable crítica CTQ (valor)", conteo: "Conteo (defectuosos / defectos)", tamano: "Tamaño de muestra / unidades",
    operario: "Operario (contexto)", lote: "Lote (trazabilidad)", ignorar: "Ignorar columna",
  };
  const ICONOS_TIPO = { entero: "tag", decimal: "decimal_increase", fecha: "schedule", texto: "badge", vacia: "block" };

  let archivo = null, analisis = null, mapeo = {}, prep = null, pestana = "previa", temporizador = null, ctx = null;

  function formulario(extra = {}) {
    const fd = new FormData();
    fd.append("archivo", archivo);
    fd.append("codificacion", $("opt-cod").value);
    fd.append("encabezado", $("opt-encabezado").checked);
    if ($("opt-delim").value) fd.append("delimitador", $("opt-delim").value);
    Object.entries(extra).forEach(([k, v]) => v !== null && v !== undefined && v !== "" && fd.append(k, v));
    return fd;
  }
  const opcionesPrep = () => ({
    mapeo: JSON.stringify(mapeo), n: $("opt-n").value, faltantes: $("opt-faltantes").value,
    atipicos: $("opt-atipicos").value, excluir_atipicos: $("opt-excluir-atipicos").checked,
  });

  // ------------------------------------------------------------------ Lectura
  async function cargarArchivo(f) {
    if (!f) return;
    archivo = f;
    $("arch-nombre").textContent = f.name;
    $("arch-detalle").textContent = `(${fmt(f.size / 1024, 0)} KB)`;
    try {
      analisis = await api("/datos/analizar", { method: "POST", body: formulario() });
    } catch (e) {
      toast(e.message, "error");
      return;
    }
    mapeo = { ...analisis.mapeo_sugerido };
    const nulos = analisis.perfil.reduce((a, p) => a + p.nulos, 0);
    $("arch-estado").classList.replace("hidden", "flex");
    $("arch-estado-txt").textContent = `${analisis.filas} filas, ${analisis.columnas.length} columnas, ${nulos} nulos`;
    pintarMapeo();
    await preparar();
  }

  function pintarMapeo() {
    const filas = analisis.perfil.map((p) => {
      const rol = mapeo[p.columna] || "ignorar";
      const rango = p.min !== undefined ? (typeof p.min === "number" ? `Mín: ${fmt(p.min, 3)} | Máx: ${fmt(p.max, 3)}` : `${esc(p.min)} a ${esc(p.max)}`)
        : `${p.unicos} valores únicos: ${p.ejemplos.map(esc).join(", ")}`;
      const estado = rol === "ignorar" ? '<span class="font-label-sm text-label-sm text-outline">Ignorada</span>'
        : rol === "valor" || rol === "conteo" ? '<span class="inline-flex items-center gap-1 font-label-sm text-label-sm font-bold text-on-secondary-container bg-secondary-container px-2 py-0.5 rounded"><span class="material-symbols-outlined text-xs">verified</span>CTQ</span>'
        : '<span class="inline-flex items-center gap-1 font-label-sm text-label-sm font-semibold text-primary bg-surface-container px-2 py-0.5 rounded"><span class="material-symbols-outlined text-xs">check_circle</span>Mapeado OK</span>';
      return `<tr class="hover:bg-surface-container-low">
        <td class="py-2 px-space-sm font-label-md text-label-md font-bold text-on-surface">${rol === "valor" ? '<span class="material-symbols-outlined text-sm text-secondary align-middle">stars</span> ' : ""}${esc(p.columna)}</td>
        <td class="py-2 px-space-sm"><span class="inline-flex items-center gap-1 font-label-sm text-label-sm text-on-surface-variant"><span class="material-symbols-outlined text-sm">${ICONOS_TIPO[p.tipo] || "help"}</span>${p.tipo}</span></td>
        <td class="py-2 px-space-sm"><select class="h-9 w-64 rounded border-outline-variant font-body-sm text-body-sm" data-columna="${esc(p.columna)}">
          ${Object.entries(ROLES).map(([k, t]) => `<option value="${k}" ${k === rol ? "selected" : ""}>${t}</option>`).join("")}</select></td>
        <td class="py-2 px-space-sm font-label-sm text-label-sm text-on-surface-variant">${rango}</td>
        <td class="py-2 px-space-sm font-label-sm text-label-sm ${p.nulos ? "text-error font-bold" : "text-outline"}">${p.nulos}</td>
        <td class="py-2 px-space-sm">${estado}</td></tr>`;
    }).join("");
    $("tabla-mapeo").innerHTML = filas;
    $("tabla-mapeo").querySelectorAll("select[data-columna]").forEach((s) => (s.onchange = () => {
      mapeo[s.dataset.columna] = s.value;
      pintarMapeo();
      programarPreparacion();
    }));
    const asignadas = Object.values(mapeo).filter((r) => r !== "ignorar").length;
    $("map-contador").textContent = `${asignadas}/${analisis.columnas.length} columnas asignadas`;
  }

  function programarPreparacion() {
    clearTimeout(temporizador);
    temporizador = setTimeout(preparar, 300);
  }

  async function preparar() {
    if (!archivo) return;
    const destino = ctx.todas.find((v) => v.id === +$("opt-destino").value);
    if (destino && CEP.esAtributos(destino)) {  // para atributos no hay subgrupos de mediciones
      prep = null;
      $("resumen-config").textContent = "Destino por atributos: asigne las columnas de conteo y tamaño y pulse Importar.";
      $("btn-importar").disabled = false;
      $("btn-exportar").disabled = true;
      pintarPestana();
      return;
    }
    try {
      prep = await api("/datos/preparar", { method: "POST", body: formulario(opcionesPrep()) });
    } catch (e) {
      prep = null;
      $("resumen-config").textContent = e.message;
      $("resumen-ok").innerHTML = '<span class="material-symbols-outlined text-sm text-error">error</span><span class="text-error">Revise el mapeo</span>';
      $("btn-importar").disabled = $("btn-exportar").disabled = true;
      pintarPestana();
      return;
    }
    const inf = prep.informe;
    $("resumen-config").textContent = `Configuración lista: ${prep.descriptivos.N} lecturas en ${inf.k_subgrupos} subgrupos de ${inf.tamanos.join("/")} (${inf.n_constante ? "n constante" : "n variable"}).`;
    $("resumen-ok").innerHTML = `<span class="w-2 h-2 rounded-full ${inf.n_constante ? "bg-secondary" : "bg-[#B45309]"}"></span>${inf.n_constante ? "Parámetros consistentes" : "n variable: use X̄-S"}`;
    $("btn-importar").disabled = $("btn-exportar").disabled = false;
    pintarDescriptivos();
    pintarPestana();
  }

  // ------------------------------------------------------------------ Resultados
  function pintarDescriptivos() {
    const d = prep.descriptivos;
    const col = Object.keys(mapeo).filter((c) => mapeo[c] === "valor");
    $("desc-ctq").textContent = `CTQ: ${col.join(", ") || "—"}`;
    const val = {
      N: [fmt(d.N, 0), d.k_subgrupos ? `${d.k_subgrupos} subgrupos${d.n ? " × " + d.n : ""}` : ""],
      media: [fmt(d.media, 3), ""], s: [fmt(d.s, 4), d.sigma_s_c4 ? `s̄/c₄ = ${fmt(d.sigma_s_c4, 4)}` : ""],
      r_barra: [d.r_barra !== undefined ? fmt(d.r_barra, 4) : "—", d.sigma_r_d2 ? `R̄/d₂ = ${fmt(d.sigma_r_d2, 4)}` : "n variable"],
      mediana: [fmt(d.mediana, 3), `IQR = ${fmt(d.iqr, 3)}`], rango: [`${fmt(d.minimo, 2)} – ${fmt(d.maximo, 2)}`, `Asimetría ${fmt(d.asimetria, 2)}`],
    };
    Object.entries(val).forEach(([k, [a, b]]) => { $(`desc-${k}`).textContent = a; $(`desc-${k}-sub`).textContent = b; });
    if (prep.histograma) GRAF.histograma($("graf-hist"), prep.histograma, { alto: 220, decimales: 2 });
    const ad = prep.normalidad && prep.normalidad.pruebas.anderson_darling;
    $("desc-ad").textContent = ad ? `p-valor Anderson-Darling = ${fmt(ad.p_valor, 3)}` : "—";
    const at = prep.informe.atipicos;
    $("previa-atipicos").textContent = `${at.cantidad || 0} atípico(s) detectado(s) (${at.metodo === "iqr" ? "Tukey 1.5×IQR" : at.metodo === "sigma" ? "3σ" : "sin filtro"})`;
  }

  function tabla(cabeceras, filas, alinearDerecha = []) {
    return `<table class="w-full text-left"><thead class="sticky top-0"><tr class="bg-surface-container-high font-label-sm text-label-sm">
      ${cabeceras.map((c, i) => `<th class="py-2 px-space-sm ${alinearDerecha.includes(i) ? "text-right" : ""}">${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${filas.map((f, j) => `<tr class="${j % 2 ? "bg-surface-container-low" : ""}">${f.map((c, i) => `<td class="py-1.5 px-space-sm font-label-md text-label-md ${alinearDerecha.includes(i) ? "text-right" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  }

  function pintarPestana() {
    document.querySelectorAll("[data-pestana]").forEach((b) => {
      b.className = `px-space-md py-1 rounded font-label-sm text-label-sm ${b.dataset.pestana === pestana ? "bg-surface-container-lowest text-primary font-bold shadow-sm" : "text-on-surface-variant"}`;
    });
    const cont = $("previa");
    if (!analisis) { cont.innerHTML = '<p class="p-space-md text-outline">Sin archivo.</p>'; return; }
    if (pestana === "previa") {
      const cols = analisis.columnas;
      cont.innerHTML = tabla(cols, analisis.vista_previa.map((f) => cols.map((c) => esc(f[c] ?? "—"))));
      $("previa-pie").textContent = `Primeras ${analisis.vista_previa.length} de ${analisis.filas} filas.`;
    } else if (pestana === "subgrupos") {
      if (!prep) { cont.innerHTML = '<p class="p-space-md text-outline">Sin subgrupos (revise el mapeo).</p>'; return; }
      cont.innerHTML = tabla(["Subgrupo", "Fecha", "n", "Valores", "Media"], prep.subgrupos_muestra.map((g) => [
        `#${esc(g.id)}`, esc(g.fecha || "—"), g.valores.length, g.valores.map((x) => fmt(x, 3)).join(" · "),
        fmt(g.valores.reduce((a, b) => a + b, 0) / g.valores.length, 3)]), [2, 4]);
      $("previa-pie").textContent = `Primeros ${prep.subgrupos_muestra.length} de ${prep.subgrupos_total} subgrupos.`;
    } else {
      if (!prep) { cont.innerHTML = '<p class="p-space-md text-outline">Sin informe.</p>'; return; }
      const inf = prep.informe;
      const f = inf.faltantes;
      const at = inf.atipicos;
      cont.innerHTML = tabla(["Paso", "Resultado"], [
        ["Filas leídas", inf.filas_originales],
        ["Faltantes / no numéricos", `${f.faltantes} (método: ${esc(f.metodo)}; descartados ${f.descartados ?? 0}, imputados ${f.imputados ?? 0})`],
        ["Atípicos", `${at.cantidad || 0}${at.limites ? ` fuera de [${fmt(at.limites[0], 3)}, ${fmt(at.limites[1], 3)}]` : ""}${$("opt-excluir-atipicos").checked ? " — eliminados" : " — conservados"}`],
        ["Filas atípicas", (inf.filas_atipicas || []).map((i) => i + 2).join(", ") || "—"],
        ["Subgrupos formados", `${inf.k_subgrupos} (tamaños: ${inf.tamanos.join(", ")})`],
      ]);
      $("previa-pie").textContent = "Las filas atípicas se numeran como en el archivo (fila 1 = cabecera).";
    }
  }

  // ------------------------------------------------------------------ Acciones
  async function importar() {
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    const destino = ctx.todas.find((v) => v.id === +$("opt-destino").value);
    if (destino.fase === "II") return toast("La variable está en Fase II: vuelva a la Fase I para importar una nueva base.", "aviso");
    const r = await CEP.modal({
      titulo: `Importar a «${destino.nombre}»`,
      texto: `Los subgrupos se agregan a la <b>Fase I</b> de la variable (${CEP.NOMBRES_CARTA[destino.tipo_carta]}, n = ${destino.n}).`,
      campos: [{ nombre: "reemplazar", etiqueta: "Datos existentes de la Fase I", tipo: "select", valor: "false",
        opciones: [["false", "Agregar a los existentes"], ["true", "Reemplazar los existentes"]] }],
      aceptar: "Importar",
    });
    if (!r) return;
    try {
      const res = await api("/datos/importar", { method: "POST", body: formulario({ ...opcionesPrep(), variable_id: destino.id, reemplazar: r.reemplazar, usuario }) });
      const omit = res.informe.omitidos_incompletos ? ` (${res.informe.omitidos_incompletos} incompletos omitidos)` : "";
      toast(`${res.importados} subgrupos importados${omit}.`);
      const destinoUrl = CEP.esAtributos(destino) ? "/ingenieria/atributos" : "/ingenieria/variables";
      setTimeout(() => (location.href = CEP.conVariable(destinoUrl, destino.id)), 900);
    } catch (e) { toast(e.message, "error"); }
  }

  async function exportar() {
    try {
      const blob = await api("/datos/exportar", { method: "POST", body: formulario(opcionesPrep()) });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = archivo.name.replace(/\.[^.]+$/, "") + "_depurado.csv";
      a.click();
    } catch (e) { toast(e.message, "error"); }
  }

  function pintarDestino() {
    const v = ctx.todas.find((x) => x.id === +$("opt-destino").value);
    if (!v) return;
    $("opt-destino-txt").textContent = `${CEP.NOMBRES_CARTA[v.tipo_carta]} · n = ${v.n} · Fase ${v.fase}${v.fase === "II" ? " (no admite importación)" : ""}`;
    if (!$("opt-n").dataset.tocado) $("opt-n").value = v.tipo_carta === "imr" ? 1 : v.n;
  }

  async function iniciar(c) {
    ctx = c;
    $("opt-destino").innerHTML = ctx.procesos.map((p) => `<optgroup label="${esc(p.nombre)}">${p.variables.map((v) =>
      `<option value="${v.id}" ${ctx.variable && v.id === ctx.variable.id ? "selected" : ""}>${esc(v.nombre)}</option>`).join("")}</optgroup>`).join("");
    pintarDestino();
    $("opt-destino").onchange = () => { pintarDestino(); programarPreparacion(); };
    $("opt-n").oninput = () => { $("opt-n").dataset.tocado = "1"; programarPreparacion(); };
    ["opt-faltantes", "opt-atipicos", "opt-excluir-atipicos"].forEach((id) => ($(id).onchange = programarPreparacion));
    ["opt-delim", "opt-cod", "opt-encabezado"].forEach((id) => ($(id).onchange = () => archivo && cargarArchivo(archivo)));
    ["inp-archivo", "inp-archivo-2"].forEach((id) => ($(id).onchange = (e) => cargarArchivo(e.target.files[0])));
    const zona = $("zona-arrastre");
    zona.addEventListener("dragover", (e) => { e.preventDefault(); zona.classList.add("border-primary-container"); });
    zona.addEventListener("dragleave", () => zona.classList.remove("border-primary-container"));
    zona.addEventListener("drop", (e) => { e.preventDefault(); zona.classList.remove("border-primary-container"); cargarArchivo(e.dataTransfer.files[0]); });
    $("btn-redetectar").onclick = () => { if (analisis) { mapeo = { ...analisis.mapeo_sugerido }; pintarMapeo(); preparar(); } };
    document.querySelectorAll("[data-pestana]").forEach((b) => (b.onclick = () => { pestana = b.dataset.pestana; pintarPestana(); }));
    $("btn-importar").onclick = importar;
    $("btn-exportar").onclick = exportar;
    pintarPestana();
  }

  CEP.arrancar(iniciar);
})();
