/* =========================================================================
 * ing_diseno.js — Plan de muestreo de la variable activa (Módulo 6).
 *  - Controles: n, frecuencia, k (qué tan estrictos), σ (datos o fijada) y cambio a detectar.
 *  - Comparación plan actual vs propuesto con ATS/ARL y carga muestral, en palabras.
 *  - Guardar plan (POST /variables/{id}/plan, con justificación).
 *  - Detalle técnico: curva ARL, tabla y Monte Carlo (/diseno/*) para cartas X̄ / I.
 * API: GET/POST /variables/{id}/plan, /diseno/arl, /diseno/curva, /diseno/simular
 * ========================================================================= */
(function () {
  "use strict";
  const { api, fmt, pct, esc, toast } = CEP;
  const $ = (id) => document.getElementById(id);
  let V = null, R = null, temporizador = null, eje = "arl";

  const num = (t) => (String(t ?? "").trim() === "" ? null : parseFloat(String(t).replace(",", ".")));
  const esAtrib = () => CEP.esAtributos(V);
  const esPorcentaje = () => ["p", "np"].includes(V.tipo_carta);

  /** Horas de producción → texto (minutos, horas o turnos). */
  function duracion(h, ht = 8) {
    if (h === null || h === undefined) return "nunca (en la práctica)";
    if (h < 1) return `${fmt(h * 60, 0)} min`;
    if (h < 2 * ht) return `${fmt(h, 1)} horas`;
    return `${fmt(h, 0)} horas (≈ ${fmt(h / ht, 0)} turnos)`;
  }
  const muestras = (x) => (x === null || x === undefined ? "—" : `${fmt(x, x < 10 ? 1 : 0)} muestras`);

  // ------------------------------------------------------------------ Lectura de controles
  function kElegido() {
    const otro = num($("pl-k-otro").value);
    if (otro) return otro;
    const r = document.querySelector('input[name="pl-k"]:checked');
    return r ? +r.value : V.k_sigma;
  }
  function sigmaElegida() {
    const modo = document.querySelector('input[name="pl-sigma-modo"]:checked');
    return modo && modo.value === "fija" ? num($("pl-sigma").value) : null;
  }
  function leerPlan() {
    const p = {
      n: V.tipo_carta === "imr" ? 1 : Math.max(1, Math.round(+$("pl-n").value || 1)),
      frecuencia_min: Math.max(1, Math.round(+$("pl-f").value || V.frecuencia_min)),
      k: kElegido(),
    };
    if (esAtrib()) {
      const f = esPorcentaje() ? 100 : 1;
      const c0 = num($("pl-c0").value), c1 = num($("pl-c1").value);
      if (c0) p.centro = c0 / f;
      if (c1) p.centro_1 = c1 / f;
    } else {
      p.delta = +$("pl-delta").value;
      const s = sigmaElegida();
      if (s) p.sigma = s;
    }
    return p;
  }
  function hayCambios() {
    const p = leerPlan();
    const sigmaActual = V.sigma_monitoreo || null;
    const sigmaNueva = esAtrib() ? sigmaActual : sigmaElegida();
    return (V.tipo_carta !== "imr" && p.n !== V.n) || p.frecuencia_min !== V.frecuencia_min
      || Math.abs(p.k - V.k_sigma) > 1e-9 || (sigmaNueva || null) !== sigmaActual;
  }

  // ------------------------------------------------------------------ Controles → interfaz
  function marcarChips() {
    document.querySelectorAll("#pl-chips button").forEach((b) => {
      const sel = +b.dataset.min === +$("pl-f").value;
      b.className = `h-10 px-space-sm rounded-lg font-label-md text-label-md ${sel ? "bg-primary-container text-on-primary" : "bg-surface-container-low hover:bg-surface-container"}`;
      b.setAttribute("aria-pressed", sel);
    });
  }
  function ponerControles() {
    $("pl-n").value = V.tipo_carta === "imr" ? 1 : V.n;
    $("pl-f").value = V.frecuencia_min;
    const radio = document.querySelector(`input[name="pl-k"][value="${V.k_sigma}"]`);
    document.querySelectorAll('input[name="pl-k"]').forEach((r) => (r.checked = false));
    if (radio) { radio.checked = true; $("pl-k-otro").value = ""; } else $("pl-k-otro").value = V.k_sigma;
    document.querySelector(`input[name="pl-sigma-modo"][value="${V.sigma_monitoreo ? "fija" : "datos"}"]`).checked = true;
    $("pl-sigma").value = V.sigma_monitoreo ? String(V.sigma_monitoreo).replace(".", ",") : "";
    marcarChips();
  }

  function adaptarAVariable() {
    $("pl-variable").textContent = V.nombre;
    const imr = V.tipo_carta === "imr";
    $("pl-n").disabled = imr;
    document.querySelectorAll("[data-paso-n]").forEach((b) => (b.disabled = imr));
    $("pl-n-ayuda").textContent = imr
      ? "Esta variable se mide de a una unidad (gráfica de valores individuales): solo se ajusta la frecuencia."
      : esAtrib() ? "Más unidades por muestra hacen más confiable el porcentaje o el conteo."
        : "Más unidades por muestra detectan antes los cambios pequeños.";
    $("pl-sigma-caja").classList.toggle("hidden", esAtrib());
    $("pl-delta-caja").classList.toggle("hidden", esAtrib());
    $("pl-atrib-caja").classList.toggle("hidden", !esAtrib());
    $("pl-atrib-caja").classList.toggle("flex", esAtrib());
    $("pl-sigma-unidad").textContent = V.unidad || "";
    if (esAtrib()) {
      const etq = { p: "% de unidades defectuosas", np: "% de unidades defectuosas", c: "fallas por muestra", u: "fallas por unidad" }[V.tipo_carta];
      $("pl-c0-txt").textContent = `Nivel habitual (${etq})`;
      $("pl-c1-txt").textContent = `Detectar si sube a (${etq})`;
    }
  }

  // ------------------------------------------------------------------ Consulta y pintado
  async function consultar() {
    const p = leerPlan();
    const q = new URLSearchParams(Object.entries(p).filter(([, v]) => v !== null && v !== undefined && !Number.isNaN(v)));
    try {
      R = await api(`/variables/${V.id}/plan?${q}`);
    } catch (e) { return toast(e.message, "error"); }
    pintarReferencia();
    pintarComparacion();
    $("pl-guardar").disabled = !hayCambios();
    $("pl-restaurar").disabled = !hayCambios();
    tecnico(p).catch((e) => toast(e.message, "error"));
  }
  function programar() { clearTimeout(temporizador); temporizador = setTimeout(consultar, 250); }

  function pintarReferencia() {
    const ref = R.referencia;
    const d = V.decimales + 1;
    if (esAtrib()) {
      const f = esPorcentaje() ? (x) => fmt(100 * x, 2) : (x) => fmt(x, 2);
      if (ref.centro !== null && ref.centro !== undefined && !$("pl-c0").value) $("pl-c0").value = f(ref.centro);
      if (R.centro_1 && !$("pl-c1").value) $("pl-c1").value = f(R.centro_1);
      $("pl-c0-origen").textContent = ref.centro === null || ref.centro === undefined
        ? "Todavía no hay datos: escribe el nivel de defectos que esperas para ver el desempeño del plan."
        : `El nivel habitual sale de ${ref.origen}. El cambio propuesto por defecto es el doble.`;
      return;
    }
    const sig = R.referencia.sigma;
    $("pl-sigma-datos").textContent = V.sigma_monitoreo
      ? "Ahora se usa la σ fijada; al elegir esta opción se vuelve a la calculada con los datos."
      : sig ? `σ = ${fmt(sig, d)} ${V.unidad} (sale de ${ref.origen})` : "Todavía no hay datos suficientes para calcularla.";
    const delta = +$("pl-delta").value;
    const sigmaUsada = sigmaElegida() || sig;
    $("pl-delta-texto").textContent = sigmaUsada
      ? `Que el promedio se corra ${fmt(delta, 2)} σ, es decir, unos ${fmt(delta * sigmaUsada, d)} ${V.unidad}.`
      : `Que el promedio se corra ${fmt(delta, 2)} veces la variabilidad del proceso (σ).`;
  }

  function comparar(a, b, menorEsMejor, textoMejor, textoPeor) {
    if (a === null || b === null || a === undefined || b === undefined || Math.abs(a - b) < 1e-9 * Math.max(1, a)) return "";
    const mejor = menorEsMejor ? b < a : b > a;
    return `<span class="ml-space-xs inline-flex items-center gap-0.5 font-label-sm text-label-sm text-on-surface-variant">
      <span class="material-symbols-outlined text-sm">${b < a ? "arrow_downward" : "arrow_upward"}</span>${mejor ? textoMejor : textoPeor}</span>`;
  }

  function pintarComparacion() {
    const a = R.actual, p = R.propuesto, ht = R.horas_turno;
    const da = a.diseno, dp = p.diseno;
    const plan = (x) => `${x.n} ${x.n === 1 ? "unidad" : "unidades"} ${CEP.cadaCuanto(x.frecuencia_min)}`;
    const celda = (principal, secundaria, extra = "") => `<div class="font-body-lg text-body-lg font-semibold text-on-surface">${principal}${extra}</div>
      <div class="font-body-sm text-body-sm text-on-surface-variant">${secundaria}</div>`;
    const filas = [
      ["Plan", celda(plan(a), `límites a ${fmt(a.k, 1)}σ`), celda(plan(p), `límites a ${fmt(p.k, 1)}σ`)],
    ];
    if (da && dp) {
      filas.push(["Tiempo para detectar el cambio",
        celda(duracion(da.ats1, ht), muestras(da.arl1)),
        celda(duracion(dp.ats1, ht), muestras(dp.arl1), comparar(da.ats1, dp.ats1, true, "más rápido", "más lento"))]);
      filas.push(["Una falsa alarma, en promedio, cada",
        celda(duracion(da.ats0, ht), muestras(da.arl0)),
        celda(duracion(dp.ats0, ht), muestras(dp.arl0), comparar(da.ats0, dp.ats0, false, "menos falsas alarmas", "más falsas alarmas"))]);
    }
    filas.push(["Unidades a revisar por turno",
      celda(fmt(a.carga.unidades_por_turno, 0), `${fmt(a.carga.muestras_por_turno, 0)} muestras en ${fmt(ht, 0)} h`),
      celda(fmt(p.carga.unidades_por_turno, 0), `${fmt(p.carga.muestras_por_turno, 0)} muestras en ${fmt(ht, 0)} h`,
        comparar(a.carga.unidades_por_turno, p.carga.unidades_por_turno, true, "menos trabajo", "más trabajo"))]);
    $("pl-comparacion").innerHTML = filas.map(([t, x, y]) => `<tr>
      <th class="py-space-sm pr-space-md align-top font-body-md text-body-md font-normal text-on-surface-variant">${t}</th>
      <td class="py-space-sm px-space-md align-top">${x}</td><td class="py-space-sm pl-space-md align-top bg-primary-fixed/20">${y}</td></tr>`).join("");

    const t = p.textos;
    const items = [t.deteccion, t.falsa_alarma, t.carga].filter(Boolean);
    if (!dp) items.unshift("Para estimar en cuánto tiempo se detectaría un cambio, indica el nivel habitual de defectos.");
    $("pl-textos").innerHTML = items.map((x) => `<li class="flex items-start gap-space-xs font-body-md text-body-md text-on-surface">
      <span class="material-symbols-outlined text-base text-primary-container mt-0.5">chevron_right</span><span>${esc(x)}</span></li>`).join("");
    const avisos = R.avisos || [];
    $("pl-avisos").classList.toggle("hidden", !avisos.length);
    $("pl-avisos").classList.toggle("flex", !!avisos.length);
    $("pl-avisos-txt").innerHTML = avisos.map((x) => `<p>${esc(x)}</p>`).join("");
  }

  // ------------------------------------------------------------------ Guardar
  async function guardar(reiniciar = false) {
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    let justificacion = guardar.ultima;
    if (!reiniciar) {
      const r = await CEP.modal({
        titulo: "Guardar el plan de muestreo",
        texto: "El cambio queda en el historial con tu nombre. Escribe brevemente el motivo.",
        campos: [{ nombre: "j", etiqueta: "Motivo del cambio", tipo: "textarea", requerido: true }],
        aceptar: "Guardar plan",
      });
      if (!r || !r.j.trim()) return;
      justificacion = guardar.ultima = r.j.trim();
    }
    const p = leerPlan();
    const cuerpo = { frecuencia_min: p.frecuencia_min, k_sigma: p.k, usuario, justificacion, reiniciar_fase_i: reiniciar };
    if (V.tipo_carta !== "imr") cuerpo.n = p.n;
    if (!esAtrib()) {
      const s = sigmaElegida();
      const modo = document.querySelector('input[name="pl-sigma-modo"]:checked').value;
      if (modo === "fija") {
        if (!s || s <= 0) return toast("Escribe la σ que quieres fijar (un número mayor que cero).", "error");
        cuerpo.sigma_monitoreo = s;
      } else if (V.sigma_monitoreo) cuerpo.borrar_sigma = true;
    }
    try {
      const r = await api(`/variables/${V.id}/plan`, { json: cuerpo });
      let msj = "Plan guardado.";
      if (r.limites_recalculados) msj += " Los límites de control se recalcularon.";
      if (r.archivados) msj += ` ${r.archivados} muestra(s) pasaron al archivo.`;
      toast(msj);
      setTimeout(() => location.reload(), 900);
    } catch (e) {
      if (!reiniciar && /Fase I de nuevo/.test(e.message)) {
        const ok = await CEP.modal({ titulo: "Empezar la Fase I de nuevo", texto: esc(e.message), aceptar: "Sí, empezar de nuevo", peligro: true });
        if (ok) return guardar(true);
        return;
      }
      toast(e.message, "error");
    }
  }

  // ------------------------------------------------------------------ Detalle técnico
  async function tecnico(p) {
    const tec = $("pl-tecnico");
    $("tec-curva").classList.toggle("hidden", esAtrib());
    $("tec-mc").classList.toggle("hidden", esAtrib());
    const dp = R.propuesto.diseno;
    if (!dp) { $("tabla-arl").innerHTML = ""; return; }
    $("k-arl0").textContent = dp.arl0 === null ? "∞" : fmt(dp.arl0, 1);
    $("k-alfa").textContent = `α = ${pct(dp.alfa, 3)} · ATS₀ = ${duracion(dp.ats0, R.horas_turno)}`;
    $("k-beta").textContent = fmt(dp.beta, 4);
    $("k-potencia").textContent = `Potencia 1 − β = ${pct(dp.potencia, 1)}`;
    $("k-arl1").textContent = dp.arl1 === null ? "∞" : fmt(dp.arl1, 3);
    $("k-de").textContent = `DE(RL) = ${dp.de_rl1 === null ? "—" : fmt(dp.de_rl1, 3)} muestras`;
    $("k-ats1").textContent = duracion(dp.ats1, R.horas_turno);
    $("k-ats0").textContent = `${fmt(R.propuesto.carga.unidades_por_hora, 1)} unidades por hora`;
    if (!tec.open) return;  // la curva y la tabla se calculan solo si el panel está abierto

    const h = p.frecuencia_min / 60;
    if (!esAtrib()) {
      const n = p.n;
      const curva = await api(`/diseno/curva?${new URLSearchParams({ k: p.k, n, h, comparar: $("p-comparar").value })}`);
      const series = Object.entries(curva.series).map(([nn, s]) => ({ nombre: `n = ${nn}`, x: curva.deltas, y: eje === "arl" ? s.arl : s.ats }));
      GRAF.curvas($("graf-arl"), series, {
        alto: 320, logY: true, tituloX: "Corrimiento δ (en σ del proceso)", tituloY: eje === "arl" ? "ARL₁ (muestras, escala log)" : "ATS₁ (horas, escala log)",
        etiquetaX: "δ", etiquetaY: eje.toUpperCase(), formatoY: ":.3f", refs: [{ x: p.delta, color: "#ba1a1a" }],
        puntos: [{ x: p.delta, y: eje === "arl" ? dp.arl1 : dp.ats1, texto: ` ${eje === "arl" ? "ARL₁" : "ATS₁"} = ${fmt(eje === "arl" ? dp.arl1 : dp.ats1, 2)}`, color: "#ba1a1a" }],
      });
      document.querySelectorAll("[data-eje]").forEach((b) => {
        b.className = `px-2 py-1 rounded font-label-sm text-label-sm ${b.dataset.eje === eje ? "bg-surface-container-lowest text-primary font-bold shadow-sm" : "text-on-surface-variant"}`;
      });
      $("tabla-arl-cab").innerHTML = `<tr class="bg-surface-container-high font-label-sm text-label-sm"><th class="py-1.5 px-space-sm text-left">δ (σ)</th>
        <th class="py-1.5 px-space-sm text-right">β</th><th class="py-1.5 px-space-sm text-right">ARL</th><th class="py-1.5 px-space-sm text-right">ATS (h)</th><th class="py-1.5 px-space-sm text-right">Muestras para detectar con 90 %</th></tr>`;
      const filas = await Promise.all([0, 0.5, 1, 1.5, 2, 2.5, 3].map(async (d) => {
        const x = await api(`/diseno/arl?${new URLSearchParams({ k: p.k, n, h, delta: d })}`);
        const p1 = 1 - x.beta;
        const m90 = p1 >= 1 ? 1 : Math.ceil(Math.log(0.1) / Math.log(1 - p1));
        return `<tr class="${Math.abs(d - p.delta) < 1e-9 ? "bg-primary-fixed/30 font-bold" : ""}"><td class="py-1.5 px-space-sm">${fmt(d, 1)}</td>
          <td class="py-1.5 px-space-sm text-right">${fmt(x.beta, 4)}</td><td class="py-1.5 px-space-sm text-right">${fmt(d === 0 ? x.arl0 : x.arl1, 2)}</td>
          <td class="py-1.5 px-space-sm text-right">${fmt(d === 0 ? x.ats0 : x.ats1, 2)}</td><td class="py-1.5 px-space-sm text-right">${d === 0 ? "—" : m90}</td></tr>`;
      }));
      $("tabla-arl").innerHTML = filas.join("");
      $("tec-formulas").textContent = "β = Φ(k − δ√n) − Φ(−k − δ√n) · ARL₁ = 1/(1 − β) · ARL₀ = 1/α con α = 2Φ(−k) · ATS = ARL · h";
    } else {
      // Atributos: ARL exacto con Binomial (p, np) o Poisson (c, u) para varios niveles de defectos.
      const c0 = R.referencia.centro;
      const f = esPorcentaje() ? (x) => pct(x, 2) : (x) => fmt(x, 3);
      const niveles = [1, 1.25, 1.5, 2, 2.5, 3].map((m) => c0 * m).filter((x) => !esPorcentaje() || x < 1);
      $("tabla-arl-cab").innerHTML = `<tr class="bg-surface-container-high font-label-sm text-label-sm"><th class="py-1.5 px-space-sm text-left">Nivel de defectos</th>
        <th class="py-1.5 px-space-sm text-right">β</th><th class="py-1.5 px-space-sm text-right">ARL</th><th class="py-1.5 px-space-sm text-right">ATS (h)</th></tr>`;
      const filas = await Promise.all(niveles.map(async (c1, i) => {
        const q = new URLSearchParams({ n: p.n, frecuencia_min: p.frecuencia_min, k: p.k, centro: c0, centro_1: i === 0 ? c0 : c1 });
        const d = (await api(`/variables/${V.id}/plan?${q}`)).propuesto.diseno;
        return `<tr><td class="py-1.5 px-space-sm">${f(c1)}${i === 0 ? " (habitual)" : ""}</td><td class="py-1.5 px-space-sm text-right">${fmt(d.beta, 4)}</td>
          <td class="py-1.5 px-space-sm text-right">${d.arl1 === null ? "∞" : fmt(d.arl1, 2)}</td><td class="py-1.5 px-space-sm text-right">${d.ats1 === null ? "∞" : fmt(d.ats1, 2)}</td></tr>`;
      }));
      $("tabla-arl").innerHTML = filas.join("");
      $("tec-formulas").textContent = esPorcentaje()
        ? "X ~ Binomial(n, p): β = P(n·LCI ≤ X ≤ n·LCS). Por ser discreta, α no es exactamente 0,27 %."
        : "X ~ Poisson(λ): β = P(LCI ≤ X ≤ LCS) en la escala del conteo. Por ser discreta, α no es exactamente 0,27 %.";
    }
  }

  async function simular() {
    const p = leerPlan();
    const btn = $("btn-simular");
    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined text-sm animate-spin">refresh</span>Simulando…';
    try {
      const r = await api("/diseno/simular", { json: { k: p.k, n: p.n, delta: p.delta, replicas: +$("mc-replicas").value, semilla: +$("mc-semilla").value } });
      $("mc-arl").textContent = fmt(r.arl_simulado, 3);
      $("mc-ic").textContent = `[${fmt(r.ic95[0], 2)}, ${fmt(r.ic95[1], 2)}]`;
      const dentro = r.ic95[0] <= r.arl_teorico && r.arl_teorico <= r.ic95[1];
      $("mc-err").textContent = `${fmt(r.arl_teorico, 3)} (${r.error_relativo >= 0 ? "+" : ""}${pct(r.error_relativo, 1)})`;
      $("mc-err").className = `font-label-lg text-label-lg ${dentro ? "text-secondary" : "text-[#B45309]"}`;
      const h = r.histograma;
      GRAF.barras($("graf-mc"), h.map((_, i) => (i === h.length - 1 && i === 50 ? "≥50" : String(i))).slice(1), h.slice(1),
        { alto: 220, tituloX: "Longitud de corrida (muestras hasta la señal)", tituloY: "Réplicas", etiquetaX: "RL", etiquetaY: "réplicas" });
    } catch (e) { toast(e.message, "error"); }
    btn.disabled = false;
    btn.innerHTML = '<span class="material-symbols-outlined text-sm">play_arrow</span>Simular';
  }

  // ------------------------------------------------------------------ Carga muestral objetivo
  // Compara el plan vigente con los dos caminos hacia una carga objetivo (aumentar n o reducir el
  // intervalo), con potencia, detección en m muestras y en un horizonte común (GET /variables/{id}/carga).
  let CG = null, tCarga = null, cargaLista = false, horizonteManual = false;
  const programarCarga = () => { clearTimeout(tCarga); tCarga = setTimeout(consultarCarga, 300); };
  const planTxt = (p) => `${p.n} ${p.n === 1 ? "unidad" : "unidades"} ${CEP.cadaCuanto(p.frecuencia_min)}`;

  async function consultarCarga() {
    if (!V || esAtrib()) return;
    const q = new URLSearchParams();
    const m = Math.max(1, Math.round(+$("cg-m").value || 5));
    q.set("m", m);
    if (cargaLista) {
      const o = num($("cg-objetivo").value), c = num($("cg-cambio").value), h = num($("cg-horizonte").value);
      if (o > 0) q.set("carga", o);
      if (c > 0) q.set("cambio", c);
      if (horizonteManual && h > 0) q.set("horizonte_h", h);
    }
    const s = sigmaElegida();
    if (s) q.set("sigma", s);
    try {
      CG = await api(`/variables/${V.id}/carga?${q}`);
    } catch (e) {
      $("cg-tabla").innerHTML = "";
      $("cg-textos").innerHTML = `<li class="font-body-md text-body-md text-on-surface-variant">${esc(e.message)}</li>`;
      return;
    }
    if (!cargaLista) {
      $("cg-objetivo").value = fmt(CG.objetivo, 1);
      $("cg-cambio").value = fmt(CG.cambio, V.decimales);
      cargaLista = true;
    }
    if (!horizonteManual) $("cg-horizonte").value = fmt(CG.horizonte_min / 60, 2);
    pintarCarga();
  }

  function pintarCarga() {
    const P = CG.planes, ht = CG.horas_turno, u = V.unidad ? ` ${V.unidad}` : "";
    const act = P.actual;
    $("cg-unidad").textContent = V.unidad ? `(${V.unidad})` : "";
    $("cg-actual").textContent = `${fmt(CG.carga_actual, 1)} unidades/h`;
    $("cg-actual-plan").textContent = `${planTxt(act)} · ${fmt(CG.carga_actual * ht, 0)} por turno de ${fmt(ht, 0)} h`;
    $("cg-cambio-sigma").textContent = `≈ ${fmt(CG.delta, 2)} σ (σ = ${fmt(CG.sigma, V.decimales + 1)}${u}, de ${CG.referencia.origen})`;
    document.querySelector('[data-usar="a"]').classList.toggle("hidden", !P.a);
    const T = CG.horizonte_min / 60;
    const planes = [act, P.a, P.b];
    // Resalta el mejor valor de cada fila entre los planes disponibles.
    const celda = (vals, fmtFn, mayorEsMejor, sub) => {
      const nums = vals.map((v) => (v === null || v === undefined ? null : v));
      const validos = nums.filter((x) => x !== null && Number.isFinite(x));
      const mejor = validos.length ? (mayorEsMejor ? Math.max(...validos) : Math.min(...validos)) : null;
      return nums.map((v, i) => {
        if (!planes[i]) return `<td class="py-space-sm px-space-md align-top font-body-sm text-body-sm text-on-surface-variant">${i === 1 ? "No aplica: con valores individuales cada muestra es una unidad." : "—"}</td>`;
        const top = mayorEsMejor !== null && v !== null && mejor !== null && Math.abs(v - mejor) < 1e-12 && validos.length > 1;
        return `<td class="py-space-sm px-space-md align-top ${i ? "bg-primary-fixed/20" : ""}">
          <div class="font-body-lg text-body-lg ${top ? "font-bold text-primary" : "font-semibold text-on-surface"}">${fmtFn(v, planes[i])}</div>
          ${sub ? `<div class="font-body-sm text-body-sm text-on-surface-variant">${sub(planes[i])}</div>` : ""}</td>`;
      }).join("");
    };
    const g = (clave) => planes.map((p) => (p ? p[clave] : null));
    const filas = [
      ["Plan", celda(planes.map(() => 0), (_, p) => planTxt(p), null, null)],
      ["Carga muestral", celda(g("carga_hora"), (v) => `${fmt(v, 1)} unidades/h`, null, (p) => `${fmt(p.carga_hora * ht, 0)} unidades por turno`)],
      ["Potencia: detectar en la muestra siguiente", celda(g("potencia"), (v) => pct(v, 1), true, (p) => `β = ${fmt(p.beta, 4)}`)],
      [`Detectar en las primeras ${act.m} muestras`, celda(g("p_m"), (v) => pct(v, 1), true, (p) => `en ${duracion(p.m * p.frecuencia_min / 60, ht)}`)],
      [`Detectar en las primeras ${fmt(T, 2)} h`, celda(g("p_horizonte"), (v) => pct(v, 1), true, (p) => `${p.muestras_en_horizonte} muestras en ese tiempo`)],
      ["Tiempo medio para detectar", celda(g("ats1_horas"), (v) => duracion(v, ht), false, (p) => muestras(p.arl1))],
      ["Una falsa alarma, en promedio, cada", celda(g("ats0_horas"), (v) => duracion(v, ht), true, (p) => muestras(p.arl0))],
    ];
    $("cg-tabla").innerHTML = filas.map(([t, tds]) => `<tr><th class="py-space-sm pr-space-md align-top font-body-md text-body-md font-normal text-on-surface-variant">${t}</th>${tds}</tr>`).join("");
    $("cg-textos").innerHTML = (CG.textos || []).map((x) => `<li class="flex items-start gap-space-xs font-body-md text-body-md text-on-surface">
      <span class="material-symbols-outlined text-base text-primary-container mt-0.5">chevron_right</span><span>${esc(x)}</span></li>`).join("");
    const avisos = CG.avisos || [];
    $("cg-avisos").classList.toggle("hidden", !avisos.length);
    $("cg-avisos").classList.toggle("flex", !!avisos.length);
    $("cg-avisos-txt").innerHTML = avisos.map((x) => `<p>${esc(x)}</p>`).join("");

    $("cg-pot-sub").textContent = "Según el tamaño del cambio del promedio (hacia arriba o hacia abajo)."
      + (P.b.n === act.n ? " El camino B usa las mismas unidades por muestra que el plan actual: su curva es la misma." : "");
    const nombres = { actual: `Actual (${planTxt(act)})`, a: P.a ? `A: ${planTxt(P.a)}` : "", b: `B: ${planTxt(P.b)}` };
    const colores = { actual: "#70787c", a: "#0f4c5c", b: "#b45309" };
    const orden = ["actual", "a", "b"].filter((c) => CG.curva_potencia.series[c]);
    GRAF.curvas($("graf-potencia"), orden.map((c) => ({ nombre: nombres[c], x: CG.curva_potencia.cambios, y: CG.curva_potencia.series[c],
      color: colores[c], guion: c === "actual" ? "dash" : "solid" })), {
      alto: 360, leyendaAbajo: true, rangoY: [0, 1.04],
      tituloX: `Cambio del promedio${V.unidad ? ` (${V.unidad})` : ""}`, tituloY: "Probabilidad de detectar", tickY: ".0%",
      etiquetaX: "cambio", etiquetaY: "potencia", formatoX: ":.2f", formatoY: ":.1%", refs: [{ x: CG.cambio, color: "#ba1a1a" }],
    });
    GRAF.curvas($("graf-acumulada"), orden.map((c) => ({ nombre: nombres[c], x: CG.curva_acumulada.horas, y: CG.curva_acumulada.series[c],
      color: colores[c], guion: c === "actual" ? "dash" : "solid" })), {
      alto: 360, leyendaAbajo: true, rangoY: [0, 1.04],
      tituloX: "Horas desde el cambio", tituloY: "Probabilidad de haber detectado", tickY: ".0%",
      etiquetaX: "horas", etiquetaY: "probabilidad", formatoX: ":.2f", formatoY: ":.1%", refs: [{ x: T, color: "#ba1a1a" }],
    });
  }

  function usarCamino(clave) {
    const p = CG && CG.planes[clave];
    if (!p) return;
    $("pl-n").value = p.n;
    $("pl-f").value = Math.round(p.frecuencia_min);
    marcarChips();
    programar();
    $("pl-form").scrollIntoView({ behavior: "smooth", block: "start" });
    toast(`Plan propuesto: ${planTxt(p)}. Revisa la comparación y pulsa «Guardar este plan» para aplicarlo.`);
  }

  // ------------------------------------------------------------------ Inicio
  async function iniciar(ctx) {
    if (!ctx.variable) return;
    V = ctx.variable;
    adaptarAVariable();
    ponerControles();
    document.querySelectorAll("[data-paso-n]").forEach((b) => (b.onclick = () => {
      $("pl-n").value = Math.max(1, (+$("pl-n").value || 1) + +b.dataset.pasoN);
      programar();
    }));
    document.querySelectorAll("#pl-chips button").forEach((b) => (b.onclick = () => { $("pl-f").value = b.dataset.min; marcarChips(); programar(); }));
    $("pl-f").addEventListener("input", () => { marcarChips(); programar(); });
    document.querySelectorAll('input[name="pl-k"]').forEach((r) => r.addEventListener("change", () => { $("pl-k-otro").value = ""; programar(); }));
    $("pl-k-otro").addEventListener("input", () => {
      if ($("pl-k-otro").value) document.querySelectorAll('input[name="pl-k"]').forEach((r) => (r.checked = false));
      programar();
    });
    $("pl-sigma").addEventListener("input", () => { document.querySelector('input[name="pl-sigma-modo"][value="fija"]').checked = true; programar(); });
    document.querySelectorAll('input[name="pl-sigma-modo"]').forEach((r) => r.addEventListener("change", programar));
    ["pl-n", "pl-delta", "pl-c0", "pl-c1", "p-comparar"].forEach((id) => $(id).addEventListener("input", programar));
    document.querySelectorAll("[data-eje]").forEach((b) => (b.onclick = () => { eje = b.dataset.eje; consultar(); }));
    $("pl-tecnico").addEventListener("toggle", () => { if ($("pl-tecnico").open) consultar(); });
    $("pl-form").addEventListener("submit", (e) => e.preventDefault());
    $("pl-guardar").onclick = () => guardar(false);
    $("pl-restaurar").onclick = () => { ponerControles(); $("pl-c0").value = ""; $("pl-c1").value = ""; consultar(); };
    $("btn-simular").onclick = simular;
    // Carga muestral objetivo (solo mediciones)
    $("cg-contenido").classList.toggle("hidden", esAtrib());
    $("cg-no-aplica").classList.toggle("hidden", !esAtrib());
    ["cg-objetivo", "cg-cambio", "cg-m"].forEach((id) => $(id).addEventListener("input", programarCarga));
    $("cg-horizonte").addEventListener("input", () => { horizonteManual = $("cg-horizonte").value.trim() !== ""; programarCarga(); });
    document.querySelectorAll("[data-usar]").forEach((b) => (b.onclick = () => usarCamino(b.dataset.usar)));
    document.querySelectorAll('input[name="pl-sigma-modo"]').forEach((r) => r.addEventListener("change", programarCarga));
    $("pl-sigma").addEventListener("input", programarCarga);
    await consultar();
    await consultarCarga();
  }

  CEP.arrancar(iniciar);
})();
