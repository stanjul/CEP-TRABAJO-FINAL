/* =========================================================================
 * ing_capacidad.js — Módulo 5: Cp, Cpk, Cpu, Cpl, fracción no conforme (esperada y observada,
 * por lado), histograma con LEI/LES, normalidad y veredicto.
 * API: /variables/{id}/capacidad?fase=&metodo=   (sin metodo: σ del plan, fijada o estimada)
 * ========================================================================= */
(function () {
  "use strict";
  const { api, fmt, pct, esc } = CEP;
  const $ = (id) => document.getElementById(id);
  let V, D;

  const NIVEL = {
    capaz: { fondo: "bg-secondary-container/50", circulo: "bg-secondary", icono: "task_alt", texto: "text-on-secondary-container", chip: "bg-secondary text-on-secondary" },
    marginal: { fondo: "bg-[#FEF3C7]", circulo: "bg-[#B45309]", icono: "warning", texto: "text-[#B45309]", chip: "bg-[#B45309] text-on-error" },
    no_capaz: { fondo: "bg-error-container/60", circulo: "bg-error", icono: "dangerous", texto: "text-on-error-container", chip: "bg-error text-on-error" },
  };
  const colorIndice = (x) => (x === null ? "text-outline" : x >= 1.33 ? "text-secondary" : x >= 1 ? "text-[#B45309]" : "text-error");
  const f2 = (x) => (x === null || x === undefined ? "—" : fmt(x, 2));
  const fPPM = (x) => (x >= 100 ? fmt(x, 0) : fmt(x, 2));

  function nivelDe(cpk) { return cpk >= 1.33 ? "capaz" : cpk >= 1 ? "marginal" : "no_capaz"; }

  function pintar() {
    const d = V.decimales + 1;
    const c = D.indices;
    const indice = c.cpk;
    const sigma = D.sigma_dentro;
    const ppm = D.ppm_esperado;
    const nivel = nivelDe(indice);
    const est = NIVEL[nivel];

    $("ctx-variable").textContent = `${V.nombre}`;
    const t = D.objetivo ?? (D.lei !== null && D.les !== null ? (D.lei + D.les) / 2 : null);
    $("ctx-espec").textContent = D.lei !== null && D.les !== null
      ? `${fmt(t, V.decimales)} ± ${fmt((D.les - D.lei) / 2, V.decimales)} ${V.unidad}` : D.les !== null ? `LES ${fmt(D.les, V.decimales)} ${V.unidad}` : `LEI ${fmt(D.lei, V.decimales)} ${V.unidad}`;
    $("ctx-datos").textContent = `${D.k_subgrupos} subgrupos · N = ${D.N}`;

    // Veredicto
    $("veredicto").className = `p-space-lg rounded-xl shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-space-md ${est.fondo}`;
    $("ver-circulo").className = `w-14 h-14 rounded-full flex items-center justify-center ${est.circulo}`;
    $("ver-icono").textContent = est.icono;
    $("ver-sub").className = `font-label-sm text-label-sm font-semibold ${est.texto}`;
    $("ver-nivel").textContent = `NIVEL ${fmt(3 * indice, 2)}σ`;
    $("ver-nivel").className = `px-space-xs py-0.5 rounded font-label-sm text-label-sm font-bold ${est.chip}`;
    $("ver-titulo").textContent = { capaz: `El proceso es capaz de cumplir la especificación (Cpk = ${f2(indice)} ≥ 1,33)`,
      marginal: `El proceso cumple la especificación con poco margen (Cpk = ${f2(indice)})`,
      no_capaz: `El proceso no es capaz de cumplir la especificación (Cpk = ${f2(indice)} < 1,00)` }[nivel];
    $("ver-titulo").className = `font-headline-sm text-headline-sm font-bold ${est.texto}`;
    const origenSigma = D.metodo_sigma === "fijada" ? "fijada por el ingeniero" : `estimada con ${{ rbar: "R̄/d₂", sbar: "s̄/c₄", mr: "MR̄/d₂" }[D.metodo_sigma]}`;
    $("ver-texto").textContent = (D.en_control === false ? "⚠ El proceso presenta señales fuera de control: el índice no es confiable. " : D.en_control ? "Bajo control estadístico. " : "")
      + `σ ${origenSigma} = ${fmt(sigma, d + 1)} ${V.unidad}.`;
    $("ver-ppm").textContent = fPPM(ppm.ppm);

    // KPIs
    $("k-cp").textContent = f2(c.cp);
    $("k-cp-t").textContent = c.cp === null ? "Unilateral" : c.cp >= 1.33 ? "Excelente" : c.cp >= 1 ? "Ajustado" : "Insuficiente";
    $("k-cpk").textContent = f2(c.cpk);
    $("k-cpk").className = `font-metric-display text-metric-display font-bold ${colorIndice(c.cpk)}`;
    $("k-cpk-t").textContent = { capaz: "Capaz", marginal: "Marginal", no_capaz: "No capaz" }[nivelDe(c.cpk)];
    $("k-cpu").textContent = f2(c.cpu);
    $("k-cpl").textContent = f2(c.cpl);
    $("k-unil-t").textContent = `mín(Cpu, Cpl) = ${f2(c.cpk)}`;
    $("k-pct").textContent = pct(ppm.total, ppm.total < 0.001 ? 4 : 2);
    $("k-ppm").textContent = `${fPPM(ppm.ppm)} ppm`;
    $("k-obs").textContent = `${D.observado.fuera} de ${D.N} (${pct(D.observado.fuera / D.N, 1)})`;

    // Histograma y descriptivos
    GRAF.histograma($("graf-hist"), D.histograma, { lei: D.lei, les: D.les, objetivo: D.objetivo, decimales: V.decimales, alto: 330,
      tituloX: `${V.nombre} (${V.unidad})` });
    $("desc-titulo").textContent = `Resumen de Estadísticos Descriptivos (N = ${D.N})`;
    const fila = (a, b) => `<div class="flex justify-between gap-space-xs"><span class="text-outline">${a}</span><b>${b}</b></div>`;
    const forma = D.normalidad ? D.normalidad.forma : {};
    $("tabla-desc").innerHTML = [
      fila("Media (X̄):", `${fmt(D.media, d)}`), fila("Mediana:", fmt(D.mediana, d)), fila("σ usada:", fmt(D.sigma_dentro, d + 1)),
      fila("Desv. estándar (s):", fmt(D.desviacion_estandar, d + 1)), fila("Mínimo:", fmt(D.minimo, d)), fila("Máximo:", fmt(D.maximo, d)),
      fila("Asimetría:", fmt(forma.asimetria, 3)), fila("Curtosis:", fmt(forma.curtosis_exceso, 3)),
    ].join("");

    // Normalidad
    if (D.normalidad) {
      const ad = D.normalidad.pruebas.anderson_darling;
      $("ad-a2").textContent = fmt(ad.estadistico, 3);
      $("ad-p").textContent = ad.p_valor < 0.001 ? "< 0.001" : fmt(ad.p_valor, 3);
      $("ad-chip").textContent = ad.rechaza_h0 ? "Rechazada" : "Aceptada";
      $("ad-chip").className = `px-space-xs py-0.5 rounded font-label-sm text-label-sm font-bold ${ad.rechaza_h0 ? "bg-[#FEF3C7] text-[#B45309]" : "bg-secondary-container text-on-secondary-container"}`;
      $("ad-icono").textContent = ad.rechaza_h0 ? "warning" : "check_circle";
      $("ad-icono").className = `material-symbols-outlined ${ad.rechaza_h0 ? "text-[#B45309]" : "text-secondary"}`;
      $("ad-texto").textContent = ad.rechaza_h0
        ? "Como p < 0.05 se rechaza H0: los ppm calculados con la normal pueden no ser exactos."
        : "Como p > 0.05, no se rechaza H0: los datos son compatibles con una distribución normal.";
      GRAF.qq($("graf-qq"), D.qq, { alto: 170, mini: true });
    }

    // Fracción no conforme por lado (esperada con la normal y observada en los datos)
    const ob = D.observado;
    const fx = (donde, p, n) => `<tr><td class="py-1.5 px-space-xs">${donde}</td><td class="py-1.5 px-space-xs text-right font-bold">${pct(p, p < 0.001 ? 4 : 2)}</td>
      <td class="py-1.5 px-space-xs text-right">${fPPM(1e6 * p)}</td><td class="py-1.5 px-space-xs text-right">${n} de ${D.N}</td></tr>`;
    const filasNC = [];
    if (D.lei !== null) filasNC.push(fx(`Por debajo del mínimo (${fmt(D.lei, V.decimales)})`, ppm.bajo_lei, ob.bajo_lei));
    if (D.les !== null) filasNC.push(fx(`Por encima del máximo (${fmt(D.les, V.decimales)})`, ppm.sobre_les, ob.sobre_les));
    filasNC.push(fx("<b>Total</b>", ppm.total, ob.fuera));
    $("tabla-comp").innerHTML = filasNC.join("");
    // Solo se indica el lado dominante si la fracción esperada es apreciable (≥ 1 ppm).
    const lado = D.lei !== null && D.les !== null && ppm.ppm >= 1 && Math.max(ppm.bajo_lei, ppm.sobre_les) > 2 * Math.min(ppm.bajo_lei, ppm.sobre_les)
      ? (ppm.sobre_les > ppm.bajo_lei ? " La mayor parte queda por encima del máximo." : " La mayor parte queda por debajo del mínimo.") : "";
    $("comp-texto").textContent = `Con la media y la σ actuales se espera que ${pct(ppm.total, ppm.total < 0.001 ? 4 : 2)} del producto quede fuera de especificación (${fPPM(ppm.ppm)} piezas por millón).${lado} `
      + "Lo esperado supone distribución normal; lo observado es lo que efectivamente salió en las muestras.";

    // Conclusiones
    const ic = { ok: ["check", "text-secondary"], advertencia: ["warning", "text-[#B45309]"], critico: ["error", "text-error"] };
    $("lista-conclusiones").innerHTML = D.conclusiones.map((x) => `<li class="flex items-start gap-space-xs font-body-sm text-body-sm">
      <span class="material-symbols-outlined text-base ${ic[x.nivel][1]}">${ic[x.nivel][0]}</span><span>${esc(x.texto)}</span></li>`).join("")
      + `<li class="flex items-start gap-space-xs font-body-sm text-body-sm"><span class="material-symbols-outlined text-base text-primary">update</span>
         <span><strong>Frecuencia de muestreo:</strong> subgrupo n = ${V.n} cada ${V.frecuencia_min} min (configurable en Límites & Reglas).</span></li>`;
  }

  async function cargar() {
    const q = new URLSearchParams();
    if ($("sel-metodo").value !== "fijada") q.set("metodo", $("sel-metodo").value);
    if ($("sel-fase").value) q.set("fase", $("sel-fase").value);
    $("pantalla").classList.add("cargando");
    try { D = await api(`/variables/${V.id}/capacidad?${q}`); pintar(); }
    finally { $("pantalla").classList.remove("cargando"); }
  }

  async function iniciar(ctx) {
    V = ctx.variable;
    if (!V) return;
    if (CEP.esAtributos(V)) {
      return CEP.avisoPantalla($("pantalla"), "Cp/Cpk se calculan para variables continuas",
        `«${esc(V.nombre)}» es por atributos. Para atributos la capacidad se expresa como fracción defectuosa media (p̄) en la carta.`,
        [CEP.conVariable("/ingenieria/atributos", V.id), "Ver carta de atributos"]);
    }
    if (V.lei === null && V.les === null) {
      return CEP.avisoPantalla($("pantalla"), "Faltan los límites de especificación",
        `Defina LEI y/o LES de «${esc(V.nombre)}» para calcular los índices de capacidad.`, [CEP.conVariable("/ingenieria/configuracion", V.id), "Ir a Límites & Reglas"]);
    }
    if (V.tipo_carta === "imr") [...$("sel-metodo").options].forEach((o) => (o.disabled = !["mr", "fijada"].includes(o.value)));
    else $("sel-metodo").querySelector('[value="mr"]').disabled = true;
    if (V.sigma_monitoreo) {
      const op = $("sel-metodo").querySelector('[value="fijada"]');
      op.hidden = false;
      op.textContent = `σ fijada por el ingeniero (${fmt(V.sigma_monitoreo, V.decimales + 1)} ${V.unidad})`;
      $("sel-metodo").value = "fijada";
    } else $("sel-metodo").value = V.tipo_carta === "imr" ? "mr" : V.estimador_sigma;
    $("sel-metodo").onchange = $("sel-fase").onchange = () => cargar().catch((e) => CEP.toast(e.message, "error"));
    await cargar();
  }

  CEP.arrancar(iniciar);
})();
