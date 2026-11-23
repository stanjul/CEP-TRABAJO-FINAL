/* =========================================================================
 * alarmas_ui.js — tarjetas de alarma (estilo Stitch) y registro de causa/acción.
 * ========================================================================= */
(function () {
  "use strict";
  const { esc, hora, fechaHora } = CEP;

  const ESTADOS = { abierta: "Sin revisar", en_investigacion: "En revisión", resuelta: "Resuelta" };
  const SEVERIDAD = {
    critica: { icono: "error", color: "text-error", fondo: "bg-error-container/40", chip: "bg-error text-on-error" },
    advertencia: { icono: "warning", color: "text-[#B45309]", fondo: "bg-[#FEF3C7]/60", chip: "bg-[#FEF3C7] text-[#B45309]" },
    alerta: { icono: "info", color: "text-on-secondary-fixed-variant", fondo: "bg-surface-container-low", chip: "bg-surface-container-highest text-on-surface-variant" },
  };

  const TIPO_EVENTO = { parada: "Parada del proceso", retencion: "Lote retenido", anomalia: "Problema reportado" };
  // Títulos en palabras simples (el nombre técnico queda en Ingeniería y en el tooltip).
  const TITULO_REGLA = {
    N1: "Valor fuera de lo normal", N2: "El proceso se corrió", N3: "Tendencia", N4: "Sube y baja alternadamente",
    N5: "Valores cerca del límite", N6: "Valores alejados del promedio", N7: "Valores demasiado parejos",
    N8: "Posible mezcla de producto", WE4: "El proceso se corrió",
  };
  const tituloRegla = (a) => (["r", "s", "mr"].includes(a.carta) ? "Aumentó la variación" : TITULO_REGLA[a.regla] || a.regla_nombre);

  /** HTML de una alarma. Abiertas: con botón de causa/acción. Resueltas: resumen en verde.
   *  El título y el texto están en palabras simples; el código de regla queda como dato chico. */
  function tarjeta(a, { compacta = false } = {}) {
    const muestra = a.subgrupo_numero ? ` · muestra #${a.subgrupo_numero}` : "";
    const titulo = a.tipo === "regla"
      ? `${hora(a.creada)} — ${esc(tituloRegla(a))}${muestra}`
      : `${hora(a.creada)} — ${esc(TIPO_EVENTO[a.tipo] || "Evento")}`;
    const codigo = a.tipo === "regla" ? `<span class="font-label-sm text-label-sm text-outline" title="${esc(a.descripcion)}">Regla ${esc(a.regla)}</span>` : "";
    if (a.estado === "resuelta") {
      return `<div class="p-space-md rounded-lg bg-surface-container-lowest border border-outline-variant/40 flex flex-col gap-1" data-alarma="${a.id}">
        <div class="flex items-center justify-between gap-space-xs">
          <div class="flex items-center gap-space-xs"><span class="material-symbols-outlined text-secondary text-lg">check_circle</span>
            <span class="font-label-md text-label-md font-bold text-on-surface">${titulo}</span></div>
          <span class="font-label-sm text-label-sm text-secondary font-bold">Resuelto</span>
        </div>
        <p class="font-body-sm text-body-sm text-on-surface-variant"><b>Causa:</b> ${esc(a.causa)} · <b>Acción:</b> ${esc(a.accion)}</p>
        <p class="font-label-sm text-label-sm text-outline">Registrado por ${esc(a.usuario || "—")} · ${fechaHora(a.cerrada)}</p>
      </div>`;
    }
    const s = SEVERIDAD[a.severidad] || SEVERIDAD.alerta;
    const seguimiento = a.causa || a.accion
      ? `<p class="font-body-sm text-body-sm text-on-surface"><b>Causa:</b> ${esc(a.causa || "—")} · <b>Acción:</b> ${esc(a.accion || "—")}</p>` : "";
    return `<div class="p-space-md rounded-lg ${s.fondo} flex flex-col gap-space-xs" data-alarma="${a.id}">
      <div class="flex items-start justify-between gap-space-xs">
        <div class="flex items-center gap-space-xs"><span class="material-symbols-outlined ${s.color} text-xl">${s.icono}</span>
          <span class="font-label-md text-label-md font-bold text-on-surface">${titulo}</span></div>
        <span class="px-space-xs py-0.5 rounded ${s.chip} font-label-sm text-label-sm font-semibold whitespace-nowrap">${ESTADOS[a.estado]}</span>
      </div>
      <p class="font-body-md text-body-md text-on-surface">${esc(a.explicacion || a.descripcion)}</p>
      ${seguimiento}
      ${compacta ? "" : `<div class="pt-space-xs flex items-center justify-between gap-space-sm">${codigo}
        <button class="h-10 px-space-md rounded-lg bg-primary-container hover:bg-primary text-on-primary font-label-md text-label-md font-semibold flex items-center gap-1 transition-colors" data-registrar="${a.id}" type="button">
          <span class="material-symbols-outlined text-sm">edit_note</span>Anotar qué pasó</button></div>`}
    </div>`;
  }

  /** Abre el diálogo de causa/acción y guarda. Devuelve la alarma actualizada o null. */
  async function registrarCausa(alarma) {
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return null;
    const r = await CEP.modal({
      titulo: "Anotar qué pasó",
      texto: esc(alarma.explicacion || alarma.descripcion),
      campos: [
        { nombre: "causa", etiqueta: "¿Qué lo causó? (si lo sabes)", tipo: "textarea", valor: alarma.causa },
        { nombre: "accion", etiqueta: "¿Qué se hizo?", tipo: "textarea", valor: alarma.accion },
        { nombre: "estado", etiqueta: "Estado", tipo: "select", valor: alarma.estado === "abierta" ? "en_investigacion" : alarma.estado,
          opciones: [["abierta", "Sin revisar"], ["en_investigacion", "En revisión"], ["resuelta", "Resuelta (hay que completar causa y acción)"]] },
      ],
      aceptar: "Guardar",
    });
    if (!r) return null;
    try {
      const a = await CEP.api(`/alarmas/${alarma.id}`, { method: "PATCH", json: { ...r, usuario } });
      CEP.toast(a.estado === "resuelta" ? "Alarma resuelta y trazada." : "Seguimiento registrado.");
      return a;
    } catch (e) {
      CEP.toast(e.message, "error");
      return null;
    }
  }

  /** Diálogo de evento manual (parada, retención, anomalía). */
  async function reportarEvento(variableId, tipoInicial = "parada") {
    const usuario = await CEP.exigirUsuario();
    if (!usuario) return null;
    const r = await CEP.modal({
      titulo: "Reportar un problema",
      texto: "Queda registrado como alerta y el estado del proceso lo muestra hasta que se resuelva.",
      campos: [
        { nombre: "tipo", etiqueta: "¿Qué pasó?", tipo: "select", valor: tipoInicial,
          opciones: [["parada", "Se detuvo el proceso"], ["retencion", "Retuve un lote"], ["anomalia", "Vi algo raro (advertencia)"]] },
        { nombre: "descripcion", etiqueta: "Cuéntalo brevemente", tipo: "textarea", requerido: true },
      ],
      aceptar: "Reportar", peligro: true,
    });
    if (!r) return null;
    try {
      const a = await CEP.api(`/variables/${variableId}/eventos`, { json: { ...r, usuario } });
      CEP.toast("Evento registrado.", "aviso");
      return a;
    } catch (e) {
      CEP.toast(e.message, "error");
      return null;
    }
  }

  window.ALARMAS = { tarjeta, registrarCausa, reportarEvento, ESTADOS, tituloRegla };
})();
