"""Plantilla de carga por la API: generar, revisar, importar, no duplicar y respetar las fases.

Variables sembradas: 1 Peso neto (X̄-R, Fase II, 19 subgrupos), 2 Envases defectuosos (p, Fase I),
3 Anillos (X̄-R, Fase I, 25 subgrupos).
"""
import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.db import sesion

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def c(tmp_path):
    sesion.configurar(f"sqlite:///{(tmp_path / 'plantilla.db').as_posix()}")
    from app.main import app

    with TestClient(app) as cliente:
        yield cliente


def descargar(c, pedido):
    r = c.post("/api/plantillas/generar", json=pedido)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == XLSX
    return r.content


def llenar(datos, hoja, filas: dict[int, list], col_inicio=4):
    """Escribe valores desde la columna D (primer dato) en las filas indicadas."""
    wb = load_workbook(io.BytesIO(datos))
    ws = wb[hoja]
    for fila, valores in filas.items():
        for j, x in enumerate(valores):
            ws.cell(fila, col_inicio + j, x)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def subir(c, ruta, datos, **form):
    return c.post(f"/api/plantillas/{ruta}", files={"archivo": ("plantilla.xlsx", datos, XLSX)}, data=form)


def test_sugerencia(c):
    s = c.get("/api/plantillas/sugerencia?proceso_id=1").json()
    peso = next(v for v in s["variables"] if v["id"] == 1)
    assert peso["siguiente_numero"] == 20 and peso["fase_i_sugerida"] == 0 and peso["fase_ii_sugerida"] == 25
    env = next(v for v in s["variables"] if v["id"] == 2)
    assert env["fase_i_sugerida"] == 0  # ya tiene 30 muestras en Fase I


def test_variable_existente_en_monitoreo(c):
    pedido = {"proceso_id": 1, "variables": [{"id": 1, "fase_i": 0, "fase_ii": 3}]}
    datos = descargar(c, pedido)
    ws = load_workbook(io.BytesIO(datos))["Peso neto"]
    assert ws.cell(7, 1).value == 20  # sigue la numeración de la variable
    datos = llenar(datos, "Peso neto", {7: [500.1, 499.9, 500.2, 500.0, 499.8], 8: [500, 500, 500]})
    rev = subir(c, "revisar", datos).json()
    v = rev["variables"][0]
    assert v["a_cargar"] == 1 and v["numeros"] == [20] and v["vacias"] == 1
    assert "Muestra 21: faltan valores" in v["errores"][0]["texto"]
    assert c.get("/api/variables/1/carta").json()["subgrupos"] == []  # revisar no guarda nada

    r = subir(c, "importar", datos, usuario="Ana").json()
    assert r["total"] == 1
    sg = c.get("/api/variables/1/carta").json()["subgrupos"]
    assert [s["numero"] for s in sg] == [20] and sg[0]["origen"] == "plantilla"
    # Subir el mismo archivo otra vez no duplica.
    assert subir(c, "importar", datos).json()["total"] == 0
    hist = c.get("/api/variables/1/historial").json()
    assert hist[0]["parametro"] == "importacion" and "Plantilla «plantilla.xlsx»" in hist[0]["justificacion"]


def test_proceso_y_variables_nuevas_con_fases(c):
    pedido = {"proceso_nombre": "Horno 3", "proceso_linea": "Panificados", "variables": [
        {"nombre": "Peso del pan", "unidad": "g", "que": "medida", "n": 2, "decimales": 1, "lei": 480, "les": 520,
         "fase_i": 3, "fase_ii": 2, "frecuencia_min": 30},
        {"nombre": "Panes quemados", "que": "defectuosos", "n": 20, "fase_i": 2, "fase_ii": 0},
    ]}
    datos = descargar(c, pedido)
    # Peso: 3 muestras de Fase I (filas 7–9) y 1 de monitoreo (fila 11); Panes: 2 muestras (revisadas + defectuosas).
    datos = llenar(datos, "Peso del pan", {7: [500, 501], 8: [499, 502], 9: [498, 500], 11: [503, 504]})
    datos = llenar(datos, "Panes quemados", {7: [20, 1], 8: [20, 3]})
    rev = subir(c, "revisar", datos).json()
    peso = rev["variables"][0]
    assert peso["nueva"] and peso["a_cargar"] == 3 and peso["otra_fase"] == 1
    assert any("primero hay que fijar los límites" in a["texto"] for a in peso["avisos"])

    r = subir(c, "importar", datos, usuario="Ana").json()
    assert r["total"] == 5
    procesos = c.get("/api/procesos").json()
    horno = next(p for p in procesos if p["nombre"] == "Horno 3")
    nombres = {v["nombre"]: v for v in horno["variables"]}
    assert nombres["Peso del pan"]["tipo_carta"] == "xbar_r" and nombres["Peso del pan"]["muestras"] == 3
    assert nombres["Panes quemados"]["tipo_carta"] == "p" and nombres["Panes quemados"]["muestras"] == 2

    # Se fijan los límites y se vuelve a subir el mismo archivo: entra la muestra de monitoreo y nada se duplica.
    pid = nombres["Peso del pan"]["id"]
    c.post(f"/api/variables/{pid}/congelar", json={"usuario": "Ana"})
    r2 = subir(c, "importar", datos).json()
    assert r2["total"] == 1
    assert len([p for p in c.get("/api/procesos").json() if p["nombre"] == "Horno 3"]) == 1  # no se recrea el proceso
    assert [s["numero"] for s in c.get(f"/api/variables/{pid}/carta").json()["subgrupos"]] == [4]


def test_validaciones_del_pedido(c):
    assert c.post("/api/plantillas/generar", json={"variables": [{"id": 1}]}).status_code == 422  # falta proceso
    r = c.post("/api/plantillas/generar", json={"proceso_id": 1, "variables": [{"nombre": "X", "fase_i": 5}]})
    assert r.status_code == 422 and "cómo se registra" in r.json()["detail"]
    r = c.post("/api/plantillas/generar", json={"proceso_id": 1, "variables": [{"id": 3}]})  # Anillos es de otro proceso
    assert r.status_code == 422 and "no pertenece" in r.json()["detail"]
    r = c.post("/api/plantillas/generar", json={"proceso_id": 1, "variables": [{"id": 1, "fase_i": 0, "fase_ii": 0}]})
    assert r.status_code == 422


def test_archivo_que_no_es_plantilla(c):
    r = subir(c, "revisar", b"hola")
    assert r.status_code == 422 and "No se pudo abrir" in r.json()["detail"]
