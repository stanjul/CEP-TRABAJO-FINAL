"""Turnos de trabajo: ventanas programadas, vencimiento de la próxima muestra y turnos reales.

Fechas de referencia: 2026-11-23 es lunes; 2026-11-28 es sábado.
"""
from datetime import datetime

import pytest

from app.api import servicios as sv
from app.core import turnos as t
from app.db import sesion
from app.db.modelos import Proceso

LV = [0, 1, 2, 3, 4]
PROG = t.normalizar([
    {"nombre": "Mañana", "inicio": "06:00", "fin": "14:00", "dias": LV},
    {"nombre": "Tarde", "inicio": "14:00", "fin": "22:00", "dias": LV},
    {"nombre": "Noche", "inicio": "22:00", "fin": "06:00", "dias": [0, 1, 2, 3]},
])


# ---------------------------------------------------------------------------
# Núcleo (funciones puras)
# ---------------------------------------------------------------------------

def test_normalizar_completa_dias_y_arranque():
    n = t.normalizar([{"nombre": " Día ", "inicio": "07:00", "fin": "19:00"}])[0]
    assert n == {"nombre": "Día", "inicio": "07:00", "fin": "19:00", "dias": t.TODOS_LOS_DIAS, "arranque_min": None}


def test_validar():
    assert t.validar(PROG) == []
    errores = t.validar(t.normalizar([{"nombre": "A", "inicio": "06:00", "fin": "06:00"},
                                      {"nombre": "a", "inicio": "07:00", "fin": "08:00", "arranque_min": 900}]))
    assert len(errores) == 3



def test_validar_superposiciones():
    """Dos turnos se pisan si sus tramos semanales [a, b) y [c, d) cumplen a < d y c < b."""
    def turnos(*filas):
        return t.normalizar([{"nombre": n, "inicio": i, "fin": f, "dias": d} for n, i, f, d in filas])
    # Contiguos (14:00 termina uno y empieza el otro): no se pisan.
    assert t.validar(turnos(("M", "06:00", "14:00", [0]), ("T", "14:00", "22:00", [0]))) == []
    # Se pisan una hora el lunes.
    e = t.validar(turnos(("M", "06:00", "15:00", [0]), ("T", "14:00", "22:00", [0])))
    assert len(e) == 1 and "lunes" in e[0]
    # Mismas horas pero días distintos: no se pisan.
    assert t.validar(turnos(("A", "06:00", "14:00", [0, 1]), ("B", "06:00", "14:00", [2]))) == []
    # Noche del domingo (22–06) cruza al lunes y pisa un turno del lunes a las 05:00.
    e = t.validar(turnos(("N", "22:00", "06:00", [6]), ("M", "05:00", "13:00", [0])))
    assert len(e) == 1 and "domingo" in e[0]
    # Noche del viernes termina el sábado 06:00: no pisa un turno del sábado que empieza a las 06:00.
    assert t.validar(turnos(("N", "22:00", "06:00", [4]), ("S", "06:00", "14:00", [5]))) == []

def test_ventana_cruza_medianoche_y_respeta_dias():
    v = t.ventana_en(PROG, datetime(2026, 11, 24, 2, 30))        # martes 02:30 → noche que empezó el lunes
    assert v["nombre"] == "Noche" and v["desde"] == datetime(2026, 11, 23, 22, 0)
    assert v["hasta"] == datetime(2026, 11, 24, 6, 0)
    assert t.ventana_en(PROG, datetime(2026, 11, 28, 10, 0)) is None   # sábado: no se trabaja
    assert t.ventana_en(PROG, datetime(2026, 11, 27, 23, 0)) is None   # viernes 23:00: la noche es de lunes a jueves
    assert t.ventana_en(PROG, datetime(2026, 11, 23, 14, 0))["nombre"] == "Tarde"   # [desde, hasta)


def test_proxima_ventana():
    p = t.proxima_ventana(PROG, datetime(2026, 11, 28, 10, 0))      # sábado → lunes 06:00
    assert p["nombre"] == "Mañana" and p["desde"] == datetime(2026, 11, 30, 6, 0)
    assert t.proxima_ventana(PROG, datetime(2026, 11, 23, 15, 0))["desde"] == datetime(2026, 11, 23, 22, 0)


def test_proxima_muestra():
    ini, fin = datetime(2026, 11, 23, 6, 0), datetime(2026, 11, 23, 14, 0)
    # Sin muestras y sin arranque: un intervalo después del inicio.
    r = t.proxima_muestra(ini, fin, None, 30, None, datetime(2026, 11, 23, 6, 10))
    assert r["estado"] == "en_turno" and r["vence"] == datetime(2026, 11, 23, 6, 30) and r["segundos"] == 20 * 60
    # Con arranque de 45 min.
    assert t.proxima_muestra(ini, fin, None, 30, 45, ini)["vence"] == datetime(2026, 11, 23, 6, 45)
    # Después de una muestra: última + h; atrasada da segundos negativos.
    r = t.proxima_muestra(ini, fin, datetime(2026, 11, 23, 8, 0), 30, None, datetime(2026, 11, 23, 8, 40))
    assert r["vence"] == datetime(2026, 11, 23, 8, 30) and r["segundos"] == -600
    # Si la próxima caería en el fin o después, no quedan muestras en el turno.
    assert t.proxima_muestra(ini, fin, datetime(2026, 11, 23, 13, 30), 30, None, ini)["estado"] == "sin_mas_muestras"


def test_muestras_programadas():
    ini, fin = datetime(2026, 11, 23, 6, 0), datetime(2026, 11, 23, 14, 0)
    assert t.muestras_programadas(ini, fin, 30, None) == 15        # 06:30 … 13:30
    assert t.muestras_programadas(ini, fin, 30, 0) == 16           # 06:00 … 13:30
    assert t.muestras_programadas(ini, fin, 600, None) == 0


def test_texto_dias():
    assert t.texto_dias(t.TODOS_LOS_DIAS) == "todos los días"
    assert t.texto_dias(LV) == "lunes a viernes"
    assert t.texto_dias([5, 6]) == "sábado y domingo"


# ---------------------------------------------------------------------------
# Turnos reales (servicios, con fechas controladas)
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    sesion.configurar(f"sqlite:///{(tmp_path / 'turnos.db').as_posix()}")
    sesion.crear_tablas()
    with sesion.SesionLocal() as s:
        sv.guardar_turnos(s, PROG)
        p = Proceso(nombre="Llenado")
        s.add(p)
        s.flush()
        v = sv.crear_variable(s, p.id, {"nombre": "Peso", "unidad": "g", "tipo_carta": "xbar_r", "n": 5,
                                        "frecuencia_min": 30, "lei": 495, "objetivo": 500, "les": 505}, "Prueba")
        s.commit()
        s.info["v"] = v
        yield s


def test_guardar_turnos_valida(db):
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        sv.guardar_turnos(db, [{"nombre": "A", "inicio": "06:00", "fin": "06:00"}])


def test_ciclo_de_turnos(db):
    lunes = lambda h, m=0: datetime(2026, 11, 23, h, m)
    # Al despertar en la mañana se abre el turno 1 desde la hora programada.
    t1 = sv.sincronizar_turnos(db, lunes(7))
    assert (t1.numero, t1.nombre, t1.inicio, t1.abierto_por) == (1, "Mañana", lunes(6), "Automático")
    # Pasada la hora de fin se cierra a esa hora y se abre el de la tarde.
    t2 = sv.sincronizar_turnos(db, lunes(14, 30))
    db.refresh(t1)
    assert (t1.fin, t1.cierre) == (lunes(14), "hora") and (t2.numero, t2.nombre) == (2, "Tarde")
    # Fin a mano: no se vuelve a abrir en la misma ventana.
    cerrado = sv.terminar_turno(db, "Ingeniera", lunes(15))
    assert cerrado["cierre"] == "manual" and cerrado["cerrado_por"] == "Ingeniera"
    assert sv.sincronizar_turnos(db, lunes(15, 30)) is None
    est = sv.estado_turno(db, lunes(15, 30))
    assert est["abierto"] is None and est["proximo"]["nombre"] == "Noche"
    # Iniciar a mano en un día sin programación: dura lo mismo que el turno elegido.
    sabado = datetime(2026, 11, 28, 10, 0)
    assert sv.sincronizar_turnos(db, sabado) is None
    # Dentro del horario del turno elegido: termina a su hora de fin habitual.
    t3 = sv.iniciar_turno(db, "Mañana", "Ingeniera", sabado)
    assert t3["numero"] == 3 and t3["fin_programado"] == datetime(2026, 11, 28, 14, 0)
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        sv.iniciar_turno(db, "Tarde", "Ingeniera", sabado)        # ya hay uno abierto
    # Fuera de su horario: dura lo mismo que el turno programado (8 h) desde ahora.
    sv.terminar_turno(db, "Ingeniera", datetime(2026, 11, 28, 10, 30))
    t4 = sv.iniciar_turno(db, "Tarde", "Ingeniera", datetime(2026, 11, 28, 11, 0))
    assert t4["fin_programado"] == datetime(2026, 11, 28, 19, 0)
    hist = sv.historial_turnos(db, momento=datetime(2026, 11, 28, 11, 5))
    assert [h["numero"] for h in hist] == [4, 3, 2, 1]


def test_cuenta_regresiva_respeta_el_turno(db):
    v = db.info["v"]
    lunes = lambda h, m=0: datetime(2026, 11, 23, h, m)
    r = sv.resumen_operario(db, v, lunes(6, 10))
    assert r["estado_muestreo"] == "en_turno" and r["proxima_muestra"] == lunes(6, 30)
    assert r["turno"]["nombre"] == "Mañana" and r["turno"]["subgrupos_programados"] == 15
    # Una muestra cargada con su hora queda en el turno real que la contiene.
    sg, _ = sv.registrar_subgrupo(db, v, valores=[500, 501, 499, 500, 500], timestamp=lunes(6, 32), origen="plantilla")
    assert sg.turno_id == r["turno"]["id"]
    r = sv.resumen_operario(db, v, lunes(6, 40))
    assert r["proxima_muestra"] == lunes(7, 2) and r["turno"]["subgrupos_tomados"] == 1
    sv.registrar_subgrupo(db, v, valores=[500] * 5, timestamp=lunes(13, 40), origen="plantilla")
    assert sv.resumen_operario(db, v, lunes(13, 45))["estado_muestreo"] == "sin_mas_muestras"
    # Fuera de turno no hay cuenta regresiva ni «atrasada».
    sv.terminar_turno(db, "Ingeniera", lunes(13, 50))
    r = sv.resumen_operario(db, v, datetime(2026, 11, 28, 9, 0))   # sábado
    assert r["estado_muestreo"] == "fuera_de_turno" and r["segundos_para_muestra"] is None
    assert r["muestra_atrasada"] is False and r["proximo_turno"]["desde"] == datetime(2026, 11, 30, 6, 0)
    assert r["turno"]["numero"] == 1 and r["turno"]["abierto"] is False      # resumen del último turno
    # Una muestra con fecha fuera de todo turno queda sin turno.
    sg, _ = sv.registrar_subgrupo(db, v, valores=[500] * 5, timestamp=datetime(2026, 11, 28, 9, 5), origen="plantilla")
    assert sg.turno_id is None
