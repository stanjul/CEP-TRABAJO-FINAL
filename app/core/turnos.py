"""Turnos de trabajo: ventanas programadas y vencimiento de la próxima muestra.

Un turno programado es {nombre, inicio "HH:MM", fin "HH:MM", dias [0..6], arranque_min}, con los
días como en `datetime.weekday()` (0 = lunes). Si fin ≤ inicio, el turno cruza la medianoche y
pertenece al día en que empieza. La ventana de un turno es el intervalo [desde, hasta).

Dentro de un turno abierto, la próxima muestra vence:
    · si ya hay muestras en el turno:  última muestra + h
    · si todavía no hay:               inicio del turno + arranque   (arranque = h si no se fijó)
Si ese vencimiento cae en o después del fin del turno, no quedan muestras en el turno.
Fuera de turno no hay cuenta regresiva.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable

TODOS_LOS_DIAS = [0, 1, 2, 3, 4, 5, 6]
NOMBRES_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _hora(texto: str) -> time:
    h, m = map(int, texto.split(":"))
    return time(h, m)


def normalizar(turnos: Iterable[dict]) -> list[dict]:
    """Completa los campos opcionales de cada turno programado: días (todos) y arranque (sin fijar)."""
    salida = []
    for t in turnos:
        dias = sorted({int(d) for d in (t.get("dias") or TODOS_LOS_DIAS) if 0 <= int(d) <= 6})
        arr = t.get("arranque_min")
        salida.append({"nombre": str(t["nombre"]).strip(), "inicio": t["inicio"], "fin": t["fin"],
                       "dias": dias or TODOS_LOS_DIAS, "arranque_min": int(arr) if arr not in (None, "") else None})
    return salida


def validar(turnos: list[dict]) -> list[str]:
    """Errores de configuración en palabras (lista vacía si todo está bien)."""
    errores, vistos = [], set()
    if not turnos:
        errores.append("Define al menos un turno.")
    for t in turnos:
        nombre = t["nombre"]
        if not nombre:
            errores.append("Cada turno necesita un nombre.")
        elif nombre.lower() in vistos:
            errores.append(f"El nombre «{nombre}» está repetido.")
        vistos.add(nombre.lower())
        if t["inicio"] == t["fin"]:
            errores.append(f"El turno «{nombre}» empieza y termina a la misma hora.")
        if t["arranque_min"] is not None and not 0 <= t["arranque_min"] <= 600:
            errores.append(f"El arranque del turno «{nombre}» debe estar entre 0 y 600 minutos.")
    if not errores:
        errores += _superposiciones(turnos)
    return errores


def _tramos_semana(turno: dict) -> list[tuple[int, int, int]]:
    """Tramos [desde, hasta) del turno en minutos de la semana (0 = lunes 00:00), con el día de inicio.

    desde = día·1440 + inicio;  hasta = desde + duración.  Lo que pasa del domingo vuelve al lunes.
    """
    semana = 7 * 1440
    ini = _hora(turno["inicio"]); ini_min = ini.hour * 60 + ini.minute
    tramos = []
    for d in turno["dias"]:
        desde = d * 1440 + ini_min
        hasta = desde + int(duracion_min(turno))
        if hasta <= semana:
            tramos.append((desde, hasta, d))
        else:
            tramos += [(desde, semana, d), (0, hasta - semana, d)]
    return tramos


def _superposiciones(turnos: list[dict]) -> list[str]:
    """Pares de turnos cuyas horas se pisan algún día (dos tramos [a, b) y [c, d) se pisan si a < d y c < b)."""
    errores = []
    for i, t1 in enumerate(turnos):
        for t2 in turnos[i + 1:]:
            choque = next((d1 for a, b, d1 in _tramos_semana(t1) for c, d, _ in _tramos_semana(t2)
                           if a < d and c < b), None)
            if choque is not None:
                errores.append(f"Los turnos «{t1['nombre']}» y «{t2['nombre']}» se superponen "
                               f"(por ejemplo el {NOMBRES_DIAS[choque]}). Ajusta sus horas o sus días.")
    return errores


def ventana(turno: dict, dia: date) -> tuple[datetime, datetime]:
    """Intervalo [desde, hasta) del turno que empieza el día `dia`."""
    ini, fin = _hora(turno["inicio"]), _hora(turno["fin"])
    desde = datetime.combine(dia, ini)
    hasta = datetime.combine(dia + timedelta(days=1) if fin <= ini else dia, fin)
    return desde, hasta


def duracion_min(turno: dict) -> float:
    desde, hasta = ventana(turno, date(2026, 1, 5))
    return (hasta - desde).total_seconds() / 60


def ventana_en(turnos: list[dict], momento: datetime) -> dict | None:
    """Turno programado cuya ventana contiene `momento` (respetando los días de trabajo), o None."""
    for t in turnos:
        for dia in (momento.date(), momento.date() - timedelta(days=1)):
            if dia.weekday() not in t["dias"]:
                continue
            desde, hasta = ventana(t, dia)
            if desde <= momento < hasta:
                return {**t, "desde": desde, "hasta": hasta}
    return None


def proxima_ventana(turnos: list[dict], momento: datetime) -> dict | None:
    """Primer turno programado que empieza después de `momento` (busca hasta 8 días adelante)."""
    candidatas = []
    for t in turnos:
        for k in range(0, 9):
            dia = momento.date() + timedelta(days=k)
            if dia.weekday() not in t["dias"]:
                continue
            desde, hasta = ventana(t, dia)
            if desde > momento:
                candidatas.append({**t, "desde": desde, "hasta": hasta})
                break
    return min(candidatas, key=lambda x: x["desde"]) if candidatas else None


def proxima_muestra(inicio: datetime, fin: datetime, ultima: datetime | None, frecuencia_min: float,
                    arranque_min: float | None, momento: datetime) -> dict:
    """Vencimiento de la próxima muestra dentro de un turno abierto [inicio, fin).

    Devuelve {estado, vence, segundos}: estado "en_turno" (vence dentro del turno) o
    "sin_mas_muestras" (el vencimiento quedaría en o después del fin del turno).
    """
    if ultima is not None and ultima >= inicio:
        vence = ultima + timedelta(minutes=frecuencia_min)
    else:
        vence = inicio + timedelta(minutes=frecuencia_min if arranque_min is None else arranque_min)
    if vence >= fin:
        return {"estado": "sin_mas_muestras", "vence": None, "segundos": None}
    return {"estado": "en_turno", "vence": vence, "segundos": int((vence - momento).total_seconds())}


def muestras_programadas(inicio: datetime, fin: datetime, frecuencia_min: float, arranque_min: float | None) -> int:
    """Muestras que caben en el turno: la primera a inicio + arranque (o + h) y luego cada h, antes del fin."""
    primera = inicio + timedelta(minutes=frecuencia_min if arranque_min is None else arranque_min)
    if primera >= fin:
        return 0
    minutos = (fin - primera).total_seconds() / 60
    return int((minutos - 1e-9) // frecuencia_min) + 1


def texto_dias(dias: list[int]) -> str:
    """'todos los días', 'lunes a viernes' o la lista de días."""
    dias = sorted(set(dias))
    if dias == TODOS_LOS_DIAS:
        return "todos los días"
    if dias == [0, 1, 2, 3, 4]:
        return "lunes a viernes"
    if dias == [0, 1, 2, 3, 4, 5]:
        return "lunes a sábado"
    nombres = [NOMBRES_DIAS[d] for d in dias]
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]
