/* =========================================================================
 * operario_alertas.js — listado de alarmas con filtro y registro de causa/acción.
 * API: /alarmas?variable_id=&estado=, PATCH /alarmas/{id}, POST /variables/{id}/eventos
 * ========================================================================= */
(function () {
  "use strict";
  const { api, esc } = CEP;
  const $ = (id) => document.getElementById(id);
  let V, estado = "pendientes", porId = {};

  async function cargar() {
    const q = new URLSearchParams({ limite: 500 });
    if (!$("todas-variables").checked && V) q.set("variable_id", V.id);
    const todas = await api(`/alarmas?${q}`);
    const filtradas = estado === "pendientes" ? todas.filter((a) => a.estado !== "resuelta") : estado ? todas.filter((a) => a.estado === estado) : todas;
    porId = Object.fromEntries(todas.map((a) => [a.id, a]));
    $("c-pend").textContent = todas.filter((a) => a.estado !== "resuelta").length;
    $("c-crit").textContent = todas.filter((a) => a.estado !== "resuelta" && a.severidad === "critica").length;
    $("c-inv").textContent = todas.filter((a) => a.estado === "en_investigacion").length;
    $("c-res").textContent = todas.filter((a) => a.estado === "resuelta").length;
    $("al-sub").textContent = $("todas-variables").checked ? "Alertas de todas las variables de la planta." : `${V.proceso.linea || V.proceso.nombre} · ${V.nombre}`;
    const nombres = Object.fromEntries(CEP.ctx.todas.map((v) => [v.id, v.nombre]));
    $("lista").innerHTML = filtradas.map((a) => `<div class="flex flex-col gap-1">
      ${$("todas-variables").checked ? `<span class="font-label-sm text-label-sm text-outline">${esc(nombres[a.variable_id] || "")}</span>` : ""}
      ${ALARMAS.tarjeta(a)}
      <span class="font-label-sm text-label-sm text-outline px-space-xs">${CEP.fechaHora(a.creada)}${a.usuario ? ` · anotado por ${esc(a.usuario)}` : ""}</span></div>`).join("")
      || `<div class="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex items-center gap-space-sm col-span-full">
          <span class="material-symbols-outlined text-secondary text-3xl">check_circle</span><span class="font-body-lg text-body-lg">No hay alertas en este filtro.</span></div>`;
    $("lista").querySelectorAll("[data-registrar]").forEach((b) => (b.onclick = async () => {
      if (await ALARMAS.registrarCausa(porId[b.dataset.registrar])) { await cargar(); CEP.pintarEstado(V); }
    }));
    document.querySelectorAll("#filtro-estado [data-estado]").forEach((b) => {
      b.className = `h-10 px-space-md rounded font-label-md text-label-md ${b.dataset.estado === estado ? "bg-primary text-on-primary font-bold" : "text-on-surface-variant"}`;
    });
  }

  async function iniciar(ctx) {
    V = ctx.variable;
    document.querySelectorAll("#filtro-estado [data-estado]").forEach((b) => (b.onclick = () => { estado = b.dataset.estado; cargar(); }));
    $("todas-variables").onchange = cargar;
    $("btn-evento").onclick = async () => { if (await ALARMAS.reportarEvento(V.id, "anomalia")) { await cargar(); CEP.pintarEstado(V); } };
    await cargar();
    setInterval(() => cargar().catch(() => {}), 30000);
  }

  CEP.arrancar(iniciar);
})();
