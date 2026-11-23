"""Datos iniciales de demostración (solo si la base está vacía).

- Proceso "Línea de Envasado L-04":
    · Peso neto (g), carta X̄-R, n = 5, cada 15 min, especificación 495–505 g. Se cargan los
      subgrupos 1–19 de `datos_prueba/proceso_simulado.csv` como Fase I y se congelan los
      límites: la variable queda en Fase II lista para que el operario registre los
      subgrupos 20–25 (con el corrimiento de +1.5σ) y vea las alarmas.
    · Envases defectuosos, carta p (n = 50): datos de las latas de jugo de Montgomery en
      Fase I, sin depurar (para practicar la exclusión de las muestras 15 y 23).
- Proceso "Ejemplos Montgomery": anillos de pistón (X̄-R), préstamos (I-MR), circuitos (c)
  y computadoras (u), en Fase I.

Los timestamps se generan hacia atrás desde ahora para que la vista de operario muestre un
turno y una cuenta regresiva coherentes.
"""

from __future__ import annotations

import csv
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.reglas import PRESETS

from .modelos import Ajuste, CambioConfiguracion, Medicion, Proceso, Subgrupo, Variable, ahora

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "datos_prueba"


def _leer_simulado() -> list[list[float]]:
    grupos: dict[int, list[float]] = {}
    with open(DATOS / "proceso_simulado.csv", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            grupos.setdefault(int(fila["subgrupo"]), []).append(float(fila["peso_neto_g"]))
    return [grupos[k] for k in sorted(grupos)]


def _cargar(db: Session, v: Variable, datos, frecuencia_min: int, es_atributo=False, tamanos=None, operario=None,
            lote=None) -> None:
    fin = ahora() - timedelta(minutes=5)
    total = len(datos)
    for i, d in enumerate(datos):
        sg = Subgrupo(variable_id=v.id, numero=i + 1, fase="I", origen="semilla", operario=operario, lote=lote,
                      timestamp=fin - timedelta(minutes=frecuencia_min * (total - 1 - i)))
        if es_atributo:
            sg.conteo = float(d)
            sg.tamano = None if tamanos is None else float(tamanos)
        else:
            sg.mediciones = [Medicion(posicion=j + 1, valor=float(x)) for j, x in enumerate(d)]
        db.add(sg)


def _alta(db: Session, v: Variable) -> None:
    db.add(CambioConfiguracion(variable_id=v.id, usuario="Sistema", parametro="alta", valor_anterior=None,
                               valor_nuevo="Datos de demostración", justificacion="Carga inicial", version=1,
                               hash="-"))


def sembrar(db: Session) -> bool:
    """Carga los datos de demostración si no hay procesos. Devuelve True si sembró."""
    if db.scalar(select(Proceso.id).limit(1)) is not None:
        return False
    from app import ejemplos_montgomery as dm  # datasets del libro (también usados en los tests)
    from app.api import servicios as sv

    # Con datos de demostración se habilita el botón "Completar con valores simulados" del Operario.
    db.add(Ajuste(clave="modo_demo", valor={"activo": True}))

    envasado = Proceso(nombre="Línea de Envasado L-04", planta="Planta Norte", linea="L-04",
                       descripcion="Envasado automático de alta velocidad (proceso simulado del curso).")
    db.add(envasado)
    db.flush()

    peso = Variable(proceso_id=envasado.id, nombre="Peso neto", unidad="g", tipo_dato="variables", tipo_carta="xbar_r",
                    n=5, frecuencia_min=15, lei=495.0, objetivo=500.0, les=505.0, estimador_sigma="rbar",
                    reglas=PRESETS["nelson"], decimales=2)
    db.add(peso)
    db.flush()
    _alta(db, peso)
    _cargar(db, peso, _leer_simulado()[:19], 15, operario="OP-104", lote="ENV-2026-001")
    db.flush()
    sv.congelar_limites(db, peso, "Sistema", "Base estable: subgrupos 1–19 del proceso simulado")

    defect = Variable(proceso_id=envasado.id, nombre="Envases defectuosos", unidad="envases", tipo_dato="atributos",
                      tipo_carta="p", n=50, frecuencia_min=60, reglas=["N1"], decimales=0)
    db.add(defect)
    db.flush()
    _alta(db, defect)
    _cargar(db, defect, dm.JUGO_DEFECTUOSOS, 60, es_atributo=True, tamanos=dm.JUGO_N)

    libro = Proceso(nombre="Ejemplos Montgomery", planta="Libro de texto", linea="Cap. 6 y 7",
                    descripcion="Ejemplos resueltos de Introduction to Statistical Quality Control.")
    db.add(libro)
    db.flush()
    ejemplos = [
        (Variable(proceso_id=libro.id, nombre="Diámetro interior de anillos de pistón", unidad="mm", tipo_carta="xbar_r",
                  n=5, frecuencia_min=60, lei=73.95, objetivo=74.0, les=74.05, decimales=3), dm.ANILLOS, False, None),
        (Variable(proceso_id=libro.id, nombre="Costo de préstamos hipotecarios", unidad="USD", tipo_carta="imr", n=1,
                  frecuencia_min=60 * 24 * 7, estimador_sigma="mr", decimales=0), [[x] for x in dm.PRESTAMOS], False, None),
        (Variable(proceso_id=libro.id, nombre="No conformidades en circuitos impresos", unidad="defectos",
                  tipo_dato="atributos", tipo_carta="c", n=1, frecuencia_min=60, reglas=["N1"], decimales=0),
         dm.CIRCUITOS, True, None),
        (Variable(proceso_id=libro.id, nombre="Defectos en computadoras personales", unidad="defectos/unidad",
                  tipo_dato="atributos", tipo_carta="u", n=5, frecuencia_min=60, reglas=["N1"], decimales=2),
         dm.COMPUTADORAS, True, dm.COMPUTADORAS_N),
    ]
    for v, datos, es_attr, tam in ejemplos:
        v.reglas = v.reglas or PRESETS["nelson"]
        db.add(v)
        db.flush()
        _alta(db, v)
        _cargar(db, v, datos, v.frecuencia_min, es_atributo=es_attr, tamanos=tam)
    db.commit()
    return True
