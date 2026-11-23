"""Conclusiones generadas por reglas."""
from app.core import capacidad, diseno_arl, graficos_variables as gv, muestreo_aceptacion as ma
from app.core.reportes import generar_conclusiones
from tests.datos_montgomery import ANILLOS


def test_conclusiones_proceso_en_control_y_capaz():
    carta = gv.calcular_xbar_r(ANILLOS, reglas=["N1"])
    cap = capacidad.analizar_capacidad(ANILLOS, 73.95, 74.05)
    c = generar_conclusiones(carta=carta, capacidad=cap)
    assert c[0]["seccion"] == "sintesis"
    textos = " ".join(x["texto"] for x in c)
    assert "bajo control" in textos
    assert "capaz" in textos.lower()
    assert not any(x["nivel"] == "critico" for x in c)


def test_conclusiones_fuera_de_control():
    datos = [list(g) for g in ANILLOS]
    datos[3] = [v + 0.05 for v in datos[3]]
    carta = gv.calcular_xbar_r(datos, reglas=["N1"])
    c = generar_conclusiones(carta=carta)
    assert c[0]["nivel"] == "critico"
    assert any("subgrupo(s) 4" in x["texto"] for x in c)


def test_conclusiones_usan_etiquetas_reales():
    base = gv.calcular_xbar_r(ANILLOS[:20], reglas=["N1"])
    nuevos = [[v + 0.05 for v in ANILLOS[20]]]
    f2 = gv.calcular_xbar_r(nuevos, limites=base["limites"], reglas=["N1"])
    f2["etiquetas"] = [21]
    c = generar_conclusiones(carta=f2)
    assert any("subgrupo(s) 21" in x["texto"] for x in c)


def test_conclusiones_diseno_y_muestreo():
    c = generar_conclusiones(diseno=diseno_arl.diseno(3, 4, 1, 1.5),
                             muestreo=ma.curvas(89, 2, 10_000, aql=0.01, ltpd=0.06))
    secciones = {x["seccion"] for x in c}
    assert {"diseno", "muestreo", "sintesis"} <= secciones
