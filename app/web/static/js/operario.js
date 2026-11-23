/* =========================================================================
 * operario.js — Vista Operario "Registrar muestra" (rediseño 2026-11, Fase C).
 *  - Estado del proceso en palabras y cuenta regresiva a la próxima muestra.
 *  - Captura de la muestra con resultado en vivo y aviso si un valor parece mal escrito.
 *  - Deshacer el último registro durante los primeros minutos.
 *  - Gráfica simple de las últimas 25 muestras, alertas y resumen del turno.
 * API: GET /variables/{id}/operario (cada 30 s), POST /variables/{id}/subgrupos,
 *      POST /variables/{id}/deshacer-ultimo, GET /variables/{id}/simular-valores
 * ========================================================================= */
(function () {
  "use strict";
  const { api, fmt, pct, hora, esc, toast } = CEP;
  const $ = (id) => document.getElementById(id);

  let V = null;               // variable activa
  let R = null;               // último resumen recibido
  let proxima = null;         // Date de la próxima muestra
  let finDeshacer = null;     // Date hasta la que se puede deshacer
  let ultimosValores = null;  // lo último que se guardó (para corregirlo si se deshace)
  let alarmasPorId = {};

  const num = (t) => (String(t ?? "").trim() === "" ? NaN : parseFloat(String(t).replace(",", ".")));
  const attr = () => CEP.esAtributos(V);

  // ------------------------------------------------------------------ Formulario
  function construirFormulario() {
    const grupo = $("sample-inputs-group");
    const campo = (id, etiqueta, unidad, extra = "") => `
      <label class="flex items-center gap-space-sm">
        <span class="w-28 font-body-md text-body-md font-semibold text-on-surface">${etiqueta}</span>
        <input class="h-14 flex-1 min-w-0 rounded-lg border-outline-variant font-headline-sm text-headline-sm text-right font-bold text-on-surface"
          id="${id}" inputmode="decimal" type="text" ${extra}/>
        <span class="w-16 font-body-md text-body-md text-on-surface-variant">${esc(unidad)}</span>
      </label>`;
    const t = V.tipo_carta;
    if (attr()) {
      let html = "";
      if (t !== "c") html += campo("val-tamano", "Revisadas", "unidades", `value="${V.n}" ${t === "np" ? "readonly" : ""}`);
      html += campo("val-conteo", t === "p" || t === "np" ? "Defectuosas" : "Fallas", t === "p" || t === "np" ? "unidades" : "fallas");
      grupo.innerHTML = html;
      $("cap-instruccion").textContent = {
        p: "Revisa las unidades de la muestra y anota cuántas salieron defectuosas.",
        np: `Revisa ${V.n} unidades y anota cuántas salieron defectuosas.`,
        c: "Revisa la muestra y anota cuántas fallas encontraste.",
        u: "Anota cuántas unidades revisaste y cuántas fallas encontraste en total.",
      }[t];
    } else {
      const n = t === "imr" ? 1 : V.n;
      grupo.innerHTML = Array.from({ length: n }, (_, i) => campo(`val-${i + 1}`, n === 1 ? "Valor" : `Unidad ${i + 1}`, V.unidad)).join("");
      $("cap-instruccion").textContent = n === 1
        ? `Mide una unidad y escribe el valor${V.unidad ? ` en ${V.unidad}` : ""}.`
        : `Toma ${n} unidades seguidas, mídelas y escribe cada valor${V.unidad ? ` en ${V.unidad}` : ""}.`;
    }
    const inputs = [...grupo.querySelectorAll("input")];
    inputs.forEach((inp, i) => {
      inp.addEventListener("input", recalcular);
      inp.addEventListener("focus", function () { this.select(); });
      inp.addEventListener("keydown", (e) => {  // Enter pasa al siguiente campo (teclado numérico / guantes)
        if (e.key === "Enter" && i < inputs.length - 1) { e.preventDefault(); inputs[i + 1].focus(); }
      });
    });
  }

  function leerValores() {
    if (attr()) return { conteo: num($("val-conteo").value), tamano: $("val-tamano") ? num($("val-tamano").value) : null };
    return { valores: [...$("sample-inputs-group").querySelectorAll("input")].map((i) => num(i.value)) };
  }

  /** Límites vigentes de la carta de posición (último valor si varían por muestra). */
  function limites() {
    const c = R && R.carta && R.carta.cartas && Object.values(R.carta.cartas)[0];
    if (!c) return null;
    const u = (x) => (Array.isArray(x) ? x[x.length - 1] : x);
    return { lc: u(c.lc), lcs: u(c.lcs), lci: u(c.lci) };
  }

  /** Resultado en vivo mientras el operario escribe. */
  function recalcular() {
    const v = leerValores();
    const caja = $("cap-vivo");
    const mostrar = (icono, texto) => {
      caja.classList.remove("hidden"); caja.classList.add("flex");
      $("cap-vivo-icono").textContent = icono;
      $("cap-vivo-texto").innerHTML = texto;
    };
    const ocultar = () => { caja.classList.add("hidden"); caja.classList.remove("flex"); };
    const lim = limites();
    if (attr()) {
      if (Number.isNaN(v.conteo)) return ocultar();
      const t = V.tipo_carta;
      const base = t === "c" ? 1 : t === "np" ? 1 : v.tamano;
      if (!base || Number.isNaN(base)) return ocultar();
      const x = v.conteo / base;
      const fuera = lim && (x > lim.lcs || x < lim.lci);
      const desc = OPER.valorCarta(V, x);
      return mostrar(fuera ? "warning" : "check_circle", fuera
        ? `Esta muestra da <b>${desc}</b>: está <b>fuera de lo normal</b>. Al guardarla se generará una alerta.`
        : `Esta muestra da <b>${desc}</b>${lim ? ` (lo habitual es ${OPER.valorCarta(V, lim.lc)})` : ""}.`);
    }
    const xs = v.valores;
    if (xs.some(Number.isNaN)) return ocultar();
    const media = xs.reduce((a, b) => a + b, 0) / xs.length;
    const d = V.decimales;
    const fueraEspec = xs.filter((x) => (V.lei !== null && x < V.lei) || (V.les !== null && x > V.les)).length;
    const fueraNormal = lim && (media > lim.lcs || media < lim.lci);
    const nombre = xs.length === 1 ? "Valor" : "Promedio de la muestra";
    let texto = `${nombre}: <b>${fmt(media, d + 1)} ${esc(V.unidad)}</b>. `;
    texto += fueraNormal ? "Está <b>fuera de lo normal</b>: al guardarla se generará una alerta." : lim ? "Está dentro de lo normal." : "";
    if (fueraEspec) texto += ` <b>${fueraEspec} de ${xs.length}</b> ${fueraEspec === 1 ? "unidad está" : "unidades están"} fuera de lo aceptado.`;
    mostrar(fueraNormal || fueraEspec ? "warning" : "check_circle", texto);
  }

  /** Valores que parecen mal escritos: a más de 5σ del centro habitual o muy lejos de la especificación. */
  function sospechosos(valores) {
    const r = R && R.rango_habitual;
    const tol = V.lei !== null && V.les !== null ? V.les - V.lei : null;
    return valores.filter((x) => {
      if (r && Math.abs(x - r.centro) > 5 * r.sigma) return true;
      if (tol !== null && (x < V.lei - tol || x > V.les + tol)) return true;
      return false;
    });
  }

  function error(texto) {
    $("cap-error").textContent = texto || "";
    $("cap-error").classList.toggle("hidden", !texto);
  }

  async function registrar(e) {
    e.preventDefault();
    error("");
    const datos = leerValores();
    if (datos.valores && datos.valores.some(Number.isNaN)) return error("Completa todos los valores con números (puedes usar coma decimal).");
    if (attr() && Number.isNaN(datos.conteo)) return error("Escribe cuántas encontraste (si no hubo ninguna, escribe 0).");
    if (attr() && datos.tamano !== null && (Number.isNaN(datos.tamano) || datos.tamano <= 0)) return error("Escribe cuántas unidades revisaste.");
    if (datos.valores) {
      const raros = sospechosos(datos.valores);
      if (raros.length) {
        const r = R.rango_habitual;
        const ok = await CEP.modal({
          titulo: "¿Están bien escritos estos valores?",
          texto: `${raros.map((x) => `<b>${fmt(x, V.decimales)} ${esc(V.unidad)}</b>`).join(", ")} ${raros.length === 1 ? "está" : "están"} muy lejos de lo habitual`
            + (r ? ` (alrededor de ${fmt(r.centro, V.decimales)} ${esc(V.unidad)})` : "") + ". Revisa si falta una coma o sobra un número.",
          aceptar: "Sí, están bien", cancelar: "Corregir",
        });
        if (!ok) return;
      }
    }
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    const btn = $("btn-submit-subgroup");
    btn.disabled = true;
    try {
      const r = await api(`/variables/${V.id}/subgrupos`, { json: { ...datos, usuario, operario: usuario, lote: $("cap-lote").value || null } });
      ultimosValores = { ...datos, lote: $("cap-lote").value };
      const nuevas = r.alarmas_nuevas;
      if (nuevas.length) toast(`Muestra #${r.subgrupo.numero} guardada. Atención: ${nuevas[0].explicacion}`, "error");
      else toast(`Muestra #${r.subgrupo.numero} guardada.`);
      $("sample-inputs-group").querySelectorAll("input:not([readonly])").forEach((i) => (i.value = ""));
      if ($("val-tamano") && V.tipo_carta !== "np") $("val-tamano").value = V.n;
      recalcular();
      await refrescar();
      CEP.pintarEstado(V);
      $("sample-inputs-group").querySelector("input:not([readonly])")?.focus();
    } catch (err) {
      error(err.message);
    } finally {
      btn.disabled = false;
    }
  }

  async function deshacer() {
    const u = R.ultimo_subgrupo;
    const r = await CEP.modal({
      titulo: `Deshacer la muestra #${u.numero}`,
      texto: "La muestra deja de contar en la gráfica y queda anotado que se anuló. Después puedes volver a cargarla bien.",
      campos: [{ nombre: "motivo", etiqueta: "¿Qué pasó? (opcional)", valor: "Error al escribir un valor" }],
      aceptar: "Deshacer muestra", peligro: true,
    });
    if (!r) return;
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    try {
      await api(`/variables/${V.id}/deshacer-ultimo`, { json: { usuario, motivo: r.motivo } });
      toast(`Se anuló la muestra #${u.numero}. Ya puedes cargarla de nuevo.`, "aviso");
      // Se dejan los valores anulados en el formulario para corregirlos sin volver a escribir todo.
      if (ultimosValores) {
        if (ultimosValores.valores) ultimosValores.valores.forEach((x, i) => { const inp = $(`val-${i + 1}`); if (inp) inp.value = String(x).replace(".", ","); });
        if (ultimosValores.conteo !== undefined) $("val-conteo").value = ultimosValores.conteo;
        if (ultimosValores.tamano && $("val-tamano")) $("val-tamano").value = ultimosValores.tamano;
        $("cap-lote").value = ultimosValores.lote || "";
        recalcular();
      }
      await refrescar();
      CEP.pintarEstado(V);
    } catch (e) { toast(e.message, "error"); }
  }

  async function simular() {
    try {
      const r = await api(`/variables/${V.id}/simular-valores?delta=${$("sel-delta").value}`);
      if (r.valores) r.valores.forEach((x, i) => { const inp = $(`val-${i + 1}`); if (inp) inp.value = String(x).replace(".", ","); });
      if (r.conteo !== undefined) { $("val-conteo").value = r.conteo; if ($("val-tamano") && r.tamano) $("val-tamano").value = r.tamano; }
      recalcular();
    } catch (e) { toast(e.message, "error"); }
  }

  // ------------------------------------------------------------------ Pintado
  function pintarAlarmas() {
    const vistas = new Map();
    [...R.alarmas_abiertas, ...R.alarmas_turno].forEach((a) => vistas.set(a.id, a));
    const todas = [...vistas.values()].sort((a, b) => (a.estado === "resuelta") - (b.estado === "resuelta") || b.id - a.id).slice(0, 6);
    alarmasPorId = Object.fromEntries(todas.map((a) => [a.id, a]));
    $("lista-alarmas").innerHTML = todas.length ? todas.map((a) => ALARMAS.tarjeta(a)).join("")
      : `<div class="p-space-md rounded-lg bg-surface-container-low flex items-center gap-space-sm">
          <span class="material-symbols-outlined text-[#15803D]">check_circle</span>
          <span class="font-body-md text-body-md text-on-surface-variant">No hubo alertas en este turno.</span></div>`;
    $("lista-alarmas").querySelectorAll("[data-registrar]").forEach((b) => (b.onclick = async () => {
      if (await ALARMAS.registrarCausa(alarmasPorId[b.dataset.registrar])) { await refrescar(); CEP.pintarEstado(V); }
    }));
  }

  function pintarTurno() {
    const t = R.turno;
    $("turno-titulo").textContent = `Este turno · ${t.nombre} (${t.inicio} a ${t.fin})`;
    const filas = [
      ["Muestras tomadas", `${t.subgrupos_tomados} de ${t.subgrupos_programados} programadas`],
      [attr() ? "Unidades buenas" : "Unidades dentro de lo aceptado",
        t.fraccion_conforme === null ? (attr() && !OPER.esP(V) ? "No aplica a conteos de fallas" : "Todavía sin datos") : pct(t.fraccion_conforme, 1)],
      ["Alertas", t.alarmas ? `${t.alarmas} (${t.alarmas_resueltas} resueltas)` : "Ninguna"],
      ["Quién registra", CEP.usuario() || "Sin identificar (toca tu nombre arriba a la derecha)"],
    ];
    $("turno-datos").innerHTML = filas.map(([a, b]) => `<div class="flex items-center justify-between gap-space-md py-space-sm">
      <dt class="text-on-surface-variant">${a}</dt><dd class="font-semibold text-on-surface text-right">${esc(b)}</dd></div>`).join("");
  }

  function pintarCaptura() {
    $("cap-titulo").textContent = `Registrar muestra #${R.proximo_numero}`;
    $("op-plan").textContent = `Muestra #${R.proximo_numero} · ${V.tipo_carta === "imr" ? "1 unidad" : attr() && V.tipo_carta === "c" ? "1 muestra" : `${V.n} unidades`} ${CEP.cadaCuanto(V.frecuencia_min)}`;
    $("demo").classList.toggle("hidden", !R.modo_demo);
    $("demo").classList.toggle("flex", !!R.modo_demo);
    finDeshacer = R.segundos_para_deshacer > 0 ? new Date(Date.now() + R.segundos_para_deshacer * 1000) : null;
  }

  // ------------------------------------------------------------------ Relojes
  const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  function tic() {
    if (proxima) {
      const seg = Math.round((proxima - Date.now()) / 1000);
      const el = $("spc-countdown");
      if (seg >= 0) {
        el.textContent = mmss(seg);
        el.className = "font-metric-display text-metric-display font-bold text-primary";
        $("aside-proxima").textContent = `Próxima muestra en ${mmss(seg)} (#${R.proximo_numero}).`;
      } else {
        el.textContent = "¡Ahora!";
        el.className = "font-metric-display text-metric-display font-bold text-error";
        $("aside-proxima").textContent = `La muestra #${R.proximo_numero} está atrasada ${mmss(-seg)}.`;
      }
    }
    const caja = $("deshacer");
    const resta = finDeshacer ? Math.round((finDeshacer - Date.now()) / 1000) : 0;
    caja.classList.toggle("hidden", resta <= 0);
    caja.classList.toggle("flex", resta > 0);
    if (resta > 0) $("deshacer-texto").textContent = `¿Te equivocaste en la muestra #${R.ultimo_subgrupo.numero}? Puedes deshacerla durante ${mmss(resta)}.`;
  }

  // ------------------------------------------------------------------ Ciclo
  async function refrescar() {
    R = await api(`/variables/${V.id}/operario`);
    V = R.variable;
    proxima = new Date(Date.now() + R.segundos_para_muestra * 1000);  // diferencia calculada en el servidor
    OPER.pintarEstado(R, V);
    const n = (R.carta.etiquetas || []).length;
    $("graf-titulo").textContent = n > 1 ? `Últimas ${n} muestras` : n === 1 ? "Primera muestra" : "Últimas muestras";
    OPER.graficar($("graf-1"), R, V, 300);
    $("resumen-ventana").innerHTML = OPER.htmlResumen(OPER.resumenVentana(R, V));
    pintarAlarmas();
    pintarTurno();
    pintarCaptura();
    $("aside-frecuencia").textContent = CEP.cadaCuanto(V.frecuencia_min);
    tic();
  }

  async function iniciar(ctx) {
    if (!ctx.variable) return;
    V = ctx.variable;
    construirFormulario();
    $("captura").addEventListener("submit", registrar);
    $("btn-simular").onclick = simular;
    $("btn-deshacer").onclick = deshacer;
    $("btn-problema").onclick = async () => { if (await ALARMAS.reportarEvento(V.id, "anomalia")) { await refrescar(); CEP.pintarEstado(V); } };
    await refrescar();
    setInterval(tic, 1000);
    setInterval(() => refrescar().catch(() => {}), 30000);
    if (location.hash === "#captura") setTimeout(() => $("sample-inputs-group").querySelector("input")?.focus(), 300);
  }

  CEP.arrancar(iniciar);
})();
