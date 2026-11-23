/* =========================================================================
 * ing_mis_variables.js — Variables a controlar: lista por proceso y asistente "Nueva variable".
 * API: GET /procesos, POST /procesos, POST /procesos/{id}/variables, DELETE /variables/{id},
 *      GET /asistente/carta
 * ========================================================================= */
(function () {
  "use strict";
  const { api, esc, fmt, toast } = CEP;
  const $ = (id) => document.getElementById(id);

  /** Nombre en palabras de lo que se registra (para personas no expertas). */
  const QUE_SE_REGISTRA = {
    xbar_r: "Medición", xbar_s: "Medición", imr: "Medición (una unidad por vez)",
    p: "Unidades defectuosas (porcentaje)", np: "Unidades defectuosas (cantidad)",
    c: "Fallas por muestra", u: "Fallas por unidad",
  };
  const NOMBRE_GRAFICA = {
    xbar_r: "Promedio y rango (X̄-R)", xbar_s: "Promedio y desviación (X̄-S)", imr: "Valores individuales (I-MR)",
    p: "Porcentaje de defectuosos (p)", np: "Cantidad de defectuosos (np)", c: "Fallas por muestra (c)", u: "Fallas por unidad (u)",
  };
  const CARTAS_POR_TIPO = { medida: ["xbar_r", "xbar_s", "imr"], defectuosos: ["p", "np"], defectos: ["c", "u"] };

  const frecuenciaTexto = (min) => CEP.cadaCuanto(min);
  function planTexto(v) {
    const n = v.tipo_carta === "imr" ? 1 : v.n;
    const unidades = v.tipo_carta === "c" ? "una muestra" : `${n} ${n === 1 ? "unidad" : "unidades"}`;
    return `${unidades} ${frecuenciaTexto(v.frecuencia_min)}`;
  }

  // ------------------------------------------------------------------ Lista
  function tarjetaVariable(v, activa) {
    const d = v.decimales;
    let espec = "";
    if (v.lei !== null || v.les !== null) {
      const partes = [];
      if (v.lei !== null) partes.push(`mín. ${fmt(v.lei, d)}`);
      if (v.objetivo !== null) partes.push(`ideal ${fmt(v.objetivo, d)}`);
      if (v.les !== null) partes.push(`máx. ${fmt(v.les, d)}`);
      espec = `${partes.join(" · ")} ${esc(v.unidad)}`;
    }
    const fase = v.fase === "II"
      ? `<span class="inline-flex items-center gap-1 px-space-xs py-0.5 rounded bg-primary-fixed/50 text-on-primary-fixed-variant font-label-sm text-label-sm"><span class="material-symbols-outlined text-sm">monitoring</span>Monitoreando</span>`
      : `<span class="inline-flex items-center gap-1 px-space-xs py-0.5 rounded bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm"><span class="material-symbols-outlined text-sm">school</span>Fase I: conociendo el proceso</span>`;
    const ir = (url) => CEP.conVariable(url, v.id);
    return `
      <article class="bg-surface-container-lowest rounded-xl shadow-sm p-space-md flex flex-col lg:flex-row lg:items-center gap-space-md ${activa ? "ring-2 ring-primary-container/40" : ""}">
        <div class="flex-1 min-w-0 flex flex-col gap-space-xs">
          <div class="flex flex-wrap items-center gap-space-sm">
            <h3 class="font-headline-sm text-headline-sm font-bold text-on-surface">${esc(v.nombre)}${v.unidad ? ` <span class="font-body-md text-body-md font-normal text-on-surface-variant">(${esc(v.unidad)})</span>` : ""}</h3>
            ${fase}
          </div>
          <dl class="grid grid-cols-1 sm:grid-cols-3 gap-x-space-lg gap-y-1 font-body-md text-body-md">
            <div><dt class="font-body-sm text-body-sm text-on-surface-variant">Qué se registra</dt><dd class="text-on-surface">${QUE_SE_REGISTRA[v.tipo_carta]}</dd></div>
            <div><dt class="font-body-sm text-body-sm text-on-surface-variant">Muestra</dt><dd class="text-on-surface">${planTexto(v)}</dd></div>
            <div><dt class="font-body-sm text-body-sm text-on-surface-variant">${espec ? "Valores aceptados" : "Gráfica"}</dt><dd class="text-on-surface">${espec || NOMBRE_GRAFICA[v.tipo_carta]}</dd></div>
          </dl>
          <p class="font-body-sm text-body-sm text-on-surface-variant">${v.muestras ? `${v.muestras} muestra(s) registradas` : "Todavía sin muestras"}</p>
        </div>
        <div class="flex flex-wrap gap-space-xs lg:justify-end">
          <a class="h-10 px-space-md rounded-lg bg-primary hover:bg-primary-container text-on-primary font-label-md text-label-md font-semibold flex items-center gap-space-xs" href="${ir("/operario")}">
            <span class="material-symbols-outlined text-sm">edit_note</span>Registrar muestras</a>
          <a class="h-10 px-space-md rounded-lg bg-surface-container-low hover:bg-surface-container text-primary font-label-md text-label-md font-semibold flex items-center gap-space-xs" href="${ir("/ingenieria/diseno")}">
            <span class="material-symbols-outlined text-sm">tune</span>Plan de muestreo</a>
          <a class="h-10 px-space-md rounded-lg bg-surface-container-low hover:bg-surface-container text-primary font-label-md text-label-md font-semibold flex items-center gap-space-xs" href="${ir(CEP.esAtributos(v) ? "/ingenieria/atributos" : "/ingenieria/variables")}">
            <span class="material-symbols-outlined text-sm">show_chart</span>Ver gráfica</a>
          ${v.muestras ? "" : `<button class="h-10 px-space-sm rounded-lg text-error hover:bg-error-container font-label-md text-label-md flex items-center gap-1" data-eliminar="${v.id}" data-nombre="${esc(v.nombre)}" type="button" title="Eliminar (solo variables sin muestras)">
            <span class="material-symbols-outlined text-sm">delete</span>Eliminar</button>`}
        </div>
      </article>`;
  }

  function pintarLista(procesos, activaId) {
    const cont = $("lista-procesos");
    if (!procesos.length) {
      cont.innerHTML = `
        <section class="bg-surface-container-lowest p-space-xl rounded-xl shadow-sm flex flex-col items-center text-center gap-space-sm">
          <span class="material-symbols-outlined text-5xl text-primary-container">add_chart</span>
          <h2 class="font-headline-sm text-headline-sm font-bold">Empieza creando la primera variable</h2>
          <p class="font-body-md text-body-md text-on-surface-variant max-w-xl">El asistente te pregunta qué se revisa, cómo se registra y cada cuánto se toma la muestra, y elige la gráfica adecuada.</p>
          <button class="mt-space-sm h-12 px-space-lg rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-bold" data-abrir-asistente type="button">Nueva variable</button>
          <a class="font-body-md text-body-md text-primary underline" href="/ingenieria/base-de-datos">o cargar los datos de demostración para conocer la aplicación</a>
        </section>`;
    } else {
      cont.innerHTML = procesos.map((p) => `
        <section class="flex flex-col gap-space-sm">
          <div class="flex items-baseline gap-space-sm px-space-xs">
            <h2 class="font-headline-sm text-headline-sm font-bold text-on-surface">${esc(p.nombre)}</h2>
            ${p.linea ? `<span class="font-body-md text-body-md text-on-surface-variant">${esc(p.linea)}</span>` : ""}
          </div>
          ${p.variables.length ? p.variables.map((v) => tarjetaVariable(v, v.id === activaId)).join("")
            : `<p class="px-space-xs font-body-md text-body-md text-on-surface-variant">Este proceso aún no tiene variables.</p>`}
        </section>`).join("");
    }
    cont.querySelectorAll("[data-abrir-asistente]").forEach((b) => (b.onclick = () => abrirAsistente(procesos)));
    cont.querySelectorAll("[data-eliminar]").forEach((b) => (b.onclick = () => eliminar(+b.dataset.eliminar, b.dataset.nombre)));
  }

  async function eliminar(id, nombre) {
    const r = await CEP.modal({
      titulo: `Eliminar «${nombre}»`,
      texto: "La variable todavía no tiene muestras, así que se puede eliminar sin perder información. Esta acción no se puede deshacer.",
      aceptar: "Eliminar variable", peligro: true,
    });
    if (!r) return;
    try {
      await api(`/variables/${id}`, { method: "DELETE" });
      if (+localStorage.getItem("cep.variable") === id) localStorage.removeItem("cep.variable");
      toast(`Variable «${nombre}» eliminada.`);
      location.href = location.pathname;
    } catch (e) { toast(e.message, "error"); }
  }

  // ------------------------------------------------------------------ Asistente
  function abrirAsistente(procesos) {
    const nodo = $("tpl-asistente").content.firstElementChild.cloneNode(true);
    document.getElementById("cep-modales").appendChild(nodo);
    const f = nodo.querySelector("form");
    const q = (sel) => nodo.querySelector(sel);
    const qa = (sel) => [...nodo.querySelectorAll(sel)];
    let paso = 1;
    let recomendada = null;

    // Paso 1: lista de procesos (radio) + "Nuevo proceso"
    const activo = CEP.ctx && CEP.ctx.proceso ? CEP.ctx.proceso.id : procesos[0] && procesos[0].id;
    q("[data-lista-procesos]").innerHTML = [...procesos.map((p) => [String(p.id), p.nombre, p.linea]), ["nuevo", "Otro proceso (crear uno nuevo)", ""]]
      .map(([id, nombre, linea]) => `
        <label class="flex items-center gap-space-sm min-h-[48px] px-space-md rounded-lg bg-surface-container-low hover:bg-surface-container cursor-pointer">
          <input name="proceso" type="radio" value="${id}" ${String(activo) === id || (!procesos.length && id === "nuevo") ? "checked" : ""}/>
          <span class="font-body-md text-body-md ${id === "nuevo" ? "text-primary font-semibold" : "text-on-surface"}">${esc(nombre)}</span>
          ${linea ? `<span class="font-body-sm text-body-sm text-on-surface-variant">${esc(linea)}</span>` : ""}
        </label>`).join("");
    const mostrarNuevo = () => {
      const nuevo = f.proceso.value === "nuevo";
      q("[data-nuevo-proceso]").classList.toggle("hidden", !nuevo);
      q("[data-nuevo-proceso]").classList.toggle("flex", nuevo);
    };
    qa('input[name="proceso"]').forEach((r) => r.addEventListener("change", mostrarNuevo));
    mostrarNuevo();

    // Paso 3: chips de frecuencia
    const marcarChips = () => qa("[data-chips-frecuencia] button").forEach((b) => {
      const sel = +b.dataset.min === +f.frecuencia_min.value;
      b.className = `h-10 px-space-sm rounded-lg font-label-md text-label-md ${sel ? "bg-primary-container text-on-primary" : "bg-surface-container-low hover:bg-surface-container"}`;
      b.setAttribute("aria-pressed", sel);
    });
    qa("[data-chips-frecuencia] button").forEach((b) => (b.onclick = () => { f.frecuencia_min.value = b.dataset.min; marcarChips(); }));
    f.frecuencia_min.addEventListener("input", marcarChips);
    marcarChips();

    const que = () => (f.que.value || "");
    const constante = () => f.constante.value !== "no";

    function adaptarATipo() {
      const t = que();
      const medida = t === "medida";
      // `hidden` gana sobre `flex`/`grid` en Tailwind (se genera después), así que basta con alternarlo.
      qa("[data-solo-medida]").forEach((el) => el.classList.toggle("hidden", !medida));
      qa("[data-solo-conteo]").forEach((el) => { el.classList.toggle("hidden", medida); el.classList.add("flex"); });
      q("[data-txt-n]").textContent = medida ? "¿Cuántas unidades mides cada vez?" : "¿Cuántas unidades revisas en cada muestra?";
      q("[data-ayuda-n]").textContent = medida
        ? "Lo habitual son 4 o 5 unidades seguidas. Escribe 1 si mides de a una (ensayos destructivos, producción lenta)."
        : t === "defectuosos" ? "Para porcentajes de defectuosos se suelen revisar 50 o más unidades." : "Si la muestra es siempre una pieza o un lote igual, escribe 1.";
      if (!medida && +f.n.value === 5 && t === "defectuosos") f.n.value = 50;
      if (!medida && t === "defectos" && +f.n.value === 50) f.n.value = 1;
      if (medida && +f.n.value === 50) f.n.value = 5;
    }

    async function recomendar() {
      const t = que();
      if (!t) return;
      const n = Math.max(1, Math.round(+f.n.value || 1));
      try {
        recomendada = await api(`/asistente/carta?${new URLSearchParams({ que: t, n, tamano_constante: t === "medida" ? true : constante() })}`);
      } catch (e) { return; }
      q("[data-rec-titulo]").textContent = `Gráfica recomendada: ${NOMBRE_GRAFICA[recomendada.carta]}`;
      q("[data-rec-razon]").textContent = recomendada.razon;
      const opciones = CARTAS_POR_TIPO[t].filter((c) => t !== "medida" || (n === 1) === (c === "imr"));
      f.tipo_carta.innerHTML = opciones.map((c) => `<option value="${c}" ${c === recomendada.carta ? "selected" : ""}>${NOMBRE_GRAFICA[c]}${c === recomendada.carta ? " (recomendada)" : ""}</option>`).join("");
    }
    f.n.addEventListener("input", recomendar);
    qa('input[name="constante"]').forEach((r) => r.addEventListener("change", recomendar));

    // Navegación
    const error = (texto) => {
      const el = q("[data-error]");
      el.textContent = texto || "";
      el.classList.toggle("hidden", !texto);
    };
    function mostrarPaso() {
      qa("[data-paso]").forEach((fs) => { const v = +fs.dataset.paso === paso; fs.classList.toggle("hidden", !v); fs.classList.toggle("flex", v); });
      qa("[data-paso-ind]").forEach((li) => {
        const i = +li.dataset.pasoInd;
        li.className = `flex flex-col gap-1 font-label-sm text-label-sm ${i === paso ? "text-primary font-bold" : i < paso ? "text-on-surface" : "text-outline"}`;
        li.innerHTML = `<span class="h-1 rounded-full ${i <= paso ? "bg-primary-container" : "bg-surface-container-high"}"></span>${li.textContent.trim() || li.dataset.texto}`;
        if (i === paso) li.setAttribute("aria-current", "step"); else li.removeAttribute("aria-current");
      });
      q("[data-atras]").classList.toggle("invisible", paso === 1);
      q("[data-siguiente]").innerHTML = paso === 4 ? '<span class="material-symbols-outlined">check</span>Crear variable' : "Siguiente";
      if (paso === 3) { adaptarATipo(); recomendar(); }
      if (paso === 4) { adaptarATipo(); resumen(); }
      error("");
      const primero = q(`[data-paso="${paso}"] input:not([type=radio]), [data-paso="${paso}"] input:checked`);
      if (primero) setTimeout(() => primero.focus(), 30);
    }
    qa("[data-paso-ind]").forEach((li) => (li.dataset.texto = li.textContent.trim()));

    const num = (t) => (String(t).trim() === "" ? null : parseFloat(String(t).replace(",", ".")));

    function validar() {
      if (paso === 1) {
        if (!f.proceso.value) return "Elige un proceso.";
        if (f.proceso.value === "nuevo" && !f.proceso_nombre.value.trim()) return "Escribe el nombre del proceso nuevo.";
      }
      if (paso === 2) {
        if (!f.nombre.value.trim()) return "Escribe el nombre de lo que vas a controlar.";
        if (!que()) return "Elige cómo se registra cada unidad.";
      }
      if (paso === 3) {
        const n = +f.n.value, fr = +f.frecuencia_min.value;
        if (!(Number.isInteger(n) && n >= 1)) return "La cantidad de unidades debe ser un número entero, 1 o más.";
        if (["xbar_r", "xbar_s"].includes(f.tipo_carta.value) && n < 2) return "Esta gráfica necesita al menos 2 unidades por muestra.";
        if (!(Number.isInteger(fr) && fr >= 1)) return "Indica cada cuántos minutos se toma la muestra.";
      }
      if (paso === 4 && que() === "medida") {
        const [lei, obj, les] = [num(f.lei.value), num(f.objetivo.value), num(f.les.value)];
        if ([lei, obj, les].some((x) => x !== null && Number.isNaN(x))) return "Los valores aceptados deben ser números (puedes usar coma decimal).";
        if (lei !== null && les !== null && lei >= les) return "El mínimo aceptado debe ser menor que el máximo.";
        if (obj !== null && ((lei !== null && obj < lei) || (les !== null && obj > les))) return "El valor ideal debe estar entre el mínimo y el máximo.";
      }
      return null;
    }

    function resumen() {
      const proc = f.proceso.value === "nuevo" ? f.proceso_nombre.value.trim() : (procesos.find((p) => String(p.id) === f.proceso.value) || {}).nombre;
      const n = +f.n.value;
      const items = [
        ["Proceso", proc],
        ["Variable", `${f.nombre.value.trim()}${que() === "medida" && f.unidad.value.trim() ? ` (${f.unidad.value.trim()})` : ""}`],
        ["Se registra", { medida: "Medición con instrumento", defectuosos: "Unidades buenas o malas", defectos: "Cantidad de fallas" }[que()]],
        ["Muestra", `${n} ${n === 1 ? "unidad" : "unidades"} ${frecuenciaTexto(+f.frecuencia_min.value)}`],
        ["Gráfica", NOMBRE_GRAFICA[f.tipo_carta.value]],
      ];
      q("[data-resumen]").innerHTML = items.map(([a, b]) => `<li><span class="text-on-surface font-semibold">${a}:</span> ${esc(b)}</li>`).join("");
    }

    async function crear() {
      const usuario = await CEP.exigirUsuario();
      if (!usuario) return;
      const btn = q("[data-siguiente]");
      btn.disabled = true;
      try {
        let procesoId = +f.proceso.value;
        if (f.proceso.value === "nuevo") {
          const p = await api("/procesos", { json: { nombre: f.proceso_nombre.value.trim(), linea: f.proceso_linea.value.trim() || null } });
          procesoId = p.id;
        }
        const medida = que() === "medida";
        const cuerpo = {
          nombre: f.nombre.value.trim(), tipo_carta: f.tipo_carta.value, n: f.tipo_carta.value === "imr" ? 1 : +f.n.value,
          frecuencia_min: +f.frecuencia_min.value, usuario,
          unidad: medida ? f.unidad.value.trim() : (que() === "defectos" ? "fallas" : "uds"),
          decimales: medida ? +f.decimales.value : 2,
        };
        if (medida) ["lei", "objetivo", "les"].forEach((c) => { const x = num(f[c].value); if (x !== null) cuerpo[c] = x; });
        const v = await api(`/procesos/${procesoId}/variables`, { json: cuerpo });
        localStorage.setItem("cep.variable", v.id);
        cerrar();
        await CEP.modal({
          titulo: "Variable creada",
          texto: `«${esc(v.nombre)}» está lista. El siguiente paso es registrar las primeras muestras: con unas 20 a 25 la app calcula los límites de control del proceso.`,
          aceptar: "Ir a registrar muestras", cancelar: "Quedarme en la lista",
        }).then((ok) => { location.href = ok ? CEP.conVariable("/operario", v.id) : CEP.conVariable(location.pathname, v.id); });
      } catch (e) {
        error(e.message);
        btn.disabled = false;
      }
    }

    function cerrar() { nodo.remove(); document.removeEventListener("keydown", teclas); }
    function teclas(e) { if (e.key === "Escape") cerrar(); }
    document.addEventListener("keydown", teclas);
    q("[data-cerrar]").onclick = cerrar;
    q("[data-atras]").onclick = () => { if (paso > 1) { paso--; mostrarPaso(); } };
    f.onsubmit = (e) => {
      e.preventDefault();
      const msj = validar();
      if (msj) return error(msj);
      if (paso < 4) { paso++; mostrarPaso(); } else crear();
    };
    mostrarPaso();
  }

  // ------------------------------------------------------------------ Inicio
  async function iniciar(ctx) {
    pintarLista(ctx.procesos, ctx.variable && ctx.variable.id);
    $("btn-nueva").onclick = () => abrirAsistente(ctx.procesos);
    if (new URLSearchParams(location.search).get("nueva") === "1") abrirAsistente(ctx.procesos);
  }

  CEP.arrancar(iniciar);
})();
