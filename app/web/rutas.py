"""Rutas HTML: cada pantalla es una plantilla Jinja2 derivada de Stitch + un JS que consume /api."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

DIR = Path(__file__).resolve().parent
plantillas = Jinja2Templates(directory=DIR / "templates")
router = APIRouter(include_in_schema=False)

# id de página → (plantilla, vista, título)
PANTALLAS = {
    "/operario": ("operario.html", "operario", "inspeccion", "Registrar muestra"),
    "/operario/proceso": ("operario_proceso.html", "operario", "proceso", "Cómo va el proceso"),
    "/operario/alertas": ("operario_alertas.html", "operario", "alertas", "Alertas"),
    "/operario/historial": ("operario_historial.html", "operario", "historial", "Historial de muestras"),
    "/ingenieria/mis-variables": ("ing_mis_variables.html", "ingenieria", "mis_variables", "Variables a controlar"),
    "/ingenieria/plantilla": ("ing_plantilla.html", "ingenieria", "plantilla", "Plantilla de carga"),
    "/ingenieria/datos": ("ing_datos.html", "ingenieria", "datos", "Datos & Carga CSV"),
    "/ingenieria/variables": ("ing_variables.html", "ingenieria", "variables", "Gráficos por Variables"),
    "/ingenieria/atributos": ("ing_atributos.html", "ingenieria", "atributos", "Gráficos por Atributos"),
    "/ingenieria/supuestos": ("ing_supuestos.html", "ingenieria", "supuestos", "Validación de Supuestos"),
    "/ingenieria/capacidad": ("ing_capacidad.html", "ingenieria", "capacidad", "Capacidad de Proceso"),
    "/ingenieria/diseno": ("ing_diseno.html", "ingenieria", "diseno", "Plan de muestreo"),
    "/ingenieria/muestreo": ("ing_muestreo.html", "ingenieria", "muestreo", "Muestreo de Aceptación"),
    "/ingenieria/configuracion": ("ing_configuracion.html", "ingenieria", "configuracion", "Configuración y Auditoría"),
    "/ingenieria/reportes": ("ing_reportes.html", "ingenieria", "reportes", "Reportes"),
    "/ingenieria/base-de-datos": ("ing_base_datos.html", "ingenieria", "base_datos", "Base de datos y respaldos"),
}


def _registrar(ruta: str, plantilla: str, vista: str, pagina: str, titulo: str) -> None:
    def vista_html(request: Request):
        if not (DIR / "templates" / plantilla).exists():
            return HTMLResponse(f"<p>La pantalla «{titulo}» aún no está disponible.</p>", status_code=501)
        return plantillas.TemplateResponse(request, plantilla, {"vista": vista, "pagina": pagina, "titulo": titulo})

    router.add_api_route(ruta, vista_html, methods=["GET"], response_class=HTMLResponse, name=pagina + "_" + vista)


for _ruta, (_p, _v, _id, _t) in PANTALLAS.items():
    _registrar(_ruta, _p, _v, _id, _t)


@router.get("/")
def inicio():
    return RedirectResponse("/operario")


@router.get("/ingenieria")
def ingenieria():
    return RedirectResponse("/ingenieria/variables")
