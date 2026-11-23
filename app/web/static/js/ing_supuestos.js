/* =========================================================================
 * ing_supuestos.js — Módulo 4: normalidad (SW, AD, Lilliefors, forma, Q-Q), independencia
 * (ACF, Ljung-Box, Durbin-Watson), rachas/tendencia y Box-Cox.  API: /variables/{id}/supuestos
 * ========================================================================= */
(function () {
  "use strict";
  const { api, fmt, esc } = CEP;
  const $ = (id) => document.getElementById(id);
  let V;

  const OK = { fondo: "bg-secondary-container/40", chip: "bg-secondary-container text-on-secondary-container", icono: "verified", color: "text-secondary" };
  const MAL = { fondo: "bg-[#FEF3C7]", chip: "bg-[#B45309] text-on-error", icono: "warning", color: "text-[#B45309]" };

  function tarjeta(sub, nombre, simbolo, est, p, rechaza, pie) {
    const e = rechaza ? MAL : OK;
    return `<div class="bg-surface-container-lowest p-space-md rounded-xl shadow-sm flex flex-col gap-space-xs">
      <div class="flex items-center justify-between"><span class="font-label-sm text-label-sm text-outline">${sub}</span>
        <span class="px-space-xs py-0.5 rounded ${e.chip} font-label-sm text-label-sm font-bold">${rechaza ? "Rechaza H0" : "Conforme"}</span></div>
      <span class="font-label-lg text-label-lg font-bold text-on-surface">${nombre}</span>
      <div class="flex items-baseline gap-1"><span class="font-label-md text-label-md text-outline">${simbolo} =</span>
        <span class="font-metric-display-mobile text-metric-display-mobile font-bold text-primary">${est}</span></div>
      <div class="flex items-center justify-between font-label-sm text-label-sm"><span>p-valor: <strong class="${e.color}">${p}</strong></span>
        <span class="text-outline">${pie}</span></div></div>`;
  }

  async function cargar() {
    const q = new URLSearchParams({ alfa: $("sel-alfa").value });
    if ($("sel-fase").value) q.set("fase", $("sel-fase").value);
    $("pantalla").classList.add("cargando");
    let d;
    try { d = await api(`/variables/${V.id}/supuestos?${q}`); } finally { $("pantalla").classList.remove("cargando"); }
    const n = d.normalidad, ind = d.independencia, rch = d.rachas, alfa = n.alfa;
    const pr = n.pruebas, pf = (x) => (x < 0.001 ? "< 0.001" : fmt(x, 3));

    $("ctx-variable").textContent = `${V.nombre} (${V.unidad})`;
    $("ctx-N").textContent = `N = ${d.N}`;
    $("ctx-k").textContent = `k = ${d.k_subgrupos}${V.tipo_carta === "imr" ? "" : ` (n = ${V.n})`}`;
    $("ctx-alfa").textContent = `α = ${alfa}`;

    // Veredicto
    const apto = d.apto_shewhart;
    $("veredicto").className = `p-space-md rounded-xl shadow-sm flex flex-col md:flex-row md:items-center gap-space-md ${apto ? "bg-secondary-container/50" : "bg-[#FEF3C7]"}`;
    $("ver-icono").textContent = apto ? "verified" : "warning";
    $("ver-icono").className = `material-symbols-outlined text-4xl ${apto ? "text-secondary" : "text-[#B45309]"}`;
    $("ver-titulo").textContent = apto ? "Supuestos validados: distribución normal y observaciones independientes" : `Supuestos con observaciones: ${d.problemas.join(", ")}`;
    $("ver-titulo").className = `font-headline-sm text-label-lg font-bold ${apto ? "text-on-secondary-container" : "text-[#B45309]"}`;
    $("ver-chip").textContent = apto ? "Apto para cartas Shewhart" : "Revisar antes de usar límites 3σ";
    $("ver-chip").className = `px-space-xs py-0.5 rounded font-label-sm text-label-sm font-bold ${apto ? OK.chip : MAL.chip}`;
    $("ver-texto").textContent = apto
      ? "Los datos no muestran evidencia contra la normalidad ni contra la independencia temporal: las tasas de falsa alarma de los límites ±3σ y los índices Cp/Cpk son válidos."
      : "Algún supuesto no se cumple: la tasa real de falsas alarmas puede diferir del 0.27 % nominal y los índices de capacidad pueden estar sesgados.";
    $("ver-cifras").innerHTML = `<span>Normalidad (AD): p = ${pf(pr.anderson_darling.p_valor)}</span><span>DW: d = ${fmt(ind.durbin_watson.d, 3)}</span><span>Lag 1: ${fmt(ind.acf.r[0], 3)}</span>`;

    // Tarjetas de pruebas
    const f = n.forma;
    const formaOk = Math.abs(f.asimetria) < 2 * f.ee_asimetria && Math.abs(f.curtosis_exceso) < 2 * f.ee_curtosis;
    $("tarjetas-pruebas").innerHTML = [
      tarjeta("Prueba principal", "Anderson-Darling", "A²", fmt(pr.anderson_darling.estadistico, 3), pf(pr.anderson_darling.p_valor), pr.anderson_darling.rechaza_h0, "H0: normal"),
      tarjeta("Prueba de contraste", "Shapiro-Wilk", "W", fmt(pr.shapiro_wilk.estadistico, 4), pf(pr.shapiro_wilk.p_valor), pr.shapiro_wilk.rechaza_h0, "H0: normal"),
      tarjeta("Lilliefors corregido", "Kolmogorov-Smirnov", "D", fmt(pr.lilliefors.estadistico, 4), pf(pr.lilliefors.p_valor), pr.lilliefors.rechaza_h0, "μ, σ estimadas"),
      tarjeta(`Independencia (k = ${ind.ljung_box.rezago})`, "Ljung-Box", "Q", fmt(ind.ljung_box.Q, 2), pf(ind.ljung_box.p_valor), ind.ljung_box.rechaza_h0, "H0: ruido blanco"),
      `<div class="bg-surface-container-lowest p-space-md rounded-xl shadow-sm flex flex-col gap-space-xs">
        <div class="flex items-center justify-between"><span class="font-label-sm text-label-sm text-outline">Parámetros de forma</span>
          <span class="px-space-xs py-0.5 rounded ${formaOk ? OK.chip : MAL.chip} font-label-sm text-label-sm font-bold">${formaOk ? "Simétrica" : "Asimétrica"}</span></div>
        <div class="flex items-baseline justify-between"><span class="font-label-md text-label-md">Asimetría:</span><span class="font-label-lg text-label-lg font-bold text-primary">${fmt(f.asimetria, 3)} <span class="font-label-sm text-label-sm text-outline">(±${fmt(2 * f.ee_asimetria, 2)})</span></span></div>
        <div class="flex items-baseline justify-between"><span class="font-label-md text-label-md">Curtosis (exceso):</span><span class="font-label-lg text-label-lg font-bold text-primary">${fmt(f.curtosis_exceso, 3)} <span class="font-label-sm text-label-sm text-outline">(±${fmt(2 * f.ee_curtosis, 2)})</span></span></div>
        <span class="font-label-sm text-label-sm text-outline">Banda ±2·EE (EE ≈ √(6/N), √(24/N))</span></div>`,
    ].join("");

    // Q-Q e histograma
    const qq = d.qq;
    GRAF.qq($("graf-qq"), qq, { alto: 320, tituloY: `${V.nombre} (${V.unidad})` });
    $("qq-chip").textContent = `${fmt(100 * qq.fraccion_dentro_bandas, 1)}% dentro de bandas 95%`;
    const h = d.histograma;
    GRAF.histograma($("graf-hist"), h, { alto: 260, decimales: V.decimales, tituloX: V.unidad });
    $("hist-texto").textContent = `Frecuencias observadas vs. N(μ = ${fmt(h.media, V.decimales + 1)}, σ = ${fmt(h.s, V.decimales + 2)}).`;
    $("hist-bins").textContent = `${h.cuentas.length} clases`;
    $("hist-media").textContent = fmt(h.media, V.decimales + 1);
    $("hist-s").textContent = fmt(h.s, V.decimales + 2);
    $("hist-r").textContent = fmt(qq.r_qq, 4);

    // ACF
    GRAF.acf($("graf-acf"), ind.acf, { alto: 250 });
    $("acf-texto").textContent = `Coeficientes r_k para k = 1 a ${ind.acf.rezagos.length} con bandas ±1.96/√N = ±${fmt(ind.acf.banda, 3)}.`;
    const nFuera = ind.acf.rezagos_fuera.length;
    $("acf-chip").textContent = ind.ljung_box.rechaza_h0 ? "Autocorrelación detectada" : "Sin inercia / deriva";
    $("acf-chip").className = `px-space-xs py-0.5 rounded font-label-sm text-label-sm font-bold whitespace-nowrap ${ind.ljung_box.rechaza_h0 ? MAL.chip : OK.chip}`;
    $("acf-lags").innerHTML = `Lag 1: <strong>${fmt(ind.acf.r[0], 3)}</strong> | Lag 2: <strong>${fmt(ind.acf.r[1], 3)}</strong> | Lag 3: <strong>${fmt(ind.acf.r[2], 3)}</strong>`;
    $("acf-fuera").textContent = nFuera ? `Rezagos fuera de banda: ${ind.acf.rezagos_fuera.join(", ")} (se esperan ~5 % por azar)` : "100 % de rezagos dentro de la banda de ruido blanco";

    // Durbin-Watson y rachas
    const dw = ind.durbin_watson.d;
    $("dw-valor").textContent = `d = ${fmt(dw, 3)} · ${ind.durbin_watson.interpretacion}`;
    $("dw-aguja").style.left = `calc(${Math.min(100, Math.max(0, (dw / 4) * 100))}% - 2px)`;
    $("rachas-chip").textContent = rch.patron;
    $("rachas-chip").className = `px-space-xs py-0.5 rounded font-label-sm text-label-sm font-bold ${rch.es_aleatorio ? OK.chip : MAL.chip}`;
    const fila = (a, b) => `<div class="flex items-center justify-between"><span class="text-on-surface-variant">${a}</span><strong>${b}</strong></div>`;
    $("tabla-rachas").innerHTML = [
      `<div class="flex items-center justify-between font-label-sm text-label-sm text-outline font-semibold"><span>Prueba de rachas (mediana = ${fmt(rch.mediana, V.decimales + 1)})</span><span>Z = ${fmt(rch.Z, 2)} (p = ${pf(rch.p_valor)})</span></div>`,
      fila("Rachas observadas", rch.rachas_observadas), fila("Rachas esperadas E[R]", fmt(rch.rachas_esperadas, 1)),
      fila("Puntos sobre / bajo la mediana", `${rch.n_sobre} / ${rch.n_bajo}`),
      fila("Racha más larga sobre / bajo", `${rch.racha_max_sobre} / ${rch.racha_max_bajo}`),
      fila("Tendencia (τ de Kendall)", `${fmt(rch.tendencia.tau_kendall, 3)} (p = ${pf(rch.tendencia.p_valor)})`),
    ].join("");
    const indep = ind.es_independiente && rch.es_aleatorio;
    $("ind-conclusion").innerHTML = `<span class="material-symbols-outlined ${indep ? "text-secondary" : "text-[#B45309]"}">${indep ? "check_circle" : "warning"}</span>
      <span>${indep ? "Conclusión: observaciones independientes y sin patrones en el tiempo." : "Conclusión: hay dependencia temporal o patrones; revise el intervalo de muestreo y las causas de deriva."}</span>`;

    // Box-Cox
    const bc = d.box_cox;
    const pos = (l) => `${((l + 5) / 10) * 100}%`;
    if (!bc.aplicable) {
      $("bc-estado").textContent = bc.motivo;
      $("bc-lambda").textContent = "λ̂ no aplicable";
      $("bc-texto").textContent = "Box-Cox requiere datos estrictamente positivos.";
      return;
    }
    const plana = bc.ic[0] <= -4.99 && bc.ic[1] >= 4.99;  // el IC cubre todo el rango buscado
    $("bc-lambda").textContent = plana ? "λ no identificable (verosimilitud plana en [−5, 5])"
      : `λ̂ = ${fmt(bc.lambda, 2)} · IC 95 % [${fmt(bc.ic[0], 2)}, ${fmt(bc.ic[1], 2)}]`;
    $("bc-ic").style.left = pos(bc.ic[0]);
    $("bc-ic").style.width = `${((bc.ic[1] - bc.ic[0]) / 10) * 100}%`;
    $("bc-punto").style.left = `calc(${pos(bc.lambda)} - 3px)`;
    $("bc-punto").classList.toggle("hidden", plana);
    $("bc-estado").textContent = n.es_normal ? "Estado actual: distribución nativa válida (λ = 1)" : "Estado actual: normalidad rechazada";
    $("bc-texto").textContent = bc.recomendar_transformar
      ? `El IC de λ no contiene 1: se sugiere transformar con λ ≈ ${fmt(bc.lambda, 2)} (${Math.abs(bc.lambda) < 0.25 ? "logaritmo" : "potencia"}) antes de calcular límites o índices.`
      : `El IC del 95 % de λ contiene 1${bc.ic_en_borde ? " (la verosimilitud es casi plana: datos lejos de cero con poca dispersión relativa)" : ""}: no se recomienda transformar; las unidades originales (${esc(V.unidad)}) conservan su interpretación.`;
  }

  async function iniciar(ctx) {
    V = ctx.variable;
    if (!V) return;
    if (CEP.esAtributos(V)) {
      return CEP.avisoPantalla($("pantalla"), "La validación de normalidad aplica a variables continuas",
        `«${esc(V.nombre)}» es una variable por atributos (${CEP.NOMBRES_CARTA[V.tipo_carta]}). Elija una variable continua en el selector superior.`);
    }
    $("sel-fase").onchange = $("sel-alfa").onchange = () => cargar().catch((e) => CEP.toast(e.message, "error"));
    await cargar();
  }

  CEP.arrancar(iniciar);
})();
