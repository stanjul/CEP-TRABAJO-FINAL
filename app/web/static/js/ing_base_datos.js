/* =========================================================================
 * ing_base_datos.js — Base de datos y respaldos.
 * API: GET /sistema/info, POST /sistema/respaldos, POST /sistema/respaldos/{n}/restaurar,
 *      GET /sistema/respaldos/{n}/descargar, POST /sistema/base/restaurar, POST /sistema/demo,
 *      POST /sistema/abrir-carpeta
 * ========================================================================= */
(function () {
  "use strict";
  const { api, esc, fmt, fechaHora, toast } = CEP;
  const $ = (id) => document.getElementById(id);
  const tamano = (b) => (b >= 1048576 ? `${fmt(b / 1048576, 1)} MB` : `${fmt(b / 1024, 0)} KB`);

  async function cargar() {
    const i = await api("/sistema/info");
    $("bd-procesos").textContent = i.procesos;
    $("bd-variables").textContent = i.variables;
    $("bd-muestras").textContent = i.muestras;
    $("bd-ruta").textContent = i.base || "—";
    $("bd-tamano").textContent = `${tamano(i.tamano_bytes)} · versión ${i.version}`;
    $("bd-carpeta").classList.toggle("hidden", !i.puede_abrir_carpeta);
    $("bd-carpeta").classList.toggle("flex", i.puede_abrir_carpeta);
    $("bd-demo").classList.toggle("hidden", i.procesos > 0);
    $("bd-demo").classList.toggle("flex", i.procesos === 0);
    $("bd-respaldos").innerHTML = i.respaldos.length ? i.respaldos.map((r) => `<tr>
        <td class="py-space-sm pr-space-sm">${fechaHora(r.fecha)}</td>
        <td class="py-space-sm pr-space-sm text-on-surface-variant">${esc(r.motivo)}</td>
        <td class="py-space-sm pr-space-sm text-right">${tamano(r.tamano_bytes)}</td>
        <td class="py-space-sm text-right whitespace-nowrap">
          <a class="inline-flex items-center gap-1 h-9 px-space-sm rounded-lg hover:bg-surface-container text-primary font-label-md text-label-md" href="/api/sistema/respaldos/${encodeURIComponent(r.nombre)}/descargar" title="Descargar">
            <span class="material-symbols-outlined text-sm">download</span></a>
          <button class="inline-flex items-center gap-1 h-9 px-space-sm rounded-lg hover:bg-surface-container text-primary font-label-md text-label-md font-semibold" data-restaurar="${esc(r.nombre)}" data-fecha="${esc(fechaHora(r.fecha))}" type="button">
            <span class="material-symbols-outlined text-sm">restore</span>Volver a este</button></td></tr>`).join("")
      : '<tr><td class="py-space-sm text-on-surface-variant" colspan="4">Todavía no hay respaldos. Se crea uno cada vez que se abre la aplicación.</td></tr>';
    $("bd-respaldos").querySelectorAll("[data-restaurar]").forEach((b) => (b.onclick = () => restaurar(b.dataset.restaurar, b.dataset.fecha)));
  }

  async function confirmar(titulo, texto) {
    return CEP.modal({ titulo, texto, aceptar: "Sí, restaurar", peligro: true });
  }

  async function restaurar(nombre, fecha) {
    if (!(await confirmar("Volver a un respaldo", `Los datos volverán a como estaban el <b>${esc(fecha)}</b>. Lo que se registró después se pierde, pero antes se guarda un respaldo de la base actual por si necesitas deshacerlo.`))) return;
    try {
      const r = await api(`/sistema/respaldos/${encodeURIComponent(nombre)}/restaurar`, { method: "POST" });
      toast(`Base restaurada: ${r.procesos} procesos, ${r.variables} variables, ${r.subgrupos} muestras.`);
      setTimeout(() => location.reload(), 900);
    } catch (e) { toast(e.message, "error"); }
  }

  async function restaurarArchivo(f) {
    if (!f) return;
    if (!(await confirmar("Restaurar desde un archivo", `Todos los datos se reemplazarán por los de <b>${esc(f.name)}</b>. Antes se guarda un respaldo de la base actual.`))) {
      $("bd-archivo").value = "";
      return;
    }
    const fd = new FormData();
    fd.append("archivo", f);
    try {
      const r = await api("/sistema/base/restaurar", { method: "POST", body: fd });
      toast(`Base restaurada desde ${r.restaurado}: ${r.procesos} procesos, ${r.subgrupos} muestras.`);
      setTimeout(() => location.reload(), 900);
    } catch (e) { toast(e.message, "error"); }
    $("bd-archivo").value = "";
  }

  CEP.arrancar(async () => {
    $("bd-respaldar").onclick = async () => {
      try { const r = await api("/sistema/respaldos", { json: { motivo: "manual" } }); toast(`Respaldo guardado (${tamano(r.tamano_bytes)}).`); await cargar(); }
      catch (e) { toast(e.message, "error"); }
    };
    $("bd-carpeta").onclick = () => api("/sistema/abrir-carpeta", { method: "POST" }).catch((e) => toast(e.message, "error"));
    $("bd-cargar-demo").onclick = async () => {
      try { await api("/sistema/demo", { method: "POST" }); toast("Datos de demostración cargados."); setTimeout(() => (location.href = "/ingenieria/mis-variables"), 700); }
      catch (e) { toast(e.message, "error"); }
    };
    $("bd-archivo").addEventListener("change", (e) => restaurarArchivo(e.target.files[0]));
    await cargar();
  });
})();
