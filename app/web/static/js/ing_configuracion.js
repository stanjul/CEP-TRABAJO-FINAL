/* =========================================================================
 * ing_configuracion.js — especificaciones, muestreo, límites, reglas activas por variable,
 * turnos y el historial de cambios (versión + SHA-256).
 * API: GET/PATCH /variables/{id}, /variables/{id}/historial, /variables/{id}/carta, /reglas, /ajustes/turnos
 * ========================================================================= */
(function () {
  "use strict";
  const { api, fmt, pct, esc, toast, fechaHora, fecha, hora } = CEP;
  const $ = (id) => document.getElementById(id);
  const POR_PAGINA = 10;
  let V, original, CATALOGO, PRESETS, reglasEdit = [], historial = [], pagina = 1, turnos = [];

  const NUMERICOS = ["lei", "objetivo", "les", "n", "frecuencia_min", "k_sigma", "decimales"];

  function leerFormulario() {
    const datos = {};
    document.querySelectorAll("[data-campo-config]").forEach((el) => {
      const c = el.dataset.campoConfig;
      if (NUMERICOS.includes(c)) datos[c] = el.value === "" ? null : +el.value;
      else datos[c] = el.value;
    });
    datos.reglas = [...reglasEdit];
    return datos;
  }

  function cambios() {
    const d = leerFormulario();
    return Object.keys(d).filter((k) => JSON.stringify(d[k]) !== JSON.stringify(k === "reglas" ? [...original.reglas] : original[k]));
  }

  function actualizarBoton() {
    const c = cambios();
    $("btn-guardar").disabled = !c.length;
    $("btn-guardar-txt").textContent = c.length ? `Guardar Nueva Revisión (v${V.version + 1}) · ${c.length} cambio(s)` : "Sin cambios pendientes";
    pintarVentana();
    pintarAyudas();
  }

  // ------------------------------------------------------------------ Pintado
  function pintarFormulario() {
    document.querySelectorAll("[data-campo-config]").forEach((el) => {
      const v = original[el.dataset.campoConfig];
      el.value = v === null || v === undefined ? "" : v;
      if (el.dataset.estructural !== undefined) el.disabled = V.fase === "II";
    });
    document.querySelectorAll("[data-unidad]").forEach((s) => (s.textContent = V.unidad));
    $("b-bloqueo").classList.toggle("hidden", V.fase !== "II");
    reglasEdit = [...original.reglas];
  }

  function pintarAyudas() {
    const d = leerFormulario();
    $("b-n-txt").textContent = CEP.esAtributos(V) ? "tamaño de muestra" : d.tipo_carta === "imr" ? "individuales (n = 1)" : `${d.n} mediciones por subgrupo`;
    $("b-frec-txt").textContent = `${fmt(d.frecuencia_min * 60, 0)} s por ciclo · ${fmt(60 / d.frecuencia_min, 2)} subgrupos/h`;
    const z = d.k_sigma;
    const Phi = (x) => { const t = 1 / (1 + 0.2316419 * Math.abs(x)); const p = 1 - 0.3989423 * Math.exp(-x * x / 2) * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274)))); return x >= 0 ? p : 1 - p; };
    $("b-k-txt").textContent = `α = ${pct(2 * (1 - Phi(z)), 3)} por punto`;
    const tol = d.lei !== null && d.les !== null ? d.les - d.lei : null;
    $("a-tol").textContent = tol === null ? "Unilateral" : `${fmt(tol, V.decimales)} ${V.unidad}`;
  }

  function pintarVentana() {
    const d = leerFormulario();
    const cont = $("a-ventana");
    if (d.lei === null || d.les === null || d.les <= d.lei) {
      cont.innerHTML = '<div class="flex-1 flex items-center justify-center bg-surface-container-low text-outline">Especificación unilateral o incompleta</div>';
      $("a-ventana-ejes").innerHTML = "";
      return;
    }
    const t = d.objetivo ?? (d.lei + d.les) / 2;
    const ancho = d.les - d.lei;
    cont.innerHTML = `<div class="bg-error-container text-on-error-container flex items-center justify-center" style="width:12%">&lt; LEI</div>
      <div class="bg-[#FEF3C7] text-[#B45309] flex items-center justify-center" style="width:8%">pre</div>
      <div class="flex-1 bg-secondary-container text-on-secondary-container flex items-center justify-center">Zona admisible (T = ${fmt(t, V.decimales)})</div>
      <div class="bg-[#FEF3C7] text-[#B45309] flex items-center justify-center" style="width:8%">pre</div>
      <div class="bg-error-container text-on-error-container flex items-center justify-center" style="width:12%">&gt; LES</div>`;
    $("a-ventana-ejes").innerHTML = `<span>LEI: ${fmt(d.lei, V.decimales)}</span><span>pre-alarma ±${fmt(0.85 * ancho / 2, V.decimales)}</span><span>LES: ${fmt(d.les, V.decimales)}</span>`;
  }

  async function pintarLimites() {
    const modo = V.fase === "II"
      ? [["radio_button_checked", "Límites fijos (Fase II congelada)", true], ["radio_button_unchecked", "Cálculo dinámico basal (Fase I)", false]]
      : [["radio_button_unchecked", "Límites fijos (Fase II congelada)", false], ["radio_button_checked", "Cálculo dinámico basal (Fase I)", true]];
    $("b-modo").innerHTML = modo.map(([ic, t, act]) => `<span class="flex items-center gap-1 px-space-sm py-1.5 rounded-lg font-label-sm text-label-sm ${act ? "bg-primary text-on-primary font-bold" : "bg-surface-container-low text-outline"}">
      <span class="material-symbols-outlined text-sm">${ic}</span>${t}</span>`).join("");
    try {
      const c = await api(`/variables/${V.id}/carta`);
      if (c.vacio) { $("b-limites").innerHTML = '<p class="font-body-sm text-body-sm text-outline">Sin datos: los límites se estiman al cargar subgrupos.</p>'; return; }
      const ult = (x) => (Array.isArray(x) ? x[x.length - 1] : x);
      const d = V.tipo_carta === "p" ? 4 : V.decimales + 1;
      $("b-limites").innerHTML = Object.entries(c.cartas).map(([k, s]) => `<div class="p-space-sm rounded-lg border border-outline-variant/60 flex flex-col gap-1">
        <div class="flex items-center justify-between"><span class="font-label-md text-label-md font-bold">Carta ${esc(s.nombre)}</span>
          <span class="px-1.5 py-0.5 rounded font-label-sm text-label-sm ${V.fase === "II" ? "bg-secondary-container text-on-secondary-container" : "bg-surface-container text-outline"}">${V.fase === "II" ? "Vigente" : "Provisional"}</span></div>
        <div class="grid grid-cols-3 text-center font-label-md text-label-md">
          <div><span class="block font-label-sm text-label-sm text-outline">LCS</span><b class="text-error">${fmt(ult(s.lcs), d)}</b></div>
          <div><span class="block font-label-sm text-label-sm text-outline">LC</span><b class="text-primary">${fmt(ult(s.lc), d)}</b></div>
          <div><span class="block font-label-sm text-label-sm text-outline">LCI</span><b class="text-error">${fmt(ult(s.lci), d)}</b></div></div></div>`).join("");
    } catch (e) { $("b-limites").innerHTML = `<p class="text-error font-body-sm">${esc(e.message)}</p>`; }
  }

  function pintarReglas() {
    const sev = { critica: ["dangerous", "Crítica", "text-error"], advertencia: ["warning", "Advertencia", "text-[#B45309]"], alerta: ["info", "Alerta", "text-primary"] };
    $("tabla-reglas").innerHTML = CATALOGO.map((r) => {
      const activa = reglasEdit.includes(r.id);
      const [ic, t, col] = sev[r.severidad];
      return `<tr class="${activa ? "" : "opacity-60"}">
        <td class="py-2 px-space-sm"><span class="font-label-md text-label-md font-bold text-on-surface">${r.id}</span><span class="block font-body-sm text-body-sm text-outline">${esc(r.nombre)}</span></td>
        <td class="py-2 px-space-sm font-body-sm text-body-sm">${esc(r.condicion)}</td>
        <td class="py-2 px-space-sm text-right font-label-md text-label-md">${pct(r.alfa_aprox, 2)}</td>
        <td class="py-2 px-space-sm"><span class="flex items-center gap-1 font-label-sm text-label-sm font-bold ${col}"><span class="material-symbols-outlined text-sm">${ic}</span>${t}</span></td>
        <td class="py-2 px-space-sm text-center"><button class="px-space-sm py-1 rounded font-label-sm text-label-sm font-bold ${activa ? "bg-secondary text-on-secondary" : "bg-surface-container text-outline"}" data-regla="${r.id}" type="button">${activa ? "ACTIVADA" : "DESACTIVADA"}</button></td></tr>`;
    }).join("");
    $("tabla-reglas").querySelectorAll("[data-regla]").forEach((b) => (b.onclick = () => {
      const id = b.dataset.regla;
      reglasEdit = reglasEdit.includes(id) ? reglasEdit.filter((x) => x !== id) : [...reglasEdit, id];
      pintarReglas();
      actualizarBoton();
    }));
    const n = reglasEdit.length;
    $("c-sensibilidad").textContent = `${n >= 7 ? "ALTA" : n >= 4 ? "MEDIA" : "BAJA"} (${n}/${CATALOGO.length} activas)`;
  }

  function pintarVersion() {
    $("ctx-proceso").textContent = `${V.proceso.planta || ""} — ${V.proceso.nombre}`;
    $("ctx-variable").textContent = `Variable: ${V.nombre} (${V.unidad})`;
    $("rev-version").textContent = `REV v${V.version}`;
    $("rev-fase").textContent = V.fase === "II" ? "Límites congelados" : "Fase I (estimación)";
    $("rev-fase").className = `px-space-xs py-0.5 rounded font-label-sm text-label-sm font-bold ${V.fase === "II" ? "bg-secondary text-on-secondary" : "bg-[#FEF3C7] text-[#B45309]"}`;
    const lc = V.limites_congelados;
    $("rev-detalle").textContent = lc ? `Límites vigentes desde ${fechaHora(lc.creado)} · ${lc.m_usados} subgrupos · por ${lc.usuario}` : "Sin límites congelados.";
    $("rev-hash").textContent = `${V.hash.slice(0, 24)}…${V.hash.slice(-6)}`;
    $("rev-hash").title = V.hash;
  }

  // ------------------------------------------------------------------ Historial
  async function cargarHistorial() {
    const q = new URLSearchParams();
    if ($("h-parametro").value) q.set("parametro", $("h-parametro").value);
    if ($("h-texto").value) q.set("texto", $("h-texto").value);
    historial = await api(`/variables/${V.id}/historial?${q}`);
    pintarHistorial();
  }

  function corto(t) {
    if (t === null || t === undefined) return '<span class="text-outline">—</span>';
    const s = String(t);
    return s.length > 60 ? `<span title="${esc(s)}">${esc(s.slice(0, 60))}…</span>` : esc(s);
  }

  function pintarHistorial() {
    const paginas = Math.max(1, Math.ceil(historial.length / POR_PAGINA));
    pagina = Math.min(pagina, paginas);
    const vis = historial.slice((pagina - 1) * POR_PAGINA, pagina * POR_PAGINA);
    $("tabla-historial").innerHTML = vis.map((h) => `<tr class="hover:bg-surface-container-low">
      <td class="py-2 px-space-sm font-label-sm text-label-sm whitespace-nowrap">${fecha(h.fecha)}<span class="block text-outline">${hora(h.fecha, true)}</span></td>
      <td class="py-2 px-space-sm font-body-sm text-body-sm font-semibold">${esc(h.usuario)}</td>
      <td class="py-2 px-space-sm"><span class="px-1.5 py-0.5 rounded bg-surface-container font-label-sm text-label-sm">${esc(h.parametro)}</span></td>
      <td class="py-2 px-space-sm font-label-sm text-label-sm text-error">${corto(h.valor_anterior)}</td>
      <td class="py-2 px-space-sm font-label-sm text-label-sm text-secondary font-bold">${corto(h.valor_nuevo)}</td>
      <td class="py-2 px-space-sm font-body-sm text-body-sm">${esc(h.justificacion || "—")}</td>
      <td class="py-2 px-space-sm font-label-sm text-label-sm"><span class="flex items-center gap-1 text-secondary"><span class="material-symbols-outlined text-sm">verified</span>v${h.version}</span>
        <span class="text-outline" title="${esc(h.hash)}">#${esc(h.hash.slice(0, 7))}</span></td></tr>`).join("")
      || '<tr><td class="py-space-md px-space-sm text-outline" colspan="7">Sin registros.</td></tr>';
    $("h-resumen").textContent = `Mostrando ${vis.length} de ${historial.length} registros`;
    $("h-pag").textContent = `${pagina} / ${paginas}`;
  }

  function exportarHistorial() {
    const cab = ["fecha", "usuario", "parametro", "valor_anterior", "valor_nuevo", "justificacion", "version", "hash"];
    const csv = [cab.join(",")].concat(historial.map((h) => cab.map((c) => `"${String(h[c] ?? "").replace(/"/g, '""')}"`).join(","))).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv" }));
    a.download = `historial_variable_${V.id}.csv`;
    a.click();
  }

  // ------------------------------------------------------------------ Turnos
  const DIAS = ["L", "M", "X", "J", "V", "S", "D"];
  const DIAS_NOMBRE = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
  function pintarTurnos() {
    const inp = "h-8 rounded border-outline-variant font-label-sm text-label-sm";
    $("turnos").innerHTML = turnos.map((t, i) => {
      const dias = t.dias || [0, 1, 2, 3, 4, 5, 6];
      return `<div class="p-space-sm rounded-lg bg-surface-container-low flex flex-col gap-space-xs">
      <div class="flex items-center gap-1">
        <input class="${inp} flex-1 min-w-0 font-semibold" data-t="${i}" data-c="nombre" value="${esc(t.nombre)}" aria-label="Nombre del turno"/>
        <button class="text-error" data-borrar="${i}" title="Quitar este turno" type="button"><span class="material-symbols-outlined text-base">close</span></button></div>
      <div class="flex items-center gap-1 font-label-sm text-label-sm text-on-surface-variant">
        <input class="${inp} w-[4.5rem]" data-t="${i}" data-c="inicio" maxlength="5" placeholder="HH:MM" title="Inicio (HH:MM, 24 h)" type="text" value="${t.inicio}"/> a
        <input class="${inp} w-[4.5rem]" data-t="${i}" data-c="fin" maxlength="5" placeholder="HH:MM" title="Fin (HH:MM, 24 h)" type="text" value="${t.fin}"/></div>
      <div class="flex gap-0.5" role="group" aria-label="Días de trabajo">${DIAS.map((d, k) => `<button class="w-7 h-7 rounded font-label-sm text-label-sm font-bold ${dias.includes(k) ? "bg-primary-container text-on-primary" : "bg-surface-container-lowest text-outline"}"
        data-t="${i}" data-dia="${k}" aria-pressed="${dias.includes(k)}" title="${DIAS_NOMBRE[k]}" type="button">${d}</button>`).join("")}</div>
      <label class="flex flex-wrap items-center gap-1 font-label-sm text-label-sm text-on-surface-variant">Primera muestra a los
        <input class="${inp} w-14" data-t="${i}" data-c="arranque_min" inputmode="numeric" placeholder="auto" title="Minutos después del inicio del turno. Vacío (auto): un intervalo de muestreo de cada variable." type="text" value="${t.arranque_min ?? ""}"/> min</label>
    </div>`;
    }).join("");
    $("turnos").querySelectorAll("input").forEach((el) => (el.oninput = () => {
      const t = turnos[+el.dataset.t], c = el.dataset.c;
      t[c] = c === "arranque_min" ? (el.value.trim() === "" ? null : parseInt(el.value, 10)) : el.value;
    }));
    $("turnos").querySelectorAll("[data-dia]").forEach((b) => (b.onclick = () => {
      const t = turnos[+b.dataset.t], k = +b.dataset.dia;
      const dias = new Set(t.dias || [0, 1, 2, 3, 4, 5, 6]);
      if (dias.has(k)) dias.delete(k); else dias.add(k);
      if (!dias.size) return toast("Un turno necesita al menos un día de trabajo.", "aviso");
      t.dias = [...dias].sort();
      pintarTurnos();
    }));
    $("turnos").querySelectorAll("[data-borrar]").forEach((b) => (b.onclick = () => { turnos.splice(+b.dataset.borrar, 1); pintarTurnos(); }));
  }

  // Turno actual (iniciar / terminar) e historial de turnos reales.
  let estadoTurno = null;
  const hm = (iso) => (iso ? String(iso).slice(11, 16) : "");
  const diaMes = (iso) => (iso ? `${String(iso).slice(8, 10)}/${String(iso).slice(5, 7)}` : "");
  async function pintarTurnoActual() {
    try { estadoTurno = await api("/turnos/estado"); } catch (e) { return; }
    const ab = estadoTurno.abierto, prox = estadoTurno.proximo;
    $("turno-actual").textContent = ab ? `#${ab.numero} · ${ab.nombre}, desde las ${hm(ab.inicio)} hasta las ${hm(ab.fin_programado)}`
      : `Fuera de turno${prox ? ` · próximo: ${prox.nombre}, ${diaMes(prox.desde)} a las ${hm(prox.desde)}` : ""}`;
    $("btn-turno-accion-texto").textContent = ab ? "Terminar turno" : "Iniciar turno";
    $("btn-turno-accion-icono").textContent = ab ? "stop_circle" : "play_circle";
    const hist = await api("/turnos?limite=15").catch(() => []);
    $("turnos-historial").innerHTML = hist.length ? hist.map((t) => `<li class="py-1.5 flex flex-col font-label-sm text-label-sm">
      <span class="font-semibold text-on-surface">#${t.numero} · ${esc(t.nombre)} · ${diaMes(t.inicio)} ${hm(t.inicio)}–${t.fin ? hm(t.fin) : "en curso"}</span>
      <span class="text-on-surface-variant">${t.muestras} ${t.muestras === 1 ? "muestra" : "muestras"}${t.fin ? ` · ${t.cierre === "manual" ? `terminado a mano por ${esc(t.cerrado_por || "—")}` : "terminó a su hora"}` : ""}${t.abierto_por && t.abierto_por !== "Automático" ? ` · iniciado por ${esc(t.abierto_por)}` : ""}</span></li>`).join("")
      : '<li class="py-1.5 font-label-sm text-label-sm text-on-surface-variant">Todavía no hay turnos registrados.</li>';
  }
  async function accionTurno() {
    const usuario = await CEP.exigirUsuario();
    if (!usuario || !estadoTurno) return;
    const ab = estadoTurno.abierto;
    try {
      if (ab) {
        const ok = await CEP.modal({ titulo: `Terminar el turno #${ab.numero} · ${ab.nombre}`,
          texto: "La cuenta regresiva de las muestras se detiene hasta el próximo turno. Queda registrado quién lo terminó y a qué hora.",
          aceptar: "Terminar turno", peligro: true });
        if (!ok) return;
        await api("/turnos/terminar", { json: { usuario } });
        toast(`Turno #${ab.numero} terminado.`);
      } else {
        const opciones = estadoTurno.programados.map((t) => [t.nombre, `${t.nombre} (${t.inicio} a ${t.fin})`]);
        const r = await CEP.modal({ titulo: "Iniciar un turno", texto: "Úsalo cuando la línea trabaja fuera de la hora programada.",
          campos: [{ nombre: "nombre", etiqueta: "¿Qué turno es?", tipo: "select", opciones,
                     valor: estadoTurno.proximo ? estadoTurno.proximo.nombre : opciones[0][0] }],
          aceptar: "Iniciar turno" });
        if (!r) return;
        const t = await api("/turnos/iniciar", { json: { nombre: r.nombre, usuario } });
        toast(`Turno #${t.numero} · ${t.nombre} iniciado.`);
      }
      await pintarTurnoActual();
      CEP.pintarEstado(V);
    } catch (e) { toast(e.message, "error"); }
  }

  // ------------------------------------------------------------------ Guardar
  async function guardar() {
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return;
    const lista = cambios();
    const d = leerFormulario();
    const r = await CEP.modal({
      titulo: `Guardar revisión v${V.version + 1}`,
      texto: `Parámetros modificados: <b>${lista.map(esc).join(", ")}</b>. La justificación queda en el historial.`,
      campos: [{ nombre: "justificacion", etiqueta: "Justificación del cambio", tipo: "textarea", requerido: true }],
    });
    if (!r) return;
    const cuerpo = { usuario, justificacion: r.justificacion, borrar: [] };
    lista.forEach((k) => {
      if (["lei", "objetivo", "les"].includes(k) && d[k] === null) cuerpo.borrar.push(k);
      else cuerpo[k] = d[k];
    });
    try {
      const res = await api(`/variables/${V.id}`, { method: "PATCH", json: cuerpo });
      toast(`Revisión v${res.variable.version} guardada (${res.cambios.length} cambio(s)).`);
      setTimeout(() => location.reload(), 700);
    } catch (e) { toast(e.message, "error"); }
  }

  async function iniciar(ctx) {
    if (!ctx.variable) return;
    V = await api(`/variables/${ctx.variable.id}`);
    original = { ...V };
    const rg = await api("/reglas");
    CATALOGO = rg.catalogo;
    PRESETS = rg.presets;
    pintarVersion();
    pintarFormulario();
    pintarReglas();
    actualizarBoton();
    pintarLimites();
    document.querySelectorAll("[data-campo-config]").forEach((el) => el.addEventListener("input", actualizarBoton));
    document.querySelectorAll("[data-preset]").forEach((b) => (b.onclick = () => { reglasEdit = [...PRESETS[b.dataset.preset]]; pintarReglas(); actualizarBoton(); }));
    $("btn-guardar").onclick = guardar;
    $("btn-exportar").onclick = exportarHistorial;
    $("h-parametro").onchange = () => { pagina = 1; cargarHistorial(); };
    let t;
    $("h-texto").oninput = () => { clearTimeout(t); t = setTimeout(() => { pagina = 1; cargarHistorial(); }, 300); };
    $("h-ant").onclick = () => { if (pagina > 1) { pagina--; pintarHistorial(); } };
    $("h-sig").onclick = () => { pagina++; pintarHistorial(); };
    await cargarHistorial();
    turnos = await api("/ajustes/turnos");
    pintarTurnos();
    $("btn-turno-mas").onclick = () => {
      turnos.push({ nombre: `Turno ${turnos.length + 1}`, inicio: "00:00", fin: "06:00", dias: [0, 1, 2, 3, 4, 5, 6], arranque_min: null });
      pintarTurnos();
    };
    $("btn-turnos").onclick = async () => {
      try {
        turnos = await api("/ajustes/turnos", { method: "PUT", json: turnos });
        pintarTurnos();
        toast("Turnos guardados.");
        await pintarTurnoActual();
        CEP.pintarEstado(V);
      } catch (e) { toast(e.message, "error"); }
    };
    $("btn-turno-accion").onclick = accionTurno;
    pintarTurnoActual();
    api("/ajustes/modo-demo").then((r) => ($("modo-demo").checked = r.activo)).catch(() => {});
    $("modo-demo").onchange = async () => {
      try {
        const r = await api("/ajustes/modo-demo", { method: "PUT", json: { activo: $("modo-demo").checked } });
        toast(r.activo ? "Modo demostración activado." : "Modo demostración desactivado.");
      } catch (e) { toast(e.message, "error"); $("modo-demo").checked = !$("modo-demo").checked; }
    };
  }

  CEP.arrancar(iniciar);
})();
