/* =========================================================================
 * comun.js — utilidades compartidas por todas las pantallas (JS vanilla).
 *
 *  CEP.api(ruta, opciones)      fetch a /api con manejo de errores (lanza Error con el detalle).
 *  CEP.arrancar(iniciar)        carga el contexto (procesos, variable activa, usuario) y llama a
 *                               iniciar(ctx) de la pantalla. ctx = {procesos, variable, proceso}.
 *  CEP.fmt / pct / fecha / hora formato de números y fechas (es-AR, cifras tabulares).
 *  CEP.toast(texto, tipo)       aviso flotante (ok | error | aviso).
 *  CEP.modal({...})             diálogo con formulario; devuelve una Promise con los valores.
 *  CEP.rellenar(raiz, datos)    completa los elementos [data-campo] con los datos.
 * ========================================================================= */
(function () {
  "use strict";

  const CLAVE_VAR = "cep.variable";
  const CLAVE_USUARIO = "cep.usuario";

  // ---------------------------------------------------------------- API
  async function api(ruta, opciones = {}) {
    const op = { headers: {}, ...opciones };
    if (op.json !== undefined) {
      op.body = JSON.stringify(op.json);
      op.headers["Content-Type"] = "application/json";
      op.method = op.method || "POST";
      delete op.json;
    }
    let r;
    try {
      r = await fetch("/api" + ruta, op);
    } catch (e) {
      marcarSync(false);
      throw new Error("Sin conexión con el servidor.");
    }
    marcarSync(true);
    const tipo = r.headers.get("content-type") || "";
    const cuerpo = tipo.includes("json") ? await r.json() : await r.blob();
    if (!r.ok) {
      let detalle = cuerpo && cuerpo.detail;
      if (Array.isArray(detalle)) detalle = detalle.map((d) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join(" · ");
      throw new Error(detalle || `Error ${r.status}`);
    }
    return cuerpo;
  }

  function marcarSync(ok) {
    const el = document.getElementById("hdr-sync");
    if (!el) return;
    el.className = "flex items-center gap-space-xs ml-space-xs px-space-xs py-0.5 rounded " + (ok ? "bg-secondary/30" : "bg-error/40");
    el.innerHTML = ok
      ? '<span class="w-2 h-2 rounded-full bg-secondary-fixed animate-pulse"></span><span class="font-label-sm text-label-sm text-secondary-fixed">Conectado</span>'
      : '<span class="w-2 h-2 rounded-full bg-error-container"></span><span class="font-label-sm text-label-sm text-error-container">Sin conexión</span>';
  }

  // ---------------------------------------------------------------- Formato
  const nf = (d) => new Intl.NumberFormat("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
  function fmt(x, d = 2) {
    if (x === null || x === undefined || Number.isNaN(x)) return "—";
    return nf(d).format(x);
  }
  function pct(x, d = 2) { return x === null || x === undefined ? "—" : fmt(100 * x, d) + "%"; }
  function fecha(iso) {
    if (!iso) return "—";
    const f = new Date(iso);
    return f.toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" });
  }
  function hora(iso, seg = false) {
    if (!iso) return "—";
    return new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", second: seg ? "2-digit" : undefined, hour12: false });
  }
  function fechaHora(iso) { return iso ? `${fecha(iso)} ${hora(iso)}` : "—"; }
  function esc(t) {
    return String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  /** Completa [data-campo="clave"] con datos[clave]; data-decimales y data-sufijo opcionales. */
  function rellenar(raiz, datos) {
    (raiz || document).querySelectorAll("[data-campo]").forEach((el) => {
      const clave = el.dataset.campo;
      if (!(clave in datos)) return;
      let v = datos[clave];
      if (typeof v === "number" && el.dataset.decimales !== undefined) v = fmt(v, +el.dataset.decimales);
      if (el.dataset.pct !== undefined && typeof datos[clave] === "number") v = pct(datos[clave], +(el.dataset.pct || 2));
      el.textContent = (v ?? "—") + (el.dataset.sufijo && v !== null && v !== undefined ? el.dataset.sufijo : "");
    });
  }

  // ---------------------------------------------------------------- Avisos y modales
  function toast(texto, tipo = "ok") {
    const caja = document.getElementById("cep-toasts");
    const estilos = {
      ok: "bg-secondary text-on-secondary",
      error: "bg-error text-on-error",
      aviso: "bg-[#FEF3C7] text-[#B45309] border border-[#B45309]",
    };
    const icono = { ok: "check_circle", error: "error", aviso: "warning" }[tipo] || "info";
    const el = document.createElement("div");
    el.className = `cep-toast max-w-md px-space-md py-space-sm rounded-lg shadow-md flex items-start gap-space-xs font-body-md text-body-md ${estilos[tipo] || estilos.ok}`;
    el.innerHTML = `<span class="material-symbols-outlined text-lg">${icono}</span><span>${esc(texto)}</span>`;
    caja.appendChild(el);
    setTimeout(() => el.remove(), tipo === "error" ? 7000 : 4000);
  }

  /**
   * Diálogo modal con campos. campos: [{nombre, etiqueta, tipo: "text"|"textarea"|"select"|"number",
   * valor, opciones:[[valor, texto]], requerido}]. Devuelve Promise<objeto|null>.
   */
  function modal({ titulo, texto = "", campos = [], aceptar = "Guardar", cancelar = "Cancelar", peligro = false, ancho = "max-w-lg" }) {
    return new Promise((resolver) => {
      const cont = document.getElementById("cep-modales");
      const fondo = document.createElement("div");
      fondo.className = "fixed inset-0 z-[60] bg-inverse-surface/50 flex items-center justify-center p-margin";
      const inputCls = "w-full h-12 px-space-md bg-surface-container-lowest border border-outline-variant rounded font-body-md text-body-md focus:outline-none focus:border-primary-container focus:ring-2 focus:ring-primary-container/30";
      const html = campos.map((c) => {
        const req = c.requerido ? "required" : "";
        let control;
        if (c.tipo === "textarea") control = `<textarea name="${c.nombre}" rows="3" ${req} class="${inputCls} h-auto py-space-sm">${esc(c.valor || "")}</textarea>`;
        else if (c.tipo === "select") control = `<select name="${c.nombre}" class="${inputCls}">${(c.opciones || []).map(([v, t]) => `<option value="${esc(v)}" ${v == c.valor ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>`;
        else control = `<input name="${c.nombre}" type="${c.tipo || "text"}" step="any" value="${esc(c.valor ?? "")}" ${req} class="${inputCls}"/>`;
        return `<label class="flex flex-col gap-space-xs"><span class="font-label-sm text-label-sm font-semibold text-outline">${esc(c.etiqueta)}${c.requerido ? " *" : ""}</span>${control}</label>`;
      }).join("");
      fondo.innerHTML = `
        <form class="w-full ${ancho} bg-surface-container-lowest rounded-xl shadow-[0_4px_12px_0_rgba(15,23,42,0.2)] p-space-lg flex flex-col gap-space-md">
          <h3 class="font-headline-sm text-headline-sm font-bold text-on-surface">${esc(titulo)}</h3>
          ${texto ? `<p class="font-body-md text-body-md text-on-surface-variant">${texto}</p>` : ""}
          ${html}
          <div class="flex justify-end gap-space-sm pt-space-xs">
            <button type="button" data-cancelar class="h-12 px-space-lg rounded-lg bg-surface-container hover:bg-surface-container-high font-label-md text-label-md font-semibold">${esc(cancelar)}</button>
            <button type="submit" class="h-12 px-space-lg rounded-lg ${peligro ? "bg-error hover:bg-on-error-container" : "bg-primary hover:bg-primary-container"} text-on-primary font-label-md text-label-md font-bold">${esc(aceptar)}</button>
          </div>
        </form>`;
      const cerrar = (v) => { fondo.remove(); resolver(v); };
      fondo.querySelector("[data-cancelar]").onclick = () => cerrar(null);
      fondo.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrar(null); });
      fondo.querySelector("form").onsubmit = (e) => {
        e.preventDefault();
        cerrar(Object.fromEntries(new FormData(e.target).entries()));
      };
      cont.appendChild(fondo);
      const primero = fondo.querySelector("input,textarea,select");
      if (primero) primero.focus();
    });
  }

  // ---------------------------------------------------------------- Usuario
  function usuario() { return localStorage.getItem(CLAVE_USUARIO) || ""; }
  function pintarUsuario() {
    const u = usuario();
    document.getElementById("hdr-usuario").textContent = u || "Sin usuario";
    document.getElementById("hdr-avatar").textContent = u ? u.split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase() : "?";
  }
  async function pedirUsuario() {
    const r = await modal({
      titulo: "Usuario actual",
      texto: "No hay inicio de sesión: este nombre queda registrado en alarmas, exclusiones y cambios de configuración.",
      campos: [{ nombre: "usuario", etiqueta: "Nombre y apellido", valor: usuario(), requerido: true }],
      aceptar: "Usar este nombre",
    });
    if (r && r.usuario.trim()) {
      localStorage.setItem(CLAVE_USUARIO, r.usuario.trim());
      pintarUsuario();
    }
    return usuario();
  }
  /** Devuelve el usuario; si no hay, lo pide antes de una acción que se registra. */
  async function exigirUsuario() { return usuario() || (await pedirUsuario()); }

  // ---------------------------------------------------------------- Contexto: proceso / variable
  function idVariableURL() {
    const p = new URLSearchParams(location.search).get("v");
    return p ? +p : null;
  }
  function conVariable(url, id) {
    const u = new URL(url, location.origin);
    u.searchParams.set("v", id);
    return u.pathname + u.search + u.hash;
  }

  async function cargarContexto() {
    const procesos = await api("/procesos");
    const todas = procesos.flatMap((p) => p.variables.map((v) => ({ ...v, proceso: p })));
    let id = idVariableURL() || +localStorage.getItem(CLAVE_VAR) || (todas[0] && todas[0].id);
    let variable = todas.find((v) => v.id === id) || todas[0] || null;
    if (variable) localStorage.setItem(CLAVE_VAR, variable.id);

    // Selector del header
    const sel = document.getElementById("sel-variable");
    sel.innerHTML = (variable ? "" : '<option value="" selected>Sin variables</option>') +
      procesos.filter((p) => p.variables.length).map((p) => `<optgroup label="${esc(p.nombre)}">${p.variables.map((v) =>
      `<option value="${v.id}" ${variable && v.id === variable.id ? "selected" : ""}>${esc(p.linea || p.nombre)} · ${esc(v.nombre)}</option>`).join("")}</optgroup>`).join("") +
      '<option value="nueva">+ Nueva variable…</option>';
    sel.onchange = () => {
      if (sel.value === "nueva") { location.href = "/ingenieria/mis-variables?nueva=1"; return; }
      if (!sel.value) return;
      localStorage.setItem(CLAVE_VAR, sel.value);
      location.href = conVariable(location.pathname, sel.value);
    };
    if (variable) {
      document.getElementById("hdr-proceso").textContent = `${variable.proceso.planta || "Estación de Control CEP"} — ${variable.proceso.nombre}`;
      document.querySelectorAll("a[data-con-variable]").forEach((a) => { a.href = conVariable(a.getAttribute("href"), variable.id); });
      const tipo = { xbar_r: "X̄-R", xbar_s: "X̄-S", imr: "I-MR", p: "p", np: "np", c: "c", u: "u" }[variable.tipo_carta];
      document.getElementById("hdr-info").textContent = `${tipo} · n=${variable.n} · Fase ${variable.fase}`;
      pintarTolerancias(variable);
      // Tarjeta "Frecuencia SPC" del menú de Operario (la vista de Inspección la actualiza en vivo).
      const fr = document.getElementById("aside-frecuencia");
      if (fr) {
        fr.textContent = cadaCuanto(variable.frecuencia_min);
        document.getElementById("aside-proxima").textContent =
          `${variable.tipo_carta === "imr" ? "1 unidad" : `${variable.n} unidades`} ${cadaCuanto(variable.frecuencia_min)}.`;
      }
    }
    return { procesos, variable, proceso: variable && variable.proceso, todas };
  }

  function pintarTolerancias(v) {
    const d = v.decimales;
    const vals = {
      objetivo: v.objetivo != null ? `${fmt(v.objetivo, d)} ${v.unidad}` : "—",
      lei: v.lei != null ? `${fmt(v.lei, d)} ${v.unidad}` : "—",
      les: v.les != null ? `${fmt(v.les, d)} ${v.unidad}` : "—",
      tolerancia: v.lei != null && v.les != null ? `${fmt(v.les - v.lei, d)} ${v.unidad}` : "—",
      n: String(v.n),
      fase: v.fase === "II" ? "II · Monitoreo" : "I · Estimación",
    };
    document.querySelectorAll("[data-tol]").forEach((el) => { el.textContent = vals[el.dataset.tol]; });
  }

  // ---------------------------------------------------------------- Header: turno y estado
  function turnoActual(turnos, ahora = new Date()) {
    const min = ahora.getHours() * 60 + ahora.getMinutes();
    const aMin = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
    return turnos.find((t) => {
      const a = aMin(t.inicio), b = aMin(t.fin);
      return a < b ? min >= a && min < b : min >= a || min < b;
    }) || null;
  }

  /** «Turno #12 · Mañana | 06:00 - 14:00» o «Fuera de turno · Mañana lun 06:00». */
  function textoTurno(e) {
    const hm = (iso) => (iso ? String(iso).slice(11, 16) : "");
    if (e && e.abierto) return `Turno #${e.abierto.numero} · ${e.abierto.nombre} | ${hm(e.abierto.inicio)} - ${hm(e.abierto.fin_programado)}`;
    if (e && e.proximo) {
      const d = new Date(e.proximo.desde);
      const hoy = new Date();
      const dia = d.toDateString() === hoy.toDateString() ? "" : `${d.toLocaleDateString("es", { weekday: "short" })} `;
      return `Fuera de turno · ${e.proximo.nombre} ${dia}${hm(e.proximo.desde)}`;
    }
    return "Fuera de turno";
  }

  async function pintarEstado(variable) {
    try {
      const e = await api("/turnos/estado");
      CEP.turno = e;
      document.getElementById("hdr-turno").textContent = textoTurno(e);
    } catch (e) { /* el header no bloquea la pantalla */ }
    if (!variable) {
      // Base vacía: no hay proceso que evaluar (no mostrar «Va bien»).
      const est = document.getElementById("hdr-estado");
      est.className = "flex items-center gap-space-xs px-space-sm py-1 rounded bg-primary text-primary-fixed font-label-sm text-label-sm font-semibold";
      est.innerHTML = '<span class="material-symbols-outlined text-sm">hourglass_empty</span><span>Sin datos</span>';
      return;
    }
    try {
      const c = await api(`/alarmas/contador?variable_id=${variable.id}`);
      const badge = document.getElementById("hdr-alarmas");
      badge.textContent = c.pendientes;
      badge.classList.toggle("hidden", !c.pendientes);
      badge.classList.toggle("flex", !!c.pendientes);
      const est = document.getElementById("hdr-estado");
      // Mismas palabras que el estado de la vista Operario.
      const [cls, icono, txt] = c.criticas ? ["bg-[#B91C1C] text-on-error", "front_hand", "Detener y avisar"]
        : c.pendientes ? ["bg-[#B45309] text-on-error", "priority_high", "Revisar"]
        : variable.fase === "I" ? ["bg-outline text-on-secondary", "school", "Conociendo el proceso"]
        : ["bg-[#15803D] text-on-secondary", "check_circle", "Va bien"];
      est.className = `flex items-center gap-space-xs px-space-sm py-1 rounded ${cls} font-label-sm text-label-sm font-semibold`;
      est.innerHTML = `<span class="material-symbols-outlined text-sm">${icono}</span><span>${txt}</span>`;
    } catch (e) { /* idem */ }
  }

  // ---------------------------------------------------------------- Arranque de pantalla
  async function arrancar(iniciar) {
    pintarUsuario();
    document.getElementById("btn-usuario").onclick = pedirUsuario;
    let ctx;
    try {
      ctx = await cargarContexto();
    } catch (e) {
      toast(e.message, "error");
      return;
    }
    CEP.ctx = ctx;
    pintarEstado(ctx.variable);
    if (!ctx.variable && !["mis_variables", "plantilla", "base_datos"].includes(document.body.dataset.pagina)) {
      // Base vacía: en lugar de pantallas en blanco, se invita a crear la primera variable
      // (o a cargar la demostración desde «Base de datos y respaldos»).
      avisoPantalla(document.querySelector("main > div"), "Todavía no hay variables",
        "Para empezar, crea la variable que quieres controlar: el asistente te guía en cuatro pasos. "
        + 'También puedes <a class="text-primary underline" href="/ingenieria/base-de-datos">cargar los datos de demostración</a> para conocer la aplicación.',
        ["/ingenieria/mis-variables?nueva=1", "Crear la primera variable"]);
      return;
    }
    try {
      await iniciar(ctx);
    } catch (e) {
      console.error(e);
      toast(e.message, "error");
    }
  }

  /** Mensaje en un contenedor cuando la variable no aplica a la pantalla. */
  function avisoPantalla(contenedor, titulo, texto, enlace) {
    contenedor.innerHTML = `
      <section class="bg-surface-container-lowest p-space-xl rounded-xl shadow-sm flex flex-col items-center text-center gap-space-sm">
        <span class="material-symbols-outlined text-5xl text-outline">info</span>
        <h2 class="font-headline-sm text-headline-sm font-bold">${esc(titulo)}</h2>
        <p class="font-body-md text-body-md text-on-surface-variant max-w-xl">${texto}</p>
        ${enlace ? `<a href="${enlace[0]}" class="mt-space-sm h-12 px-space-lg rounded-lg bg-primary text-on-primary font-label-md text-label-md font-bold flex items-center">${esc(enlace[1])}</a>` : ""}
      </section>`;
  }

  /** Frecuencia en minutos → "cada 15 min", "cada hora", "cada 2 horas", "cada 7 días". */
  function cadaCuanto(min) {
    if (min % 1440 === 0) return min === 1440 ? "cada día" : `cada ${min / 1440} días`;
    if (min % 60 === 0) return min === 60 ? "cada hora" : `cada ${min / 60} horas`;
    return `cada ${fmt(min, 0)} min`;
  }

  const NOMBRES_CARTA ={ xbar_r: "X̄ - R", xbar_s: "X̄ - S", imr: "I - MR", p: "p", np: "np", c: "c", u: "u" };
  const esAtributos = (v) => ["p", "np", "c", "u"].includes(v.tipo_carta);

  window.CEP = {
    api, arrancar, fmt, pct, fecha, hora, fechaHora, esc, rellenar, toast, modal, usuario, exigirUsuario,
    pedirUsuario, conVariable, avisoPantalla, pintarEstado, turnoActual, textoTurno, turno: null,
    NOMBRES_CARTA, esAtributos, cadaCuanto, ctx: null,
  };
})();
