"""Las pantallas HTML se sirven, incluyen sus scripts y los recursos locales existen (sin internet)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import sesion
from app.web.rutas import PANTALLAS

STATIC = Path(__file__).resolve().parents[1] / "app" / "web" / "static"


@pytest.fixture
def c(tmp_path):
    sesion.configurar(f"sqlite:///{(tmp_path / 'web.db').as_posix()}")
    from app.main import app

    with TestClient(app) as cliente:
        yield cliente


@pytest.mark.parametrize("ruta", list(PANTALLAS))
def test_pantallas_responden(c, ruta):
    r = c.get(ruta)
    assert r.status_code == 200
    html = r.text
    assert "/static/vendor/tailwindcss.js" in html and "/static/js/comun.js" in html
    assert 'id="sel-variable"' in html  # selector de proceso / variable del header
    assert "googleapis" not in html and "cdn.tailwindcss.com" not in html  # todo local


def test_redirecciones(c):
    assert c.get("/", follow_redirects=False).headers["location"] == "/operario"
    assert c.get("/ingenieria", follow_redirects=False).headers["location"] == "/ingenieria/variables"


def test_recursos_locales():
    for archivo in ["vendor/tailwindcss.js", "vendor/plotly.min.js", "vendor/fuentes.css", "js/tailwind-config.js",
                    "js/comun.js", "js/graficos.js", "css/estilos.css", "img/logo.svg", "plantilla_datos.csv"]:
        assert (STATIC / archivo).exists(), archivo
    css = (STATIC / "vendor" / "fuentes.css").read_text(encoding="utf-8")
    for fuente in ("League Spartan", "Montserrat", "Material Symbols Outlined"):
        assert fuente in css
    assert "https://" not in css
    # Cada archivo de fuente declarado existe (la app funciona sin internet).
    import re
    for archivo in re.findall(r"url\((fuentes/[^)]+)\)", css):
        assert (STATIC / "vendor" / archivo).exists(), archivo
    config = (STATIC / "js" / "tailwind-config.js").read_text(encoding="utf-8")
    assert '"headline-lg":["League Spartan"' in config and '"body-md":["Montserrat"' in config


def test_js_propios_se_revalidan(c):
    """Tras actualizar la app, el navegador no debe quedarse con un JS viejo en caché."""
    assert c.get("/static/js/graficos.js").headers["cache-control"] == "no-cache"
    assert "no-cache" not in c.get("/static/vendor/fuentes.css").headers.get("cache-control", "")


def test_vista_activa_en_menu(c):
    html = c.get("/ingenieria/capacidad").text
    assert 'aria-current="page"' in html and "Suite de Ingeniería" in html
    op = c.get("/operario").text
    assert "Cómo va el proceso" in op and "Registrar muestra" in op
    # El menú lateral del operario no lleva a pantallas de Ingeniería (solo la pestaña del header).
    menu = op.split("<aside", 1)[1].split("</aside>", 1)[0]
    assert "/ingenieria/" not in menu
