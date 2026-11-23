/* =========================================================================
 * ing_atributos.js — asistente de selección de carta de atributos y tarjetas propias de
 * la pantalla (modelo, fórmula y totales). La carta en sí la maneja carta_ing.js.
 * ========================================================================= */
(function () {
  "use strict";
  const { api, fmt, pct, esc } = CEP;
  const $ = (id) => document.getElementById(id);

  const FORMULAS = {
    p: ["Binomial", "p̄ ± 3·√(p̄(1−p̄)/nᵢ)"],
    np: ["Binomial", "n·p̄ ± 3·√(n·p̄(1−p̄))"],
    c: ["Poisson", "c̄ ± 3·√c̄"],
    u: ["Poisson", "ū ± 3·√(ū/nᵢ)"],
  };

  async function recomendar() {
    const q = new URLSearchParams({ tipo_dato: $("as-tipo").value, tamano_constante: $("as-constante").value, interes: $("as-interes").value });
    try {
      const r = await api(`/atributos/recomendar?${q}`);
      $("as-carta").textContent = `Carta ${r.carta}`;
      $("as-dist").textContent = r.distribucion;
      $("as-razon").textContent = r.razon;
      $("as-alt").textContent = r.alternativas.length ? `Alternativa(s): ${r.alternativas.join(", ")}` : "";
    } catch (e) { CEP.toast(e.message, "error"); }
  }

  /** Completa las tarjetas propias de atributos cuando carta_ing.js termina de cargar la carta. */
  async function tarjetas(v) {
    if (!CEP.esAtributos(v)) return;
    const [dist, formula] = FORMULAS[v.tipo_carta];
    $("ka-dist").textContent = dist;
    $("ka-formula").textContent = formula;
    const carta = await api(`/variables/${v.id}/carta`);
    const sgs = carta.subgrupos || [];
    const tam = sgs.map((s) => s.tamano).filter((x) => x !== null);
    const total = tam.reduce((a, b) => a + b, 0);
    const d = sgs.reduce((a, s) => a + (s.conteo || 0), 0);
    $("ka-tamanos").textContent = tam.length ? `n: mín ${fmt(Math.min(...tam), 0)} · máx ${fmt(Math.max(...tam), 0)}` : "Unidad de inspección constante";
    $("ka-variable").textContent = carta.n_variable ? "Límites variables por muestra" : "Límites constantes";
    $("ka-m").textContent = sgs.length;
    $("ka-n").textContent = v.tipo_carta === "c" ? "—" : fmt(total, 0);
    $("ka-d-t").textContent = ["p", "np"].includes(v.tipo_carta) ? "Defectuosos" : "Defectos";
    $("ka-d").textContent = fmt(d, 0);
    $("ka-conf").textContent = ["p", "np"].includes(v.tipo_carta) && total ? pct(1 - d / total, 2) : "—";
    // El asistente arranca con la situación de la variable activa.
    $("as-tipo").value = ["p", "np"].includes(v.tipo_carta) ? "defectuosos" : "defectos";
    $("as-constante").value = carta.n_variable ? "false" : "true";
    $("as-interes").value = ["np", "c"].includes(v.tipo_carta) ? "conteo" : "proporcion";
  }

  document.addEventListener("DOMContentLoaded", () => {
    ["as-tipo", "as-constante", "as-interes"].forEach((id) => $(id).addEventListener("change", recomendar));
  });
  // Espera el contexto que carga comun.js.
  const espera = setInterval(async () => {
    if (!CEP.ctx) return;
    clearInterval(espera);
    if (CEP.ctx.variable) await tarjetas(CEP.ctx.variable).catch(() => {});
    recomendar();
  }, 100);
})();
