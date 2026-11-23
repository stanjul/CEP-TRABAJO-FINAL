"""Fase A del rediseño: asistente de variables, plan de muestreo (n, frecuencia, k, σ) y σ fijada.

Variables sembradas: 1 Peso neto (X̄-R, Fase II), 2 Envases defectuosos (p, Fase I),
3 Anillos (X̄-R, Fase I), 4 Préstamos (I-MR), 5 Circuitos (c), 6 Computadoras (u).
"""
import math
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db import sesion


@pytest.fixture
def c(tmp_path):
    sesion.configurar(f"sqlite:///{(tmp_path / 'prueba.db').as_posix()}")
    from app.main import app

    with TestClient(app) as cliente:
        yield cliente


# ---------------------------------------------------------------------------
# Asistente y alta de variables
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("consulta,carta", [
    ("que=medida&n=1", "imr"), ("que=medida&n=5", "xbar_r"), ("que=medida&n=15", "xbar_s"),
    ("que=defectuosos&tamano_constante=false", "p"), ("que=defectos&tamano_constante=true", "c"),
    ("que=defectos&tamano_constante=false", "u"),
])
def test_asistente_carta(c, consulta, carta):
    r = c.get(f"/api/asistente/carta?{consulta}").json()
    assert r["carta"] == carta
    assert "binomial" not in r["razon"].lower()  # explicación en lenguaje simple


def test_alta_con_usuario_y_eliminacion(c):
    p = c.post("/api/procesos", json={"nombre": "Horno 2", "linea": "Panificados"}).json()
    v = c.post(f"/api/procesos/{p['id']}/variables",
               json={"nombre": "  Peso del pan ", "unidad": "g", "tipo_carta": "xbar_r", "n": 4, "frecuencia_min": 60,
                     "lei": 480, "les": 520, "usuario": "L. Duarte"}).json()
    assert v["nombre"] == "Peso del pan" and v["sigma_monitoreo"] is None
    hist = c.get(f"/api/variables/{v['id']}/historial").json()
    assert hist[-1]["parametro"] == "alta" and hist[-1]["usuario"] == "L. Duarte"
    assert c.delete(f"/api/variables/{v['id']}").status_code == 200
    assert c.get(f"/api/variables/{v['id']}").status_code == 404


def test_alta_validaciones(c):
    assert c.post("/api/procesos", json={"nombre": "   "}).status_code == 422
    r = c.post("/api/procesos/1/variables", json={"nombre": "X", "tipo_carta": "xbar_r", "n": 1})
    assert r.status_code == 422
    r = c.post("/api/procesos/1/variables", json={"nombre": "X", "tipo_carta": "xbar_r", "n": 5, "lei": 10, "les": 5})
    assert r.status_code == 422
    # Atributos: se ignoran especificaciones y σ.
    v = c.post("/api/procesos/1/variables", json={"nombre": "Rayas", "tipo_carta": "c", "n": 1, "lei": 1, "les": 9,
                                                  "sigma_monitoreo": 2}).json()
    assert v["les"] is None and v["sigma_monitoreo"] is None


def test_no_se_elimina_variable_con_datos(c):
    r = c.delete("/api/variables/1")
    assert r.status_code == 409 and "trazabilidad" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Plan de muestreo: consulta
# ---------------------------------------------------------------------------

def test_plan_fase_ii_compara_actual_y_propuesto(c):
    r = c.get("/api/variables/1/plan?n=8&frecuencia_min=15&delta=1").json()
    assert r["referencia"]["origen"] == "límites congelados" and r["referencia"]["sigma"] > 0
    act, prop = r["actual"], r["propuesto"]
    assert prop["n"] == 8 and prop["frecuencia_min"] == 15
    assert prop["diseno"]["arl1"] < act["diseno"]["arl1"]  # más unidades por muestra ⇒ detecta antes
    assert prop["diseno"]["ats1"] == pytest.approx(prop["diseno"]["arl1"] * 0.25)
    assert prop["carga"]["unidades_por_hora"] == 32
    assert "falsa alarma" in prop["textos"]["falsa_alarma"]
    assert r["avisos"]  # cambiar n en Fase II recalcula límites y archiva el monitoreo


def test_plan_atributos_usa_nivel_de_defectos(c):
    r = c.get("/api/variables/2/plan").json()
    assert r["referencia"]["origen"] == "datos de la Fase I"
    p0 = r["referencia"]["centro"]
    assert r["centro_1"] == pytest.approx(2 * p0)
    d = r["propuesto"]["diseno"]
    assert 0 < d["alfa"] < 0.05 and d["arl1"] < d["arl0"]
    assert "%" in r["propuesto"]["textos"]["deteccion"]


def test_plan_atributos_sin_datos_con_centro_indicado(c):
    v = c.post("/api/procesos/1/variables", json={"nombre": "Etiquetas", "tipo_carta": "p", "n": 100}).json()
    r = c.get(f"/api/variables/{v['id']}/plan").json()
    assert r["propuesto"]["diseno"] is None and r["propuesto"]["textos"]["carga"]
    r = c.get(f"/api/variables/{v['id']}/plan?centro=0.03&centro_1=0.08").json()
    assert r["referencia"]["origen"] == "indicado por el usuario"
    assert r["propuesto"]["diseno"]["arl1"] > 1


# ---------------------------------------------------------------------------
# Plan de muestreo: guardar
# ---------------------------------------------------------------------------

def test_cambiar_frecuencia_no_recalcula_limites(c):
    r = c.post("/api/variables/1/plan", json={"frecuencia_min": 15, "usuario": "Ing. Paz",
                                               "justificacion": "Más control en arranque"}).json()
    assert r["variable"]["frecuencia_min"] == 15 and not r["limites_recalculados"]
    assert c.get("/api/variables/1/operario").json()["variable"]["frecuencia_min"] == 15


def test_cambiar_n_en_fase_ii_recalcula_con_sigma_congelada(c):
    antes = c.get("/api/variables/1").json()["limites_congelados"]["datos"]
    c.post("/api/variables/1/subgrupos", json={"valores": [500.1, 500.2, 499.9, 500.0, 500.3]})
    r = c.post("/api/variables/1/plan", json={"n": 8, "usuario": "Ing. Paz", "justificacion": "Detectar antes"}).json()
    assert r["limites_recalculados"] and r["archivados"] == 1
    nuevos = c.get("/api/variables/1").json()["limites_congelados"]["datos"]
    assert nuevos["n"] == 8
    assert nuevos["sigma_hat"] == pytest.approx(antes["sigma_hat"])
    assert nuevos["xbar"]["lc"] == pytest.approx(antes["xbar"]["lc"])
    assert nuevos["xbar"]["lcs"] == pytest.approx(antes["xbar"]["lc"] + 3 * antes["sigma_hat"] / math.sqrt(8))
    # La carta de Fase II arranca vacía y ahora pide 8 mediciones.
    assert c.get("/api/variables/1/carta").json()["subgrupos"] == []
    assert c.post("/api/variables/1/subgrupos", json={"valores": [500.0] * 5}).status_code == 422
    assert c.post("/api/variables/1/subgrupos", json={"valores": [500.0] * 8}).status_code == 201
    params = [h["parametro"] for h in c.get("/api/variables/1/historial").json()[:3]]
    assert {"n", "limites", "subgrupos archivados"} <= set(params)


def test_sigma_del_ingeniero_en_fase_ii_y_volver_a_estimada(c):
    antes = c.get("/api/variables/1").json()["limites_congelados"]["datos"]
    r = c.post("/api/variables/1/plan", json={"sigma_monitoreo": 1.5, "justificacion": "σ histórica de la planta"})
    assert r.json()["limites_recalculados"]
    lim = c.get("/api/variables/1").json()["limites_congelados"]["datos"]
    assert lim["sigma_hat"] == 1.5
    assert lim["xbar"]["lcs"] == pytest.approx(antes["xbar"]["lc"] + 3 * 1.5 / math.sqrt(5))
    r = c.post("/api/variables/1/plan", json={"borrar_sigma": True, "justificacion": "Volver a la σ de los datos"})
    lim = c.get("/api/variables/1").json()["limites_congelados"]["datos"]
    assert lim["sigma_hat"] == pytest.approx(antes["sigma_hat"])
    assert c.get("/api/variables/1").json()["sigma_monitoreo"] is None


def test_k_en_fase_ii(c):
    antes = c.get("/api/variables/1").json()["limites_congelados"]["datos"]
    c.post("/api/variables/1/plan", json={"k_sigma": 2.5, "justificacion": "Más sensibilidad"})
    lim = c.get("/api/variables/1").json()["limites_congelados"]["datos"]
    assert lim["xbar"]["lcs"] == pytest.approx(antes["xbar"]["lc"] + 2.5 * antes["sigma_hat"] / math.sqrt(5))
    # Las muestras de monitoreo no se archivan si solo cambia k.
    assert c.post("/api/variables/1/plan", json={"k_sigma": 3, "justificacion": "x" * 3}).json()["archivados"] == 0


def test_cambiar_n_en_fase_i_con_datos_pide_confirmacion(c):
    r = c.post("/api/variables/3/plan", json={"n": 4, "justificacion": "Prueba"})
    assert r.status_code == 409 and "empezar la Fase I de nuevo" in r.json()["detail"]
    r = c.post("/api/variables/3/plan", json={"n": 4, "justificacion": "Prueba", "reiniciar_fase_i": True}).json()
    assert r["archivados"] == 25 and r["variable"]["n"] == 4
    assert c.get("/api/variables/3/carta").json()["vacio"]


def test_sigma_fijada_en_fase_i(c):
    libre = c.get("/api/variables/3/carta").json()
    c.post("/api/variables/3/plan", json={"sigma_monitoreo": 0.01, "justificacion": "Norma de la empresa"})
    fija = c.get("/api/variables/3/carta").json()
    assert fija["fase"] == "I" and fija["estimador"] == "σ fijada por el ingeniero"
    assert fija["sigma_hat"] == 0.01
    assert fija["limites"]["sigma_estimada_datos"] == pytest.approx(libre["sigma_hat"])
    centro = libre["limites"]["xbar"]["lc"]
    assert fija["cartas"]["xbar"]["lcs"] == pytest.approx(centro + 0.03 / math.sqrt(5))
    # Al congelar, la Fase II hereda la σ fijada.
    c.post("/api/variables/3/congelar", json={"usuario": "Ing. Paz"})
    assert c.get("/api/variables/3").json()["limites_congelados"]["datos"]["sigma_hat"] == 0.01


def test_validaciones_del_plan(c):
    assert c.post("/api/variables/2/plan", json={"sigma_monitoreo": 1, "justificacion": "abc"}).status_code == 422
    assert c.post("/api/variables/4/plan", json={"n": 5, "justificacion": "abc"}).status_code == 422
    assert c.post("/api/variables/1/plan", json={"n": 5}).status_code == 422  # sin justificación
    # Por PATCH, σ sigue bloqueada en Fase II (el camino es el plan, que recalcula límites).
    r = c.patch("/api/variables/1", json={"sigma_monitoreo": 2, "justificacion": "abc"})
    assert r.status_code == 409


def test_k_en_atributos_fase_ii(c):
    c.post("/api/variables/2/congelar", json={})
    antes = c.get("/api/variables/2/carta").json()["cartas"]["p"]
    c.post("/api/variables/2/plan", json={"k_sigma": 2, "justificacion": "Prueba"})
    lim = c.get("/api/variables/2").json()["limites_congelados"]["datos"]
    assert lim["k"] == 2
    despues = c.get("/api/variables/2/carta").json()["cartas"]["p"]
    assert despues["lc"] == antes["lc"]


# ---------------------------------------------------------------------------
# Fase B: capacidad solo con Cp / Cpk (sin Pp / Ppk) y con la σ del plan
# ---------------------------------------------------------------------------

def test_capacidad_sin_pp_ppk_y_con_sigma_fijada(c):
    r = c.get("/api/variables/3/capacidad").json()
    assert set(r["indices"]) == {"cp", "cpk", "cpu", "cpl"}
    assert "largo_plazo" not in r and "sigma_global" not in r
    assert "Ppk" not in " ".join(x["texto"] for x in r["conclusiones"])
    c.post("/api/variables/3/plan", json={"sigma_monitoreo": 0.01, "justificacion": "Norma"})
    r = c.get("/api/variables/3/capacidad").json()
    assert r["metodo_sigma"] == "fijada" and r["indices"]["cp"] == pytest.approx(0.10 / 0.06)
    # Elegir un estimador explícito ignora la σ fijada (comparación en la pantalla).
    assert c.get("/api/variables/3/capacidad?metodo=rbar").json()["metodo_sigma"] == "rbar"
    op = c.get("/api/variables/1/operario").json()["capacidad"]
    assert "ppk" not in op and op["ppm_esperado"] >= 0


# ---------------------------------------------------------------------------
# Migración de una base anterior (sin la columna sigma_monitoreo)
# ---------------------------------------------------------------------------

def test_migracion_agrega_columna(tmp_path):
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE variables (id INTEGER PRIMARY KEY, nombre VARCHAR(120))")
    con.commit()
    con.close()
    sesion.configurar(f"sqlite:///{ruta.as_posix()}")
    sesion.migrar_columnas()
    con = sqlite3.connect(ruta)
    columnas = [fila[1] for fila in con.execute("PRAGMA table_info(variables)")]
    con.close()
    assert "sigma_monitoreo" in columnas
