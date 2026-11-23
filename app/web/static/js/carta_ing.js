/* =========================================================================
 * carta_ing.js — pantallas de Ingeniería "Gráficos por Variables" y "Gráficos por Atributos".
 *
 *  - Fase I: límites estimados; se marcan subgrupos a excluir, se simula el impacto
 *    (Δ límites, Cpk antes → después) y se aplica el recálculo con causa asignable.
 *  - Congelar límites → Fase II (monitoreo con límites fijos). Volver a Fase I con motivo.
 *  - Auditoría de reglas (preset WE / Nelson) y cambio de tipo de carta con justificación.
 * La pantalla se detecta con <body data-pagina="variables|atributos">.
 * ========================================================================= */
(function () {
  "use strict";
  const { api, fmt, pct, esc, toast, fecha } = CEP;
  const $ = (id) => document.getElementById(id);
  const MODO = document.body.dataset.pagina;            // "variables" | "atributos"
  const POR_PAGINA = 15;

  let V, CARTA, CAP, CATALOGO, ALARMAS_SG = {};
  let faseVista = "I";
  let pendientes = new Set();                            // números de subgrupo marcados para excluir
  let pagina = 1;
  let seleccionado = null;

  // Φ(z) normal estándar (aprox. de Abramowitz-Stegun 7.1.26, error < 1.5e-7).
  function Phi(z) {
    const t = 1 / (1 + 0.3275911 * Math.abs(z) / Math.SQRT2);
    const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-z * z / 2);
    return z >= 0 ? (1 + y) / 2 : (1 - y) / 2;
  }

  const esAttr = () => CEP.esAtributos(V);
  const ultimo = (v) => (Array.isArray(v) ? v[v.length - 1] : v);
  const claves = () => Object.keys(CARTA.cartas || {});
  const dec = () => (V.tipo_carta === "p" ? 4 : V.decimales + 1);
  const f = (x) => (x === null || x === undefined ? "—" : V.tipo_carta === "p" ? pct(x, 2) : fmt(x, dec()));
  const u = () => (esAttr() ? "" : ` ${V.unidad}`);

  // ------------------------------------------------------------------ Carga
  async function cargar() {
    document.getElementById("pantalla").classList.add("cargando");
    try {
      CARTA = await api(`/variables/${V.id}/carta?fase=${faseVista}`);
      CAP = null;
      if (!esAttr() && (V.lei !== null || V.les !== null) && !CARTA.vacio) {
        // Si la fase mostrada aún no tiene datos (Fase II recién iniciada), se usa el criterio
        // automático de la API (base de Fase I hasta juntar 20 subgrupos de Fase II).
        CAP = await api(`/variables/${V.id}/capacidad?fase=${faseVista}`)
          .catch(() => api(`/variables/${V.id}/capacidad`)).catch(() => null);
      }
      ALARMAS_SG = {};
      if (faseVista === "II") {
        const alarmas = await api(`/alarmas?variable_id=${V.id}&limite=2000`);
        alarmas.forEach((a) => { if (a.subgrupo_id) (ALARMAS_SG[a.subgrupo_id] = ALARMAS_SG[a.subgrupo_id] || []).push(a); });
      }
      pendientes = new Set((CARTA.subgrupos || []).filter((s) => s.excluido).map((s) => s.numero));
      pintarTodo();
    } finally {
      document.getElementById("pantalla").classList.remove("cargando");
    }
  }

  function pintarTodo() {
    pintarBarra();
    if (CARTA.vacio) {
      $("graf-1").innerHTML = `<p class="p-space-xl text-center font-body-md text-on-surface-variant">${esc(CARTA.mensaje)} Cargue datos en <a class="text-primary underline" href="${CEP.conVariable("/ingenieria/datos", V.id)}">Datos & Carga CSV</a> o regístrelos en la vista de Operario.</p>`;
      return;
    }
    pintarKpis();
    pintarGraficos();
    pintarReglas();
    pintarCapacidad();
    pintarTabla();
    pintarSimulacion(null);
  }

  // ------------------------------------------------------------------ Barra superior
  function pintarBarra() {
    const activo = "bg-primary text-on-primary font-semibold shadow-sm";
    const inactivo = "text-on-surface-variant";
    $("btn-fase-1").className = `px-space-md py-1 font-label-md text-label-md rounded transition-all ${faseVista === "I" ? activo : inactivo}`;
    $("btn-fase-2").className = `px-space-md py-1 font-label-md text-label-md rounded transition-all flex items-center gap-space-xs ${faseVista === "II" ? activo : inactivo} ${V.fase === "I" ? "opacity-40 cursor-not-allowed" : ""}`;
    $("fase-2-ping").classList.toggle("hidden", V.fase !== "II");
    const lc = CARTA.limites_congelados;
    $("chip-limites").innerHTML = V.fase === "II"
      ? `<span class="material-symbols-outlined text-sm">verified</span>Límites congelados ${lc ? fecha(lc.creado) : ""}`
      : `<span class="material-symbols-outlined text-sm">pending</span>Límites provisionales (Fase I)`;
    $("fase-tip-titulo").textContent = faseVista === "II" ? "Fase II: Monitoreo" : "Fase I: Estimación basal";
    $("fase-tip-texto").textContent = faseVista === "II"
      ? `Límites fijados con ${lc ? lc.m_usados : "—"} subgrupos tras depurar causas especiales. Los subgrupos nuevos se evalúan sin recalcular.`
      : "Los límites se estiman con los subgrupos no excluidos. Excluya solo subgrupos con causa asignable comprobada y recalcule.";

    document.querySelectorAll("#selector-carta [data-tipo]").forEach((b) => {
      const act = b.dataset.tipo === V.tipo_carta;
      b.className = `px-space-md py-1.5 rounded-lg font-label-md text-label-md whitespace-nowrap transition-all flex items-center gap-space-xs ${act ? "bg-surface-container-lowest text-primary font-bold shadow-sm" : "text-on-surface-variant hover:text-primary"}`;
    });

    const sgs = CARTA.subgrupos || [];
    $("chip-periodo").textContent = sgs.length ? `${fecha(sgs[0].timestamp)} – ${fecha(sgs[sgs.length - 1].timestamp)}` : "Sin datos";
    const N = esAttr() ? sgs.reduce((a, s) => a + (s.tamano || 0), 0) : sgs.reduce((a, s) => a + (s.valores || []).length, 0);
    $("chip-datos").textContent = `${sgs.length} subgrupos · n=${V.n}${esAttr() && V.tipo_carta === "c" ? "" : ` · N=${N}`}`;
    const lotes = sgs.map((s) => s.lote).filter(Boolean);
    $("chip-lote").textContent = lotes.length ? lotes[lotes.length - 1] : "—";

    const btn = $("btn-fase-accion");
    btn.innerHTML = V.fase === "I"
      ? '<span class="material-symbols-outlined text-sm">lock</span><span>Congelar Límites → Fase II</span>'
      : '<span class="material-symbols-outlined text-sm">lock_open</span><span>Volver a Fase I</span>';
  }

  // ------------------------------------------------------------------ KPIs
  function pintarKpis() {
    const [k1, k2] = claves();
    const s1 = CARTA.cartas[k1];
    const titulos = { xbar: "Carta X̄ (Medias)", i: "Carta I (Individuales)", p: "Carta p (Fracción)", np: "Carta np (Número)", c: "Carta c (Defectos)", u: "Carta u (Defectos/unidad)" };
    if ($("k1-titulo")) $("k1-titulo").textContent = titulos[k1];
    if ($("k1-n")) $("k1-n").textContent = V.tipo_carta === "imr" ? "n = 1" : CARTA.n_variable ? "n variable" : `n = ${V.n}`;
    $("k1-lc").textContent = f(ultimo(s1.lc));
    $("k1-unidad").textContent = `${esAttr() ? "" : V.unidad + " "}(LC)`;
    const varia = Array.isArray(s1.lcs);
    $("k1-lcs").textContent = `LCS${varia ? " (último)" : ""}: ${f(ultimo(s1.lcs))}${u()}`;
    $("k1-lci").textContent = `LCI${varia ? " (último)" : ""}: ${f(ultimo(s1.lci))}${u()}`;
    if ($("k1-les")) {
      $("k1-les").textContent = `LES: ${V.les !== null && !esAttr() ? fmt(V.les, V.decimales) + u() : "—"}`;
      $("k1-lei").textContent = `LEI: ${V.lei !== null && !esAttr() ? fmt(V.lei, V.decimales) + u() : "—"}`;
    }
    if (k2 && $("k2-titulo")) {
      const s2 = CARTA.cartas[k2];
      $("k2-titulo").textContent = { r: "Carta R (Rangos)", s: "Carta S (Desv. Estándar)", mr: "Carta MR (Rangos Móviles)" }[k2];
      $("k2-formula").textContent = { r: "D4·R̄ / D3·R̄", s: "B4·s̄ / B3·s̄", mr: "D4·MR̄ (n=2)" }[k2];
      $("k2-lc").textContent = f(ultimo(s2.lc));
      $("k2-unidad").textContent = `${V.unidad} (${{ r: "R̄", s: "s̄", mr: "MR̄" }[k2]})`;
      $("k2-lcs").textContent = `LCS: ${f(ultimo(s2.lcs))}${u()}`;
      $("k2-lci").textContent = `LCI: ${f(ultimo(s2.lci))}${u()}`;
      $("k2-sigma-t").textContent = `σ̂ = ${CARTA.estimador || "—"}`;
      $("k2-sigma").textContent = CARTA.sigma_hat ? `${fmt(CARTA.sigma_hat, dec())}${u()}` : "—";
    }
    if ($("k3-constantes")) {
      const c = CARTA.constantes || {};
      const lista = { xbar_r: [["A₂", c.A2], ["D₃", c.D3], ["D₄", c.D4], ["d₂", c.d2]],
        xbar_s: [["A₃", c.A3], ["B₃", c.B3], ["B₄", c.B4], ["c₄", c.c4]],
        imr: [["d₂ (n=2)", 1.128], ["D₄ (n=2)", 3.267], ["E₂ = 3/d₂", 2.66]] }[V.tipo_carta] || [];
      $("k3-constantes").innerHTML = lista.map(([n, val]) => `<div class="px-space-xs py-1 bg-surface-container-low rounded flex items-center gap-1 font-label-sm text-label-sm">
        <span class="text-outline">${n}:</span><span class="font-bold text-primary">${val === undefined ? "—" : Number(val).toFixed(val < 1 && n.startsWith("c") ? 4 : 3)}</span></div>`).join("");
      $("k3-cpk").textContent = CAP ? `${fmt(CAP.indices.cpk, 2)} (${{ capaz: "Adecuado", marginal: "Marginal", no_capaz: "No capaz" }[CAP.veredicto.nivel]})` : (V.lei === null && V.les === null ? "Sin especificación" : "Sin datos suficientes");
      $("k3-cpk").className = `font-bold text-label-md ${!CAP || CAP.indices.cpk >= 1.33 ? "text-secondary" : "text-error"}`;
    }
    pintarDiagnostico();
  }

  function violacionesPorPunto() {
    const m = new Map();
    claves().forEach((k) => CARTA.cartas[k].violaciones.forEach((v) => {
      if (!m.has(v.indice)) m.set(v.indice, []);
      m.get(v.indice).push({ ...v, carta: k });
    }));
    return m;
  }

  function pintarDiagnostico() {
    const m = violacionesPorPunto();
    const n = m.size;
    const excl = (CARTA.subgrupos || []).filter((s) => s.excluido).length;
    $("diag-n").textContent = n;
    const rojo = n > 0;
    $("diag-icono").textContent = rojo ? "warning" : "task_alt";
    $("diag-icono").className = `material-symbols-outlined text-base ${rojo ? "text-error" : "text-secondary"}`;
    $("diag-titulo").className = `font-label-sm text-label-sm font-bold ${rojo ? "text-error" : "text-secondary"}`;
    $("diag-n").className = `font-metric-display-mobile text-metric-display-mobile font-bold ${rojo ? "text-error" : "text-secondary"}`;
    $("diag-chip").textContent = rojo ? "Acción Requerida" : "Bajo Control";
    $("diag-chip").className = `px-1.5 py-0.5 rounded text-[10px] font-bold font-label-sm ${rojo ? "bg-error-container text-on-error-container" : "bg-secondary-container text-on-secondary-container"}`;
    $("diag-texto").textContent = faseVista === "I"
      ? `${rojo ? "Causas asignables en evaluación." : "Sin señales en los subgrupos incluidos."} ${excl} subgrupo(s) excluido(s).`
      : `${rojo ? "Señales en la Fase II: registre causa y acción en Alertas." : "El proceso se mantiene dentro de los límites congelados."}`;
    const pie = $("diag-pie");
    if (rojo) {
      const [i, vs] = [...m.entries()][0];
      $("diag-primero").textContent = `Subgrupo #${CARTA.etiquetas[i]}: ${vs.map((v) => v.regla).join(", ")}`;
      pie.className = "flex items-center justify-between pt-space-xs p-space-xs rounded-lg font-label-sm text-label-sm bg-error-container/30 text-on-error-container";
      $("diag-auditar").classList.remove("hidden");
      $("diag-auditar").onclick = () => enfocar(i);
    } else {
      $("diag-primero").textContent = "Sin subgrupos para auditar";
      pie.className = "flex items-center justify-between pt-space-xs p-space-xs rounded-lg font-label-sm text-label-sm bg-surface-container-low text-on-surface-variant";
      $("diag-auditar").classList.add("hidden");
    }
  }

  // ------------------------------------------------------------------ Gráficos
  function pintarGraficos() {
    const [k1, k2] = claves();
    const titulos = { xbar: "CARTA DE MEDIAS (X̄)", i: "CARTA DE INDIVIDUALES (I)", p: "CARTA p — FRACCIÓN DEFECTUOSA", np: "CARTA np — NÚMERO DE DEFECTUOSOS",
      c: "CARTA c — DEFECTOS", u: "CARTA u — DEFECTOS POR UNIDAD", r: "CARTA DE DISPERSIÓN (R)", s: "CARTA DE DISPERSIÓN (S)", mr: "CARTA DE RANGOS MÓVILES (MR)" };
    $("g1-titulo").textContent = titulos[k1];
    $("g1-sub").textContent = `Fase ${CARTA.fase} · ${V.nombre}${CARTA.n_variable ? " · límites variables (n distinto)" : ""}`;
    const op = {
      etiquetas: CARTA.etiquetas, excluidos: CARTA.excluidos, decimales: dec(), unidad: esAttr() ? "" : V.unidad,
      alHacerClic: enfocar,
      textoPunto: (i) => { const s = CARTA.subgrupos[i]; return s && s.causa_exclusion ? `<br>Causa: ${esc(s.causa_exclusion)}` : ""; },
    };
    GRAF.cartaControl($("graf-1"), CARTA.cartas[k1], { ...op, zonas: true, alto: 290, lei: esAttr() ? null : V.lei, les: esAttr() ? null : V.les });
    if (k2 && $("caja-g2")) {
      $("caja-g2").classList.remove("hidden");
      const s2 = CARTA.cartas[k2];
      $("g2-titulo").textContent = titulos[k2];
      $("g2-sub").textContent = { r: "R = X_max − X_min", s: "s = √(Σ(x−x̄)²/(n−1))", mr: "MRᵢ = |xᵢ − xᵢ₋₁|" }[k2];
      $("g2-leyenda").innerHTML = `<span class="text-error font-medium">LCS = ${f(ultimo(s2.lcs))}${u()}</span><span class="text-primary font-bold">LC = ${f(ultimo(s2.lc))}${u()}</span><span class="text-secondary font-medium">LCI = ${f(ultimo(s2.lci))}${u()}</span>`;
      GRAF.cartaControl($("graf-2"), s2, { ...op, zonas: false, alto: 190 });
    } else if ($("caja-g2")) {
      $("caja-g2").classList.add("hidden");
    }
  }

  // ------------------------------------------------------------------ Reglas
  function pintarReglas() {
    const activas = V.reglas || [];
    const conteo = {};
    const detalle = {};
    claves().forEach((k) => CARTA.cartas[k].violaciones.forEach((v) => {
      conteo[v.regla] = (conteo[v.regla] || 0) + 1;
      (detalle[v.regla] = detalle[v.regla] || []).push(CARTA.etiquetas[v.indice]);
    }));
    $("lista-reglas").innerHTML = activas.map((id) => {
      const r = CATALOGO.find((x) => x.id === id) || { condicion: id, nombre: id, severidad: "alerta" };
      const c = conteo[id] || 0;
      if (!c) {
        return `<div class="p-space-xs rounded-lg bg-surface-container-low flex items-center justify-between gap-space-xs">
          <div class="flex flex-col"><span class="font-label-sm text-label-sm font-medium text-on-surface">${id}: ${esc(r.condicion)}</span>
          <span class="font-body-sm text-body-sm text-outline">${esc(r.nombre)}: sin señales.</span></div>
          <span class="font-label-sm text-label-sm text-secondary font-bold flex items-center gap-0.5 whitespace-nowrap"><span class="material-symbols-outlined text-xs">check_circle</span> 0 OK</span></div>`;
      }
      const critica = r.severidad === "critica";
      const sgs = [...new Set(detalle[id])];
      return `<div class="p-space-xs rounded-lg ${critica ? "bg-error-container/20" : "bg-[#FEF3C7]/70"} flex flex-col gap-0.5">
        <div class="flex items-center justify-between gap-space-xs">
          <span class="font-label-sm text-label-sm font-bold ${critica ? "text-error" : "text-[#B45309]"}">${id}: ${esc(r.condicion)}</span>
          <span class="font-label-sm text-label-sm px-1.5 py-0.5 rounded ${critica ? "bg-error text-on-error" : "bg-[#B45309] text-on-error"} font-bold whitespace-nowrap">${c} ${critica ? (c > 1 ? "Violaciones" : "Violación") : (c > 1 ? "Alertas" : "Alerta")}</span>
        </div>
        <p class="font-body-sm text-body-sm text-on-surface-variant">Subgrupo(s) #${sgs.slice(0, 8).join(", #")}${sgs.length > 8 ? "…" : ""}.</p></div>`;
    }).join("") || '<p class="font-body-sm text-body-sm text-outline">No hay reglas activas.</p>';
    const iguales = (a, b) => a.length === b.length && a.every((x) => b.includes(x));
    const presets = CEP.ctx.presets;
    const modo = iguales(activas, presets.western_electric) ? "western_electric" : iguales(activas, presets.nelson) ? "nelson" : null;
    $("reglas-modo").textContent = modo === "western_electric" ? "Western Electric Activo" : modo === "nelson" ? "Nelson Activo" : `Personalizado (${activas.length})`;
    document.querySelectorAll("[data-preset]").forEach((b) => {
      b.className = `px-2 py-1 font-label-sm text-label-sm rounded ${b.dataset.preset === modo ? "bg-surface-container-lowest text-primary font-bold shadow-sm" : "text-on-surface-variant hover:text-primary"}`;
    });
    $("alfa-falsa").textContent = `${pct(2 * Phi(-V.k_sigma), 2)} (${fmt(V.k_sigma, 2)}σ)`;
  }

  async function cambiarPreset(preset) {
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    const r = await CEP.modal({
      titulo: `Activar reglas ${preset === "nelson" ? "Nelson (8)" : "Western Electric (4)"}`,
      texto: "El cambio queda registrado en el historial de configuración.",
      campos: [{ nombre: "justificacion", etiqueta: "Justificación", tipo: "textarea", requerido: true }],
    });
    if (!r) return;
    try {
      const res = await api(`/variables/${V.id}`, { method: "PATCH", json: { reglas: CEP.ctx.presets[preset], usuario, justificacion: r.justificacion } });
      V = { ...V, ...res.variable };
      toast("Reglas actualizadas.");
      await cargar();
    } catch (e) { toast(e.message, "error"); }
  }

  async function cambiarTipo(tipo) {
    if (tipo === V.tipo_carta) return;
    if (V.fase === "II") return toast("Con límites congelados no se cambia el tipo de carta: vuelva primero a la Fase I.", "aviso");
    if ((tipo === "imr") !== (V.tipo_carta === "imr") && (CARTA.subgrupos || []).length) {
      return toast("No se puede pasar entre subgrupos (n > 1) e individuales (n = 1) con datos cargados. Cree otra variable.", "aviso");
    }
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    const r = await CEP.modal({
      titulo: `Cambiar a carta ${CEP.NOMBRES_CARTA[tipo]}`,
      campos: [{ nombre: "justificacion", etiqueta: "Justificación", tipo: "textarea", requerido: true }],
    });
    if (!r) return;
    try {
      const cuerpo = { tipo_carta: tipo, usuario, justificacion: r.justificacion };
      if (tipo === "xbar_s") cuerpo.estimador_sigma = "sbar";
      if (tipo === "xbar_r") cuerpo.estimador_sigma = "rbar";
      await api(`/variables/${V.id}`, { method: "PATCH", json: cuerpo });
      location.reload();
    } catch (e) { toast(e.message, "error"); }
  }

  // ------------------------------------------------------------------ Capacidad
  function pintarCapacidad() {
    if (!$("cap-cp")) return;
    if (!CAP) {
      ["cap-cp", "cap-cpk", "cap-lados", "cap-nc"].forEach((id) => ($(id).textContent = "—"));
      $("cap-cp-t").textContent = esAttr() ? "No aplica" : (V.lei === null && V.les === null) ? "Defina LEI/LES" : "Sin datos suficientes";
      ["cap-k", "cap-sg", "cap-ppm"].forEach((id) => ($(id).textContent = ""));
      return;
    }
    const c = CAP.indices;
    $("cap-cp").textContent = c.cp === null ? "—" : fmt(c.cp, 2);
    $("cap-cp-t").textContent = c.cp === null ? "Unilateral" : c.cp >= 1.33 ? "Adecuado (≥ 1.33)" : "Insuficiente";
    $("cap-cpk").textContent = fmt(c.cpk, 2);
    $("cap-cpk").className = `font-metric-display-mobile text-metric-display-mobile font-bold ${c.cpk >= 1.33 ? "text-secondary" : c.cpk >= 1 ? "text-[#B45309]" : "text-error"}`;
    $("cap-k").textContent = CAP.k_descentrado === null ? "" : `Descentrado k = ${fmt(CAP.k_descentrado, 2)}`;
    $("cap-lados").textContent = `${c.cpu === null ? "—" : fmt(c.cpu, 2)} / ${c.cpl === null ? "—" : fmt(c.cpl, 2)}`;
    $("cap-sg").textContent = `σ = ${fmt(CAP.sigma_dentro, dec())}${u()}${CAP.metodo_sigma === "fijada" ? " (fijada)" : ""}`;
    $("cap-nc").textContent = CEP.pct(CAP.ppm_esperado.total, CAP.ppm_esperado.total < 0.001 ? 4 : 2);
    $("cap-ppm").textContent = `${fmt(CAP.ppm_esperado.ppm, 1)} ppm esperadas`;
  }

  // ------------------------------------------------------------------ Tabla de depuración
  function columnasFila(i) {
    const s = CARTA.subgrupos[i];
    if (esAttr()) {
      const k = claves()[0];
      return [fmt(s.conteo, 0), V.tipo_carta === "c" ? "—" : fmt(s.tamano, 0), f(CARTA.cartas[k].valores[i])];
    }
    const [k1, k2] = claves();
    return [`${f(CARTA.cartas[k1].valores[i])}${u()}`, k2 && CARTA.cartas[k2].valores[i] !== null ? `${f(CARTA.cartas[k2].valores[i])}${u()}` : "—"];
  }

  function filasVisibles() {
    const m = violacionesPorPunto();
    let idx = CARTA.subgrupos.map((_, i) => i);
    if ($("solo-senales").checked) idx = idx.filter((i) => m.has(i) || CARTA.subgrupos[i].excluido || pendientes.has(CARTA.subgrupos[i].numero));
    return { idx, m };
  }

  function pintarTabla() {
    const { idx, m } = filasVisibles();
    const paginas = Math.max(1, Math.ceil(idx.length / POR_PAGINA));
    pagina = Math.min(pagina, paginas);
    const visibles = idx.slice((pagina - 1) * POR_PAGINA, pagina * POR_PAGINA);
    const editable = faseVista === "I" && V.fase === "I";
    $("dep-titulo").textContent = faseVista === "I" ? "Depuración de Subgrupos & Causas Asignables" : "Señales de Fase II & Seguimiento de Alarmas";
    $("dep-texto").textContent = faseVista === "I"
      ? (V.fase === "I" ? "Los subgrupos con causas atribuibles comprobadas deben ser excluidos del recálculo basal para evitar inflación artificial de los límites de control."
        : "Base de la Fase I con la que se congelaron los límites (solo lectura). Para modificarla, vuelva a la Fase I.")
      : "Subgrupos monitoreados contra los límites congelados. La causa y la acción se registran desde la alarma (vista Operario o Alertas).";
    $("dep-simulador").classList.toggle("hidden", !editable);

    $("tabla-subgrupos").innerHTML = visibles.map((i) => {
      const s = CARTA.subgrupos[i];
      const vs = m.get(i) || [];
      const marcado = pendientes.has(s.numero);
      const alarmas = ALARMAS_SG[s.id] || [];
      const alarma = alarmas[0];
      const causa = s.causa_exclusion || (alarma && alarma.causa) || (vs.length ? '<span class="text-outline">Pendiente de análisis</span>' : '<span class="text-outline">Sin causa asignable (variación común).</span>');
      const accion = s.accion_exclusion || (alarma && alarma.accion) || '<span class="text-outline">—</span>';
      let estado;
      if (s.excluido) estado = '<span class="inline-flex items-center gap-1 font-label-sm text-label-sm font-semibold text-on-secondary-container bg-secondary-container px-2 py-0.5 rounded"><span class="material-symbols-outlined text-xs">verified</span> Causa Válida (excluido)</span>';
      else if (alarma && alarma.estado === "resuelta") estado = '<span class="inline-flex items-center gap-1 font-label-sm text-label-sm font-semibold text-on-secondary-container bg-secondary-container px-2 py-0.5 rounded"><span class="material-symbols-outlined text-xs">check_circle</span> Resuelta</span>';
      else if (vs.length) estado = '<span class="inline-flex items-center gap-1 font-label-sm text-label-sm font-semibold text-[#B45309] bg-[#FEF3C7] px-2 py-0.5 rounded"><span class="material-symbols-outlined text-xs">hourglass_empty</span> En Investigación</span>';
      else estado = '<span class="inline-flex items-center gap-1 font-label-sm text-label-sm font-medium text-secondary bg-surface-container px-2 py-0.5 rounded">Estable</span>';
      const reglas = vs.length
        ? [...new Set(vs.map((v) => v.regla))].map((r) => `<span class="inline-flex items-center gap-1 font-label-sm text-label-sm font-bold text-error bg-error-container px-2 py-0.5 rounded mr-1"><span class="material-symbols-outlined text-xs">priority_high</span>${r}</span>`).join("")
        : '<span class="font-label-sm text-label-sm text-secondary font-medium">Bajo Control</span>';
      const fondo = seleccionado === i ? "bg-secondary-container/40" : vs.length ? "bg-error-container/10 hover:bg-error-container/20" : "hover:bg-surface-container-low";
      return `<tr class="${fondo} transition-colors ${s.excluido ? "opacity-80" : ""}" id="fila-${i}">
        <td class="py-2 px-space-sm text-center"><input class="w-4 h-4 rounded text-primary focus:ring-primary cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed" data-numero="${s.numero}" type="checkbox" ${marcado ? "checked" : ""} ${editable ? "" : "disabled"}/></td>
        <td class="py-2 px-space-sm font-label-md text-label-md font-bold text-primary">#${s.numero}</td>
        ${columnasFila(i).map((c) => `<td class="py-2 px-space-sm font-label-md text-label-md text-right ${vs.length ? "text-error font-bold" : "text-on-surface"}">${c}</td>`).join("")}
        <td class="py-2 px-space-sm">${reglas}</td>
        <td class="py-2 px-space-sm font-body-sm text-body-sm text-on-surface">${typeof causa === "string" && causa.startsWith("<") ? causa : esc(causa)}</td>
        <td class="py-2 px-space-sm font-body-sm text-body-sm text-on-surface-variant">${typeof accion === "string" && accion.startsWith("<") ? accion : esc(accion)}</td>
        <td class="py-2 px-space-sm">${estado}</td></tr>`;
    }).join("") || '<tr><td colspan="9" class="py-space-md text-center text-outline">Sin subgrupos para mostrar.</td></tr>';
    $("tabla-subgrupos").querySelectorAll("input[data-numero]").forEach((cb) => (cb.onchange = () => {
      const n = +cb.dataset.numero;
      if (cb.checked) pendientes.add(n); else pendientes.delete(n);
      simular();
    }));
    $("pag-resumen").textContent = `Mostrando ${visibles.length} de ${idx.length} subgrupos`;
    $("pag-num").textContent = `${pagina} / ${paginas}`;
    $("pag-ant").disabled = pagina <= 1;
    $("pag-sig").disabled = pagina >= paginas;
  }

  function enfocar(i) {
    seleccionado = i;
    const { idx } = filasVisibles();
    let pos = idx.indexOf(i);
    if (pos < 0) { $("solo-senales").checked = false; pos = i; }
    pagina = Math.floor(pos / POR_PAGINA) + 1;
    pintarTabla();
    $("pag-seleccion").textContent = `Subgrupo seleccionado: #${CARTA.etiquetas[i]}`;
    const fila = $(`fila-${i}`);
    if (fila) fila.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // ------------------------------------------------------------------ Simulación y recálculo
  const guardados = () => new Set(CARTA.subgrupos.filter((s) => s.excluido).map((s) => s.numero));
  const hayCambios = () => { const g = guardados(); return g.size !== pendientes.size || [...g].some((n) => !pendientes.has(n)); };

  async function simular() {
    $("btn-apply-recalc").disabled = !hayCambios();
    if (!hayCambios()) return pintarSimulacion(null);
    try {
      pintarSimulacion(await api(`/variables/${V.id}/simular-exclusion`, { json: { excluidos: [...pendientes] } }));
    } catch (e) {
      $("sim-resultado").innerHTML = `<span class="text-error">${esc(e.message)}</span>`;
    }
  }

  function pintarSimulacion(r) {
    if (!r) {
      $("sim-resultado").innerHTML = '<span class="text-outline">Marque subgrupos para ver el impacto</span>';
      $("btn-apply-recalc").disabled = true;
      return;
    }
    const d = r.delta;
    const signo = (x) => (x > 0 ? "+" : "");
    let html = `<span class="text-error font-bold">Δ LCS: ${signo(d.lcs)}${f(d.lcs)}${u()}</span><span class="text-outline">|</span>
      <span class="text-primary font-bold">Δ LC: ${signo(d.lc)}${f(d.lc)}</span>`;
    if (r.cpk_antes !== undefined) html += `<span class="text-outline">|</span><span class="text-secondary font-bold">Cpk: ${fmt(r.cpk_antes, 2)} → ${fmt(r.cpk_despues, 2)}</span>`;
    html += `<span class="text-outline">|</span><span class="${r.senales_despues.length ? "text-error" : "text-secondary"} font-bold">${r.senales_despues.length ? "Quedan señales: #" + r.senales_despues.join(", #") : "Sin señales restantes"}</span>`;
    $("sim-resultado").innerHTML = html;
  }

  async function aplicarRecalculo() {
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    const g = guardados();
    const nuevos = [...pendientes].filter((n) => !g.has(n));
    const quitar = [...g].filter((n) => !pendientes.has(n));
    const porNumero = Object.fromEntries(CARTA.subgrupos.map((s) => [s.numero, s]));
    try {
      for (const n of nuevos) {
        const r = await CEP.modal({
          titulo: `Excluir subgrupo #${n}`,
          texto: "Solo se excluyen subgrupos con una causa asignable identificada. Queda registrado en el historial.",
          campos: [{ nombre: "causa", etiqueta: "Causa asignable identificada", tipo: "textarea", requerido: true },
                   { nombre: "accion", etiqueta: "Acción correctiva de piso", tipo: "textarea" }],
          aceptar: "Excluir y continuar",
        });
        if (!r) { toast("Recálculo cancelado.", "aviso"); break; }
        await api(`/subgrupos/${porNumero[n].id}`, { method: "PATCH", json: { excluido: true, causa: r.causa, accion: r.accion, usuario } });
      }
      for (const n of quitar) await api(`/subgrupos/${porNumero[n].id}`, { method: "PATCH", json: { excluido: false, usuario } });
      toast("Límites recalculados con la base depurada.");
    } catch (e) { toast(e.message, "error"); }
    await cargar();
  }

  // ------------------------------------------------------------------ Fases
  async function accionFase() {
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    if (V.fase === "I") {
      const senales = violacionesPorPunto().size;
      const r = await CEP.modal({
        titulo: "Congelar límites y pasar a Fase II",
        texto: `Se congelarán los límites estimados con ${CARTA.limites ? CARTA.limites.m_usados : "—"} subgrupos.` + (senales ? ` <b class="text-error">Atención: quedan ${senales} punto(s) con señal sin excluir.</b>` : ""),
        campos: [{ nombre: "motivo", etiqueta: "Motivo / observaciones", tipo: "textarea", valor: "Base estable tras depuración de causas asignables" }],
        aceptar: "Congelar límites",
      });
      if (!r) return;
      try {
        const res = await api(`/variables/${V.id}/congelar`, { json: { usuario, motivo: r.motivo } });
        res.advertencias.forEach((a) => toast(a, "aviso"));
        toast("Límites congelados: la variable pasa a Fase II.");
        setTimeout(() => location.reload(), 800);
      } catch (e) { toast(e.message, "error"); }
    } else {
      const r = await CEP.modal({
        titulo: "Volver a Fase I",
        texto: "Los límites congelados se archivan en el historial. Use esta opción cuando el proceso cambió de forma permanente.",
        campos: [{ nombre: "motivo", etiqueta: "Motivo (obligatorio)", tipo: "textarea", requerido: true },
                 { nombre: "base", etiqueta: "Nueva base de Fase I", tipo: "select", valor: "no",
                   opciones: [["no", "Conservar la base anterior (los datos de Fase II se archivan)"], ["si", "Usar los subgrupos de Fase II como nueva base"]] }],
        aceptar: "Volver a Fase I", peligro: true,
      });
      if (!r) return;
      try {
        await api(`/variables/${V.id}/volver-fase-i`, { json: { usuario, motivo: r.motivo, usar_fase_ii_como_base: r.base === "si" } });
        toast("La variable volvió a la Fase I.");
        setTimeout(() => location.reload(), 800);
      } catch (e) { toast(e.message, "error"); }
    }
  }

  // ------------------------------------------------------------------ Inicio
  async function iniciar(ctx) {
    V = ctx.variable;
    if (!V) return;
    if (MODO === "variables" && esAttr()) {
      return CEP.avisoPantalla($("pantalla"), "Esta variable usa una carta por atributos",
        `«${esc(V.nombre)}» se controla con una carta ${CEP.NOMBRES_CARTA[V.tipo_carta]}.`, [CEP.conVariable("/ingenieria/atributos", V.id), "Ir a Gráficos por Atributos"]);
    }
    if (MODO === "atributos" && !esAttr()) {
      return CEP.avisoPantalla($("pantalla"), "Esta variable es de tipo continuo",
        `«${esc(V.nombre)}» se controla con una carta ${CEP.NOMBRES_CARTA[V.tipo_carta]}. El asistente de atributos sigue disponible abajo para variables p, np, c o u.`,
        [CEP.conVariable("/ingenieria/variables", V.id), "Ir a Gráficos por Variables"]);
    }
    const reglas = await api("/reglas");
    CATALOGO = reglas.catalogo;
    ctx.presets = reglas.presets;
    faseVista = V.fase;
    $("btn-fase-1").onclick = () => { faseVista = "I"; cargar(); };
    $("btn-fase-2").onclick = () => { if (V.fase === "II") { faseVista = "II"; cargar(); } else toast("Primero congele los límites de la Fase I.", "aviso"); };
    $("btn-fase-accion").onclick = accionFase;
    document.querySelectorAll("#selector-carta [data-tipo]").forEach((b) => (b.onclick = () => cambiarTipo(b.dataset.tipo)));
    document.querySelectorAll("[data-preset]").forEach((b) => (b.onclick = () => cambiarPreset(b.dataset.preset)));
    $("btn-apply-recalc").onclick = aplicarRecalculo;
    $("solo-senales").onchange = () => { pagina = 1; pintarTabla(); };
    $("pag-ant").onclick = () => { pagina--; pintarTabla(); };
    $("pag-sig").onclick = () => { pagina++; pintarTabla(); };
    $("btn-png").onclick = () => {
      ["graf-1", "graf-2"].forEach((id, i) => {
        const el = $(id);
        if (el && el.data) Plotly.downloadImage(el, { format: "png", width: 1400, height: i ? 380 : 560, filename: `carta_${V.tipo_carta}_${id}_fase${faseVista}` });
      });
    };
    await cargar();
  }

  CEP.arrancar(iniciar);
})();
