"""Fase C del rediseño: vista Operario en palabras simples, deshacer el último registro y modo demo.

Variables sembradas: 1 Peso neto (X̄-R, Fase II), 2 Envases defectuosos (p, Fase I),
3 Anillos (X̄-R), 4 Préstamos (I-MR), 5 Circuitos (c), 6 Computadoras (u).
"""
import csv
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import sesion
from app.db.modelos import ahora

CARPETA = Path(__file__).resolve().parents[1] / "datos_prueba"


@pytest.fixture
def c(tmp_path):
    sesion.configurar(f"sqlite:///{(tmp_path / 'prueba.db').as_posix()}")
    from app.main import app

    with TestClient(app) as cliente:
        yield cliente


def simulado():
    grupos = {}
    with open(CARPETA / "proceso_simulado.csv", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            grupos.setdefault(int(fila["subgrupo"]), []).append(float(fila["peso_neto_g"]))
    return [grupos[k] for k in sorted(grupos)]


def test_resumen_en_palabras(c):
    op = c.get("/api/variables/1/operario").json()
    assert op["semaforo"]["titulo"] == "El proceso va bien"
    assert op["semaforo"]["que_hacer"]
    assert op["modo_demo"] is True  # la semilla activa el modo demostración
    assert op["rango_habitual"]["sigma"] > 0 and 495 < op["rango_habitual"]["centro"] < 505
    # Fase II recién iniciada: la ventana todavía no tiene muestras.
    assert op["ventana"]["muestras"] == 0
    f1 = c.get("/api/variables/3/operario").json()
    assert f1["semaforo"]["titulo"] == "Conociendo el proceso"
    v = f1["ventana"]
    assert v["muestras"] == 25 and v["unidades"] == 125 and 0 <= v["pct_dentro"] <= 1
    p = c.get("/api/variables/2/operario").json()["ventana"]
    assert 0 < p["pct_defectuosos"] < 1


def test_alarma_explicada_en_palabras(c):
    datos = simulado()
    r = c.post("/api/variables/1/subgrupos", json={"valores": datos[19], "usuario": "Op"}).json()
    a = r["alarmas_nuevas"][0]
    assert a["regla"] == "N1"
    assert a["explicacion"].startswith("Un valor quedó por encima de los límites normales")
    op = c.get("/api/variables/1/operario").json()
    assert op["semaforo"]["titulo"] == "Detener y avisar"
    assert all(x["explicacion"] for x in op["alarmas_abiertas"])


def test_deshacer_ultimo_registro(c):
    datos = simulado()
    r = c.post("/api/variables/1/subgrupos", json={"valores": datos[19], "usuario": "Op"}).json()
    numero = r["subgrupo"]["numero"]
    assert c.get("/api/variables/1/operario").json()["segundos_para_deshacer"] > 0
    d = c.post("/api/variables/1/deshacer-ultimo", json={"usuario": "Op", "motivo": "Escribí mal un valor"})
    assert d.status_code == 200 and d.json()["anulado"] == numero
    op = c.get("/api/variables/1/operario").json()
    # La alarma que generó el registro queda cerrada y el semáforo vuelve a verde.
    assert op["semaforo"]["color"] == "verde" and not op["alarmas_abiertas"]
    assert op["proximo_numero"] == numero + 1  # el número anulado no se reutiliza
    assert c.get("/api/variables/1/carta").json()["subgrupos"] == []
    hist = c.get("/api/variables/1/subgrupos").json()
    anulado = next(s for s in hist if s["numero"] == numero)
    assert anulado["fase"] == "anulado" and "Escribí mal" in anulado["comentario"]
    cambios = c.get("/api/variables/1/historial").json()
    assert cambios[0]["parametro"] == f"anulación subgrupo #{numero}" and cambios[0]["usuario"] == "Op"
    # No se puede deshacer dos veces seguidas (el anterior es de la semilla).
    assert c.post("/api/variables/1/deshacer-ultimo", json={}).status_code == 409


def test_deshacer_fuera_de_tiempo(c):
    viejo = (ahora() - timedelta(minutes=20)).isoformat()
    c.post("/api/variables/1/subgrupos", json={"valores": [500.0] * 5, "timestamp": viejo})
    assert c.get("/api/variables/1/operario").json()["segundos_para_deshacer"] == 0
    r = c.post("/api/variables/1/deshacer-ultimo", json={})
    assert r.status_code == 409 and "10 minutos" in r.json()["detail"]


def test_modo_demo(c):
    assert c.get("/api/ajustes/modo-demo").json() == {"activo": True}
    assert c.put("/api/ajustes/modo-demo", json={"activo": False}).json() == {"activo": False}
    assert c.get("/api/variables/1/operario").json()["modo_demo"] is False
