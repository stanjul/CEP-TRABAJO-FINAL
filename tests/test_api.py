"""Pruebas de la API y la base de datos con una base SQLite temporal sembrada.

Variables sembradas: 1 Peso neto (X̄-R, Fase II), 2 Envases defectuosos (p, Fase I),
3 Anillos (X̄-R), 4 Préstamos (I-MR), 5 Circuitos (c), 6 Computadoras (u).
"""
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import servicios as sv
from app.db import sesion

CARPETA = Path(__file__).resolve().parents[1] / "datos_prueba"


@pytest.fixture
def c(tmp_path):
    sesion.configurar(f"sqlite:///{(tmp_path / 'prueba.db').as_posix()}")
    from app.main import app

    with TestClient(app) as cliente:
        yield cliente


def simulado():
    """Subgrupos del proceso simulado (lista de 25 listas de 5)."""
    import csv
    grupos = {}
    with open(CARPETA / "proceso_simulado.csv", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            grupos.setdefault(int(fila["subgrupo"]), []).append(float(fila["peso_neto_g"]))
    return [grupos[k] for k in sorted(grupos)]


# ---------------------------------------------------------------------------
# Semilla y consultas básicas
# ---------------------------------------------------------------------------

def test_semilla(c):
    procesos = c.get("/api/procesos").json()
    assert [p["nombre"] for p in procesos] == ["Línea de Envasado L-04", "Ejemplos Montgomery"]
    peso = c.get("/api/variables/1").json()
    assert peso["fase"] == "II" and peso["limites_congelados"]["m_usados"] == 19
    assert len(c.get("/api/reglas").json()["catalogo"]) == 9
    assert len(c.get("/api/constantes").json()) == 24
    assert c.get("/api/salud").json()["estado"] == "ok"


def test_variable_inexistente(c):
    assert c.get("/api/variables/999/carta").status_code == 404


def test_json_sin_nan(c):
    """El primer MR no existe: debe llegar como null (no NaN, que rompe el JSON)."""
    r = c.get("/api/variables/4/carta")
    assert r.status_code == 200
    assert r.json()["cartas"]["mr"]["valores"][0] is None


# ---------------------------------------------------------------------------
# Vista de operario: Fase II con el corrimiento del proceso simulado
# ---------------------------------------------------------------------------

def test_flujo_operario_detecta_corrimiento(c):
    op = c.get("/api/variables/1/operario").json()
    assert op["semaforo"]["color"] == "verde"
    assert op["proximo_numero"] == 20
    assert op["capacidad"]["cpk"] > 1.33  # base de Fase I mientras no hay datos de Fase II

    datos = simulado()
    r = c.post("/api/variables/1/subgrupos", json={"valores": datos[19], "usuario": "C. Mendoza"})
    assert r.status_code == 201
    assert r.json()["subgrupo"]["numero"] == 20
    assert [a["regla"] for a in r.json()["alarmas_nuevas"]] == ["N1"]
    for g in datos[20:]:
        c.post("/api/variables/1/subgrupos", json={"valores": g, "usuario": "C. Mendoza"})

    op = c.get("/api/variables/1/operario").json()
    assert op["semaforo"]["color"] == "rojo"
    assert len(op["carta"]["cartas"]["xbar"]["valores"]) == 6
    assert op["carta"]["etiquetas"] == [20, 21, 22, 23, 24, 25]
    reglas = {a["regla"] for a in op["alarmas_abiertas"]}
    assert {"N1", "N5"} <= reglas
    # Las rachas no se duplican: N5 se dispara al inicio de la secuencia, no en cada punto.
    assert sum(a["regla"] == "N5" for a in op["alarmas_abiertas"]) < 4
    assert c.get("/api/alarmas/contador?variable_id=1").json()["pendientes"] == len(op["alarmas_abiertas"])


def test_alarma_causa_accion_trazada(c):
    datos = simulado()
    alarma = c.post("/api/variables/1/subgrupos", json={"valores": datos[19]}).json()["alarmas_nuevas"][0]
    # Resolver sin causa/acción no se permite.
    r = c.patch(f"/api/alarmas/{alarma['id']}", json={"estado": "resuelta", "usuario": "Ana"})
    assert r.status_code == 422
    r = c.patch(f"/api/alarmas/{alarma['id']}", json={"estado": "resuelta", "causa": "Cambio de lote de envase",
                                                       "accion": "Ajuste de tara", "usuario": "Ana"})
    a = r.json()
    assert a["estado"] == "resuelta" and a["usuario"] == "Ana" and a["cerrada"]
    assert c.get("/api/variables/1/operario").json()["semaforo"]["color"] == "verde"
    assert c.get("/api/alarmas?variable_id=1&estado=resuelta").json()[0]["causa"] == "Cambio de lote de envase"


def test_evento_manual(c):
    r = c.post("/api/variables/1/eventos", json={"tipo": "retencion", "descripcion": "Lote retenido por inspección"})
    assert r.status_code == 201 and r.json()["severidad"] == "critica"
    assert c.get("/api/variables/1/operario").json()["semaforo"]["color"] == "rojo"


def test_validacion_registro(c):
    assert c.post("/api/variables/1/subgrupos", json={"valores": [500, 501]}).status_code == 422
    assert c.post("/api/variables/2/subgrupos", json={"conteo": 60}).status_code == 422  # > n = 50
    r = c.post("/api/variables/2/subgrupos", json={"conteo": 10})
    assert r.status_code == 201 and r.json()["subgrupo"]["tamano"] == 50


def test_simular_valores(c):
    r = c.get("/api/variables/1/simular-valores?delta=1.5&semilla=1").json()
    assert len(r["valores"]) == 5
    assert "conteo" in c.get("/api/variables/2/simular-valores").json()


# ---------------------------------------------------------------------------
# Fase I: exclusión, recálculo, congelamiento y vuelta a Fase I (carta p del libro)
# ---------------------------------------------------------------------------

def test_fase_i_carta_p_montgomery(c):
    carta = c.get("/api/variables/2/carta").json()
    assert carta["etiquetas"][carta["puntos_con_senal"][0]] == 15
    assert carta["cartas"]["p"]["lc"] == pytest.approx(0.2313, abs=5e-5)
    ids = {s["numero"]: s["id"] for s in carta["subgrupos"]}

    sim = c.post("/api/variables/2/simular-exclusion", json={"excluidos": [15, 23]}).json()
    assert sim["despues"]["lc"] == pytest.approx(0.2150, abs=5e-5)
    assert sim["senales_despues"] == [21]  # el libro señala que la muestra 21 supera el LCS revisado

    assert c.patch(f"/api/subgrupos/{ids[15]}", json={"excluido": True}).status_code == 422  # falta la causa
    for num, causa in [(15, "Lote nuevo de cartón"), (23, "Operario sin experiencia")]:
        r = c.patch(f"/api/subgrupos/{ids[num]}", json={"excluido": True, "causa": causa, "usuario": "Ing. Soto"})
        assert r.status_code == 200 and r.json()["excluido"]
    carta = c.get("/api/variables/2/carta").json()
    assert carta["cartas"]["p"]["lcs"] == pytest.approx(0.3893, abs=5e-5)

    r = c.post("/api/variables/2/congelar", json={"usuario": "Ing. Soto", "motivo": "Base revisada"}).json()
    assert r["limites"]["m_usados"] == 28
    assert any("21" in a for a in r["advertencias"])
    assert c.get("/api/variables/2").json()["fase"] == "II"

    # Fase II: los límites no se recalculan.
    c.post("/api/variables/2/subgrupos", json={"conteo": 30})
    f2 = c.get("/api/variables/2/carta").json()
    assert f2["fase"] == "II" and f2["cartas"]["p"]["lc"] == pytest.approx(0.2150, abs=5e-5)
    assert f2["puntos_con_senal"] == [0]

    assert c.post("/api/variables/2/volver-fase-i", json={}).status_code == 422  # motivo obligatorio
    r = c.post("/api/variables/2/volver-fase-i", json={"motivo": "Cambio de proveedor", "usuario": "Ing. Soto"})
    assert r.json()["fase"] == "I"
    historial = c.get("/api/variables/2/historial").json()
    parametros = [h["parametro"] for h in historial]
    assert "exclusion subgrupo #15" in parametros and parametros.count("fase") == 2
    assert len(c.get("/api/variables/2/limites").json()) == 1


def test_fase_ii_sin_limites_409(c):
    assert c.get("/api/variables/3/carta?fase=II").status_code == 409


# ---------------------------------------------------------------------------
# Configuración con historial
# ---------------------------------------------------------------------------

def test_configuracion_historial(c):
    r = c.patch("/api/variables/1", json={"les": 506, "frecuencia_min": 30, "usuario": "Ing. Benítez",
                                          "justificacion": "Nueva especificación del cliente"})
    assert r.status_code == 200
    cambios = r.json()["cambios"]
    assert {x["parametro"] for x in cambios} == {"les", "frecuencia_min"}
    les = next(x for x in cambios if x["parametro"] == "les")
    assert les["valor_anterior"] == "505.0" and les["valor_nuevo"] == "506.0"
    assert len(cambios[0]["hash"]) == 64
    v = c.get("/api/variables/1").json()
    assert v["les"] == 506 and v["hash"] == cambios[0]["hash"]
    assert c.get("/api/variables/1/historial?texto=cliente").json()[0]["usuario"] == "Ing. Benítez"


def test_configuracion_validaciones(c):
    # n y tipo de carta no se cambian con límites congelados.
    assert c.patch("/api/variables/1", json={"n": 4, "justificacion": "prueba"}).status_code == 409
    assert c.patch("/api/variables/3", json={"lei": 80, "justificacion": "prueba"}).status_code == 422  # LEI > LES
    assert c.patch("/api/variables/3", json={"reglas": ["N1", "X9"], "justificacion": "prueba"}).status_code == 422
    assert c.patch("/api/variables/3", json={"les": 1}).status_code == 422  # falta justificación
    r = c.patch("/api/variables/3", json={"borrar": ["lei"], "justificacion": "Especificación unilateral"})
    assert r.json()["variable"]["lei"] is None


def test_crear_proceso_y_variable(c):
    p = c.post("/api/procesos", json={"nombre": "Torque de tapa"}).json()
    v = c.post(f"/api/procesos/{p['id']}/variables", json={"nombre": "Torque", "unidad": "lbf·in",
                                                           "tipo_carta": "xbar_s", "n": 4}).json()
    assert v["estimador_sigma"] == "sbar" and v["fase"] == "I" and v["tipo_dato"] == "variables"
    assert c.get(f"/api/variables/{v['id']}/carta").json()["vacio"]


def test_turnos(c):
    assert len(c.get("/api/ajustes/turnos").json()) == 3
    nuevos = [{"nombre": "Día", "inicio": "07:00", "fin": "19:00"}, {"nombre": "Noche", "inicio": "19:00", "fin": "07:00"}]
    assert c.put("/api/ajustes/turnos", json=nuevos).json() == nuevos
    t = sv.turno_actual(nuevos, datetime(2026, 11, 21, 2, 30))
    assert t["nombre"] == "Noche" and t["desde"] == datetime(2026, 11, 20, 19, 0)


# ---------------------------------------------------------------------------
# Datos: análisis, preparación e importación de archivos
# ---------------------------------------------------------------------------

def _archivo(nombre):
    return {"archivo": (nombre, (CARPETA / nombre).read_bytes())}


def test_datos_analizar_preparar(c):
    r = c.post("/api/datos/analizar", files=_archivo("proceso_simulado.csv")).json()
    assert r["filas"] == 125 and r["mapeo_sugerido"]["peso_neto_g"] == "valor"
    assert len(r["vista_previa"]) == 20
    r = c.post("/api/datos/preparar", files=_archivo("proceso_con_faltantes.csv"),
               data={"faltantes": "imputar_media_subgrupo", "atipicos": "iqr", "excluir_atipicos": "true"}).json()
    assert r["informe"]["faltantes"]["imputados"] == 3
    assert r["subgrupos_total"] == 25 and r["histograma"]["cuentas"]
    csv_dep = c.post("/api/datos/exportar", files=_archivo("proceso_simulado.csv"))
    assert csv_dep.status_code == 200 and csv_dep.text.startswith("subgrupo,muestra,valor")


def test_datos_importar_variables_y_atributos(c):
    p = c.post("/api/procesos", json={"nombre": "Importación"}).json()
    v = c.post(f"/api/procesos/{p['id']}/variables", json={"nombre": "Peso", "tipo_carta": "xbar_r", "n": 5}).json()
    r = c.post("/api/datos/importar", files=_archivo("proceso_simulado_ancho.csv"),
               data={"variable_id": v["id"], "atipicos": "ninguno"}).json()
    assert r["importados"] == 25
    assert len(c.get(f"/api/variables/{v['id']}/subgrupos").json()) == 25

    va = c.post(f"/api/procesos/{p['id']}/variables", json={"nombre": "Latas", "tipo_carta": "p", "n": 50}).json()
    r = c.post("/api/datos/importar", files=_archivo("montgomery_jugo_p.csv"), data={
        "variable_id": va["id"], "mapeo": '{"muestra": "subgrupo", "defectuosos": "conteo", "tamano": "tamano"}'}).json()
    assert r["importados"] == 30
    assert c.get(f"/api/variables/{va['id']}/carta").json()["cartas"]["p"]["lcs"] == pytest.approx(0.4102, abs=5e-5)


def test_datos_mapeo_invalido(c):
    r = c.post("/api/datos/preparar", files=_archivo("proceso_simulado.csv"), data={"mapeo": '{"no_existe": "valor"}'})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Supuestos, capacidad, diseño, muestreo y atributos
# ---------------------------------------------------------------------------

def test_supuestos_y_capacidad_anillos(c):
    s = c.get("/api/variables/3/supuestos").json()
    assert s["N"] == 125 and s["normalidad"]["es_normal"]
    cap = c.get("/api/variables/3/capacidad").json()
    assert cap["indices"]["cp"] == pytest.approx(1.68, abs=0.015)
    assert cap["en_control"] is True and cap["histograma"]["cuentas"]
    assert c.get("/api/variables/5/capacidad").status_code == 400  # atributos
    assert c.get("/api/variables/4/capacidad").status_code == 422  # sin especificaciones


def test_diseno(c):
    r = c.get("/api/diseno/arl?k=3&n=4&h=1&delta=1.5").json()
    assert r["arl1"] == pytest.approx(2.0) and r["conclusiones"]
    curva = c.get("/api/diseno/curva?k=3&n=5&comparar=3,10").json()
    assert set(curva["series"]) == {"5", "3", "10"}
    sim = c.post("/api/diseno/simular", json={"k": 3, "n": 4, "delta": 1.5, "replicas": 2000, "semilla": 3}).json()
    assert abs(sim["error_relativo"]) < 0.08


def test_muestreo(c):
    r = c.get("/api/muestreo/curvas?n=89&c=2&N=10000&aql=0.01&ltpd=0.06").json()
    assert r["en_aql"]["pa"] == pytest.approx(0.94, abs=0.01)
    assert c.post("/api/muestreo/disenar", json={"aql": 0.01, "ltpd": 0.06}).json()["n"] == 110
    assert c.get("/api/muestreo/decidir?d=2&n=200&c=3").json()["dictamen"] == "ACEPTADO"
    lote = c.post("/api/muestreo/lotes", json={"codigo": "MP-1", "N": 10000, "n": 200, "c": 3, "defectos": 5}).json()
    assert lote["dictamen"] == "RECHAZADO"
    assert c.get("/api/muestreo/lotes").json()["tasa_aceptacion"] == 0
    assert c.get("/api/muestreo/curvas?n=10&c=12").status_code == 422


def test_atributos_asistente_y_adhoc(c):
    assert c.get("/api/atributos/recomendar?tipo_dato=defectos&tamano_constante=false").json()["carta"] == "u"
    r = c.post("/api/atributos/calcular", json={"tipo": "c", "conteos": [21, 24, 16, 12, 15, 5, 28, 20]}).json()
    assert r["tipo"] == "c" and "c" in r["cartas"]


def test_cartas_de_todos_los_ejemplos(c):
    for vid, clave in [(3, "xbar"), (4, "i"), (5, "c"), (6, "u")]:
        r = c.get(f"/api/variables/{vid}/carta")
        assert r.status_code == 200 and clave in r.json()["cartas"]
    u = c.get("/api/variables/6/carta").json()["cartas"]["u"]
    assert u["lcs"] == pytest.approx(3.79, abs=5e-3)
