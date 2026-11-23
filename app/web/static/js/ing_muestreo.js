/* =========================================================================
 * ing_muestreo.js — Módulo 7: plan simple (N, n, c), curvas OC (binomial / hipergeométrica /
 * Poisson), AOQ/AOQL, ATI, diseño del plan, dictamen del lote e historial.
 * API: /muestreo/curvas, /muestreo/disenar, /muestreo/decidir, /muestreo/lotes
 * ========================================================================= */
(function () {
  "use strict";
  const { api, fmt, pct, esc, toast, fechaHora } = CEP;
  const $ = (id) => document.getElementById(id);
  let C = null, temporizador = null;

  const par = () => ({
    N: Math.round(+$("p-N").value), n: Math.round(+$("p-n").value), c: Math.round(+$("p-c").value),
    aql: +$("p-aql").value / 100, ltpd: +$("p-ltpd").value / 100,
  });
  const nombres = { binomial: "Binomial (tipo B)", hipergeometrica: "Hipergeométrica (tipo A)", poisson: "Poisson" };

  /** Valor de una curva en p por interpolación lineal sobre la grilla del servidor. */
  function interp(xs, ys, x) {
    for (let i = 1; i < xs.length; i++) if (x <= xs[i]) return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
    return ys[ys.length - 1];
  }

  async function calcular() {
    const p = par();
    if (!(p.n >= 1 && p.c >= 0 && p.N >= p.n && p.c < p.n)) {
      $("oc-pie").textContent = "Revise los parámetros: debe cumplirse 0 ≤ c < n ≤ N.";
      return;
    }
    try {
      C = await api(`/muestreo/curvas?${new URLSearchParams({ n: p.n, c: p.c, N: p.N, aql: p.aql, ltpd: p.ltpd, puntos: 201 })}`);
    } catch (e) { toast(e.message, "error"); return; }

    $("p-N-sub").textContent = `Muestra = ${pct(p.n / p.N, 2)} del lote`;
    $("p-n-sub").textContent = `Re = ${p.c + 1} (rechazo)`;
    $("p-c-sub").textContent = `Ac = ${p.c}`;
    $("p-aql-sub").textContent = `Pₐ @ AQL: ${pct(C.en_aql.pa, 1)} (α = ${pct(C.en_aql.alfa_real, 1)})`;
    $("p-ltpd-sub").textContent = `Pₐ @ LTPD: ${pct(C.en_ltpd.pa, 1)} (β = ${pct(C.en_ltpd.beta_real, 1)})`;
    $("p-aql-sub").className = `font-label-sm text-label-sm ${C.en_aql.alfa_real <= +$("p-alfa").value ? "text-secondary" : "text-[#B45309]"}`;
    $("p-ltpd-sub").className = `font-label-sm text-label-sm ${C.en_ltpd.beta_real <= +$("p-beta").value ? "text-secondary" : "text-[#B45309]"}`;

    // Curva OC
    const activos = [...document.querySelectorAll("[data-modelo]")].filter((x) => x.checked).map((x) => x.dataset.modelo);
    const series = activos.filter((m) => C.oc[m]).map((m) => ({ nombre: nombres[m], x: C.p, y: C.oc[m], guion: m === "poisson" ? "dot" : m === "hipergeometrica" ? "dash" : "solid" }));
    GRAF.curvas($("graf-oc"), series, {
      alto: 360, tituloX: "Fracción defectuosa del lote p", tituloY: "Probabilidad de aceptación Pₐ", tickX: ".1%", tickY: ".0%",
      etiquetaX: "p", etiquetaY: "Pₐ", formatoX: ":.2%", formatoY: ":.4f",
      refs: [{ x: p.aql, color: "#086a5f" }, { x: p.ltpd, color: "#ba1a1a" }],
      puntos: [{ x: p.aql, y: C.en_aql.pa, texto: ` AQL ${pct(p.aql, 2)} · Pₐ ${fmt(C.en_aql.pa, 3)}`, color: "#086a5f" },
               { x: p.ltpd, y: C.en_ltpd.pa, texto: ` LTPD ${pct(p.ltpd, 2)} · Pₐ ${fmt(C.en_ltpd.pa, 3)}`, color: "#ba1a1a" }],
    });
    $("oc-pie").textContent = `Binomial: Pₐ = Σ_{d≤${p.c}} C(${p.n},d)·pᵈ(1−p)^(${p.n}−d) · Hipergeométrica con N = ${p.N}`;
    $("oc-p50").textContent = `Punto de indiferencia p₅₀ = ${pct(C.p50, 2)}`;

    // AOQ y ATI
    GRAF.curvas($("graf-aoq"), [{ nombre: "AOQ", x: C.p, y: C.aoq, color: "#0f4c5c" }], {
      alto: 170, tickX: ".0%", tickY: ".2%", etiquetaX: "p", etiquetaY: "AOQ", formatoX: ":.2%", formatoY: ":.3%",
      refs: [{ y: C.aoql.valor, color: "#ba1a1a" }], puntos: [{ x: C.aoql.p, y: C.aoql.valor, texto: ` AOQL ${pct(C.aoql.valor, 2)}`, color: "#ba1a1a" }],
    });
    $("aoql-chip").textContent = `AOQL: ${pct(C.aoql.valor, 3)}`;
    GRAF.curvas($("graf-ati"), [{ nombre: "ATI", x: C.p, y: C.ati, color: "#0f4c5c" }], {
      alto: 170, tickX: ".0%", etiquetaX: "p", etiquetaY: "ATI", formatoX: ":.2%", formatoY: ":,.0f", refs: [{ y: p.N, color: "#70787c" }],
    });
    $("ati-chip").textContent = `ATI @ AQL: ${fmt(interp(C.p, C.ati, p.aql), 0)}`;

    // Tabla de riesgos
    const puntos = [["AQL", p.aql], ["p₅₀", C.p50], ["AOQL", C.aoql.p], ["LTPD", p.ltpd]];
    $("tabla-riesgos").innerHTML = puntos.map(([t, x]) => `<tr><td class="py-1.5 px-space-xs font-bold">${t}</td><td class="py-1.5 px-space-xs text-right">${pct(x, 2)}</td>
      <td class="py-1.5 px-space-xs text-right">${fmt(interp(C.p, C.oc.binomial, x), 4)}</td><td class="py-1.5 px-space-xs text-right">${fmt(interp(C.p, C.oc.hipergeometrica, x), 4)}</td>
      <td class="py-1.5 px-space-xs text-right">${pct(interp(C.p, C.aoq, x), 3)}</td><td class="py-1.5 px-space-xs text-right">${fmt(interp(C.p, C.ati, x), 0)}</td></tr>`).join("");
    $("conclusiones").innerHTML = C.conclusiones.map((c) => `<li class="flex items-start gap-space-xs font-body-sm text-body-sm">
      <span class="material-symbols-outlined text-base ${c.nivel === "ok" ? "text-secondary" : "text-[#B45309]"}">${c.nivel === "ok" ? "check_circle" : "warning"}</span>${esc(c.texto)}</li>`).join("");
    await decidir();
  }

  async function decidir() {
    const p = par();
    const d = Math.max(0, Math.min(p.n, Math.round(+$("dec-d").value)));
    $("dec-d").value = d;
    $("dec-n").textContent = p.n;
    $("dec-limites").textContent = `Límites: Ac = ${p.c} | Re = ${p.c + 1}`;
    try {
      const r = await api(`/muestreo/decidir?${new URLSearchParams({ d, n: p.n, c: p.c })}`);
      const ok = r.aceptado;
      $("dec-veredicto").className = `p-space-sm rounded-lg flex flex-col gap-1 ${ok ? "bg-secondary-container/50 text-on-secondary-container" : "bg-error-container text-on-error-container"}`;
      $("dec-titulo").innerHTML = `<span class="material-symbols-outlined">${ok ? "check_circle" : "cancel"}</span>LOTE ${r.dictamen}`;
      $("dec-condicion").textContent = `Condición: ${r.condicion}`;
      $("dec-p").textContent = pct(r.p_hat, 2);
      $("dec-ic").textContent = `[${pct(r.ic95[0], 2)}, ${pct(r.ic95[1], 2)}]`;
      $("dec-pa").textContent = C ? fmt(interp(C.p, C.oc.binomial, r.p_hat), 4) : "—";
      $("dec-destino").textContent = ok ? "Aprobado a planta" : "Rechazo / inspección 100 %";
    } catch (e) { toast(e.message, "error"); }
  }

  async function disenar() {
    const p = par();
    try {
      const r = await api("/muestreo/disenar", { json: { aql: p.aql, ltpd: p.ltpd, alfa: +$("p-alfa").value, beta: +$("p-beta").value, N: p.N, modelo: "binomial" } });
      $("p-n").value = r.n;
      $("p-c").value = r.c;
      toast(`Plan diseñado: n = ${r.n}, c = ${r.c} (α real ${pct(r.alfa_real, 1)}, β real ${pct(r.beta_real, 1)}).`);
      await calcular();
    } catch (e) { toast(e.message, "error"); }
  }

  async function cargarLotes() {
    const r = await api("/muestreo/lotes");
    $("hist-resumen").textContent = r.lotes.length ? `Tasa de aceptación histórica: ${pct(r.tasa_aceptacion, 1)} · ${r.lotes.length} lote(s)` : "Sin lotes registrados";
    $("tabla-lotes").innerHTML = r.lotes.map((l) => `<tr class="hover:bg-surface-container-low">
      <td class="py-2 px-space-sm font-label-md text-label-md font-bold text-primary">${esc(l.codigo)}<span class="block font-body-sm text-body-sm text-outline font-normal">${esc(l.descripcion || "")}</span></td>
      <td class="py-2 px-space-sm font-label-sm text-label-sm">${fechaHora(l.fecha)}</td>
      <td class="py-2 px-space-sm text-right font-label-md">${fmt(l.N, 0)}</td><td class="py-2 px-space-sm text-right font-label-md">${l.n}</td>
      <td class="py-2 px-space-sm text-right font-label-md">${l.c}</td><td class="py-2 px-space-sm text-right font-label-md">${l.defectos}</td>
      <td class="py-2 px-space-sm text-right font-label-md">${pct(l.p_hat, 2)}</td>
      <td class="py-2 px-space-sm"><span class="px-2 py-0.5 rounded font-label-sm text-label-sm font-bold ${l.dictamen === "ACEPTADO" ? "bg-secondary-container text-on-secondary-container" : "bg-error-container text-on-error-container"}">${l.dictamen}</span></td>
      <td class="py-2 px-space-sm font-body-sm text-body-sm">${esc(l.usuario || "—")}</td></tr>`).join("")
      || '<tr><td class="py-space-md px-space-sm text-outline" colspan="9">Registre el dictamen de un lote para iniciar el historial.</td></tr>';
  }

  async function registrarLote() {
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    const p = par();
    try {
      const r = await api("/muestreo/lotes", { json: { codigo: $("lote-codigo").value || "SIN-CODIGO", descripcion: $("lote-desc").value,
        N: p.N, n: p.n, c: p.c, defectos: +$("dec-d").value, usuario } });
      toast(`Lote ${r.codigo}: ${r.dictamen}.`, r.dictamen === "ACEPTADO" ? "ok" : "aviso");
      await cargarLotes();
    } catch (e) { toast(e.message, "error"); }
  }

  function exportarCSV() {
    if (!C) return;
    const filas = [["p", "Pa_binomial", "Pa_hipergeometrica", "Pa_poisson", "AOQ", "ATI"]];
    C.p.forEach((x, i) => filas.push([x, C.oc.binomial[i], C.oc.hipergeometrica[i], C.oc.poisson[i], C.aoq[i], C.ati[i]].map((v) => (+v).toFixed(6))));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([filas.map((f) => f.join(",")).join("\n")], { type: "text/csv" }));
    a.download = `curvas_plan_n${C.n}_c${C.c}.csv`;
    a.click();
  }

  function programar() { clearTimeout(temporizador); temporizador = setTimeout(calcular, 300); }

  async function iniciar() {
    ["p-N", "p-n", "p-c", "p-aql", "p-ltpd", "p-alfa", "p-beta"].forEach((id) => $(id).addEventListener("input", programar));
    document.querySelectorAll("[data-modelo]").forEach((x) => (x.onchange = calcular));
    $("dec-d").addEventListener("input", decidir);
    $("btn-inc").onclick = () => { $("dec-d").value = +$("dec-d").value + 1; decidir(); };
    $("btn-dec").onclick = () => { $("dec-d").value = Math.max(0, +$("dec-d").value - 1); decidir(); };
    $("btn-disenar").onclick = disenar;
    $("btn-registrar-lote").onclick = registrarLote;
    $("btn-csv").onclick = exportarCSV;
    await calcular();
    await cargarLotes();
  }

  CEP.arrancar(iniciar);
})();
