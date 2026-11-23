"""Generación de reportes PDF / Excel (core) y endpoints de reportes (API)."""
import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.core import capacidad, diseno_arl, figuras, graficos_variables as gv, supuestos
from app.core.reportes import construir_excel, construir_pdf, generar_conclusiones
from app.db import sesion
from tests.datos_montgomery import ANILLOS


@pytest.fixture(scope="module")
def contenido():
    carta = gv.calcular_xbar_r(ANILLOS)
    carta["etiquetas"] = list(range(1, 26))
    carta["subgrupos"] = [{"numero": i + 1, "timestamp": "2026-11-20T06:00:00", "fase": "I", "excluido": False}
                          for i in range(25)]
    cap = capacidad.analizar_capacidad(ANILLOS, 73.95, 74.05, 74.0)
    valores = [x for g in ANILLOS for x in g]
    cap["histograma"] = supuestos.histograma(valores)
    sup = supuestos.diagnostico(valores)
    dis = {"resumen": diseno_arl.diseno(3, 5, 1, 1), "curva": diseno_arl.curva_arl(3, 5, tamanos_comparar=[3, 10])}
    return {
        "folio": "REP-TEST-001", "plantilla": "integral", "titulo": "Informe de prueba", "fecha": "21/11/2026 10:00",
        "usuario": "Prueba", "modulos": ["resumen", "cartas", "alarmas", "capacidad", "supuestos", "diseno", "muestreo", "auditoria"],
        "proceso": {"nombre": "Ejemplos Montgomery", "planta": "Libro", "linea": "Cap. 6"},
        "variable": {"nombre": "Diámetro", "unidad": "mm", "tipo_carta": "xbar_r", "tipo_dato": "variables", "n": 5, "fase": "I",
                     "decimales": 3, "lei": 73.95, "objetivo": 74.0, "les": 74.05, "reglas": ["N1"], "version": 1},
        "sintesis_proceso": [{"variable": "Diámetro", "unidad": "mm", "especificacion": "73,95 – 74,05", "tipo": "X̄-R", "fase": "I",
                              "media": "74,001", "s": "0,0102", "cpk": "1,63", "estado": "Bajo control (Fase I)"}],
        "carta": carta, "limites_congelados": None, "capacidad": cap, "supuestos": sup, "diseno": dis,
        "alarmas": [], "exclusiones": [], "lotes": [{"codigo": "L1", "fecha": "2026-11-20T08:00:00", "N": 1000, "n": 50, "c": 1,
                                                    "defectos": 0, "p_hat": 0.0, "dictamen": "ACEPTADO", "usuario": "Ana"}],
        "historial": [{"fecha": "2026-11-20T08:00:00", "usuario": "Ana", "parametro": "les", "valor_anterior": "74.04",
                       "valor_nuevo": "74.05", "justificacion": "Plano rev. B", "version": 2, "hash": "a" * 64}],
        "conclusiones": generar_conclusiones(carta=carta, capacidad=cap, supuestos=sup),
    }


def test_figuras_png(contenido):
    for png in (figuras.carta_control(contenido["carta"]), figuras.histograma(contenido["capacidad"]["histograma"], 73.95, 74.05),
                figuras.qq_y_acf(contenido["supuestos"]["qq"], contenido["supuestos"]["independencia"]["acf"])):
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 5000


def test_pdf(contenido):
    pdf = construir_pdf(contenido)
    assert pdf[:5] == b"%PDF-" and len(pdf) > 30_000
    assert b"/DejaVu" in pdf or b"CEP" in pdf  # fuente con símbolos (σ, ≥, Δ) incrustada


def test_pdf_solo_resumen(contenido):
    pdf = construir_pdf({**contenido, "modulos": ["resumen"]})
    assert pdf[:5] == b"%PDF-" and len(pdf) < len(construir_pdf(contenido))


def test_excel(contenido):
    wb = load_workbook(io.BytesIO(construir_excel(contenido)))
    for hoja in ("Resumen", "Subgrupos", "Limites", "Capacidad", "Supuestos", "Diseno ARL", "Lotes", "Historial", "Graficos"):
        assert hoja in wb.sheetnames, hoja
    ws = wb["Subgrupos"]
    assert ws.max_row == 26 + 0  # cabecera + 25 subgrupos (sin título)
    assert ws.cell(2, 4).value == pytest.approx(74.010, abs=6e-4)  # X̄ del subgrupo 1 como número real
    assert len(wb["Graficos"]._images) >= 3


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@pytest.fixture
def c(tmp_path):
    sesion.configurar(f"sqlite:///{(tmp_path / 'rep.db').as_posix()}")
    from app.main import app

    with TestClient(app) as cliente:
        yield cliente


def test_api_reportes(c, tmp_path):
    assert set(c.get("/api/reportes/plantillas").json()["plantillas"]) == {"integral", "capacidad", "control", "auditoria"}
    prev = c.post("/api/reportes/vista-previa", json={"variable_id": 3, "plantilla": "capacidad"}).json()
    assert prev["modulos"] == ["resumen", "capacidad", "supuestos"]
    assert prev["capacidad"]["indices"]["cp"] == pytest.approx(1.67, abs=0.02)
    assert any(c_["seccion"] == "sintesis" for c_ in prev["conclusiones"])

    r = c.post("/api/reportes/generar", json={"variable_id": 3, "plantilla": "integral", "formato": "pdf", "usuario": "Ana"})
    assert r.status_code == 201
    rep = r.json()
    assert rep["nombre_archivo"].endswith(".pdf") and len(rep["sha256"]) == 64
    assert (tmp_path / "reportes" / rep["nombre_archivo"]).exists()  # junto a la base temporal, no en data/
    descarga = c.get(f"/api/reportes/{rep['id']}/descargar")
    assert descarga.content[:5] == b"%PDF-" and descarga.headers["x-sha256"] == rep["sha256"]
    assert c.get(f"/api/reportes/{rep['id']}/verificar").json()["integro"]

    # Si el archivo se altera, la verificación lo detecta.
    ruta = tmp_path / "reportes" / rep["nombre_archivo"]
    ruta.write_bytes(ruta.read_bytes() + b"%alterado")
    assert not c.get(f"/api/reportes/{rep['id']}/verificar").json()["integro"]

    x = c.post("/api/reportes/generar", json={"variable_id": 2, "plantilla": "control", "formato": "xlsx"}).json()
    assert x["formato"] == "xlsx"
    assert len(c.get("/api/reportes").json()) == 2
    assert len(c.get("/api/reportes?variable_id=2").json()) == 1


def test_api_reporte_variable_sin_datos(c):
    p = c.post("/api/procesos", json={"nombre": "Vacío"}).json()
    v = c.post(f"/api/procesos/{p['id']}/variables", json={"nombre": "X", "tipo_carta": "xbar_r", "n": 5}).json()
    r = c.post("/api/reportes/generar", json={"variable_id": v["id"], "plantilla": "integral", "formato": "pdf"})
    assert r.status_code == 201
