"""Servicios: combinan la base de datos con la lógica estadística de `app.core`.

Los routers solo validan la petición y llaman a estas funciones. Aquí no hay fórmulas: todo
cálculo se delega al core.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, time, timedelta
from typing import Iterable

import numpy as np
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import capacidad as core_cap
from app.core import graficos_atributos as ga
from app.core import graficos_variables as gv
from app.core import supuestos as core_sup
from app.core.reglas import CATALOGO, PRESETS, REGLAS_DISPERSION, explicar
from app.db.modelos import (Ajuste, Alarma, CambioConfiguracion, LimitesCarta, Medicion, Proceso, Subgrupo,
                            TurnoRegistro, Variable, ahora)

from .util import usuario_o_anonimo

TIPOS_VARIABLES = ("xbar_r", "xbar_s", "imr")
TIPOS_ATRIBUTOS = ("p", "np", "c", "u")
CAMPOS_CONFIG = ("nombre", "unidad", "tipo_carta", "n", "frecuencia_min", "lei", "objetivo", "les", "k_sigma",
                 "estimador_sigma", "sigma_monitoreo", "reglas", "decimales")
# Campos que cambian la forma de calcular los límites: con PATCH solo se modifican en Fase I.
# En Fase II, n, k y σ se cambian con `aplicar_plan`, que recalcula los límites congelados.
CAMPOS_ESTRUCTURALES = ("tipo_carta", "n", "k_sigma", "estimador_sigma", "sigma_monitoreo")
TURNOS_POR_DEFECTO = [
    {"nombre": "Turno 1", "inicio": "06:00", "fin": "14:00"},
    {"nombre": "Turno 2", "inicio": "14:00", "fin": "22:00"},
    {"nombre": "Turno 3", "inicio": "22:00", "fin": "06:00"},
]


# ---------------------------------------------------------------------------
# Lectura básica
# ---------------------------------------------------------------------------

def obtener_proceso(db: Session, proceso_id: int) -> Proceso:
    p = db.get(Proceso, proceso_id)
    if p is None:
        raise HTTPException(404, f"Proceso {proceso_id} no encontrado.")
    return p


def crear_variable(db: Session, proceso_id: int, d: dict, usuario: str | None,
                   justificacion: str = "Creación de la variable") -> Variable:
    """Crea una variable validando sus datos (sin commit). `d` tiene los campos de VariableCrear."""
    d = dict(d)
    d["nombre"] = (d.get("nombre") or "").strip()
    if not d["nombre"]:
        raise HTTPException(422, "Escriba un nombre para la variable.")
    if d.get("lei") is not None and d.get("les") is not None and d["lei"] >= d["les"]:
        raise HTTPException(422, "El límite inferior de especificación debe ser menor que el superior.")
    if d["tipo_carta"] in TIPOS_ATRIBUTOS:
        d["sigma_monitoreo"] = None
        d["lei"] = d["les"] = d["objetivo"] = None
    elif d["tipo_carta"] in ("xbar_r", "xbar_s") and d["n"] < 2:
        raise HTTPException(422, "Las cartas X̄ necesitan al menos 2 unidades por muestra.")
    d["reglas"] = d.get("reglas") or PRESETS["nelson"]
    if d.get("estimador_sigma") is None:
        d["estimador_sigma"] = {"xbar_s": "sbar", "imr": "mr"}.get(d["tipo_carta"], "rbar")
    if d["tipo_carta"] == "imr":
        d["n"] = 1
    v = Variable(proceso_id=proceso_id, tipo_dato="atributos" if d["tipo_carta"] in TIPOS_ATRIBUTOS else "variables",
                 **{k: x for k, x in d.items() if k in CAMPOS_CONFIG})
    db.add(v)
    db.flush()
    registrar_cambio(db, v, "alta", None, variable_a_dict(v), usuario, justificacion)
    return v


def obtener_variable(db: Session, variable_id: int) -> Variable:
    v = db.get(Variable, variable_id)
    if v is None:
        raise HTTPException(404, f"Variable {variable_id} no encontrada.")
    return v


def es_atributos(v: Variable) -> bool:
    return v.tipo_carta in TIPOS_ATRIBUTOS


def variable_a_dict(v: Variable) -> dict:
    """Configuración de la variable (también es lo que se resume en el hash de auditoría)."""
    return {
        "id": v.id, "proceso_id": v.proceso_id, "nombre": v.nombre, "unidad": v.unidad, "tipo_dato": v.tipo_dato,
        "tipo_carta": v.tipo_carta, "n": v.n, "frecuencia_min": v.frecuencia_min, "lei": v.lei,
        "objetivo": v.objetivo, "les": v.les, "k_sigma": v.k_sigma, "estimador_sigma": v.estimador_sigma,
        "sigma_monitoreo": v.sigma_monitoreo,
        "reglas": list(v.reglas or []), "fase": v.fase, "decimales": v.decimales, "version": v.version,
    }


def proceso_a_dict(p: Proceso, con_variables: bool = True) -> dict:
    d = {"id": p.id, "nombre": p.nombre, "planta": p.planta, "linea": p.linea, "descripcion": p.descripcion}
    if con_variables:
        d["variables"] = [{**variable_a_dict(v), "muestras": len(v.subgrupos)} for v in p.variables]
    return d


def hash_config(v: Variable) -> str:
    """SHA-256 de la configuración vigente (permite verificar que el historial no se alteró)."""
    datos = {k: val for k, val in variable_a_dict(v).items() if k not in ("id", "proceso_id")}
    if datos.get("sigma_monitoreo") is None:  # campo nuevo: sin σ fijada el hash no cambia respecto de versiones previas
        datos.pop("sigma_monitoreo", None)
    return hashlib.sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def subgrupos_de(db: Session, v: Variable, fases: Iterable[str] = ("I",), ultimos: int | None = None) -> list[Subgrupo]:
    """Subgrupos de la variable en las fases indicadas, en orden cronológico (número)."""
    q = select(Subgrupo).where(Subgrupo.variable_id == v.id, Subgrupo.fase.in_(list(fases))).order_by(Subgrupo.numero)
    lista = list(db.scalars(q))
    return lista[-ultimos:] if ultimos else lista


def limites_activos(db: Session, v: Variable) -> LimitesCarta | None:
    return db.scalars(select(LimitesCarta).where(LimitesCarta.variable_id == v.id, LimitesCarta.activo)
                      .order_by(LimitesCarta.id.desc())).first()


def subgrupo_a_dict(sg: Subgrupo, v: Variable) -> dict:
    d = {
        "id": sg.id, "numero": sg.numero, "timestamp": sg.timestamp, "fase": sg.fase, "operario": sg.operario,
        "lote": sg.lote, "origen": sg.origen, "excluido": sg.excluido, "causa_exclusion": sg.causa_exclusion,
        "accion_exclusion": sg.accion_exclusion, "comentario": sg.comentario,
        "turno": {"id": sg.turno.id, "numero": sg.turno.numero, "nombre": sg.turno.nombre} if sg.turno else None,
    }
    if es_atributos(v):
        d.update({"conteo": sg.conteo, "tamano": sg.tamano})
    else:
        est = gv.estadisticos_subgrupo(sg.valores)
        d.update({"valores": sg.valores, **{k: est[k] for k in ("media", "rango", "s")}})
    return d


# ---------------------------------------------------------------------------
# Cálculo de cartas
# ---------------------------------------------------------------------------

def _reglas(v: Variable) -> list[str]:
    return [r for r in (v.reglas or PRESETS["nelson"]) if r in CATALOGO]


def _calcular_core(v: Variable, subgrupos: list[Subgrupo], limites: dict | None) -> dict:
    """Ejecuta la carta del core para la lista de subgrupos (excluidos según la BD)."""
    excluidos = [i for i, sg in enumerate(subgrupos) if sg.excluido]
    comunes = {"excluidos": excluidos, "k": v.k_sigma, "limites": limites, "reglas": _reglas(v)}
    if v.tipo_carta in TIPOS_VARIABLES:
        datos = [sg.valores for sg in subgrupos]
        res = gv.calcular_carta(v.tipo_carta, datos, **comunes)
        if limites is None and v.sigma_monitoreo:
            # Fase I con σ fijada por el ingeniero: el centro sale de los datos y σ es la indicada.
            con_sigma = gv.limites_con_sigma(v.tipo_carta, gv.centro_de_limites(res["limites"]), v.sigma_monitoreo,
                                             res["limites"]["n"], v.k_sigma)
            con_sigma["m_usados"] = res["limites"].get("m_usados")
            con_sigma["sigma_estimada_datos"] = res["sigma_hat"]
            res = gv.calcular_carta(v.tipo_carta, datos, **{**comunes, "limites": con_sigma})
            res["fase"] = "I"
            res["estimador"] = "σ fijada por el ingeniero"
        return res
    conteos = [sg.conteo or 0.0 for sg in subgrupos]
    tamanos = [sg.tamano or v.n for sg in subgrupos]
    return ga.calcular_carta_atributos(v.tipo_carta, conteos, tamanos, **comunes)


def _cartas_vacias(v: Variable, limites: dict) -> dict:
    """Cartas sin puntos (Fase II recién iniciada): solo las líneas de los límites congelados."""
    def serie(nombre, l):
        return {"nombre": nombre, "valores": [], "lc": l["lc"], "lcs": l["lcs"], "lci": l["lci"], "sigma": None,
                "violaciones": []}

    t = v.tipo_carta
    if t == "xbar_r":
        return {"xbar": serie("X̄", limites["xbar"]), "r": serie("R", limites["r"])}
    if t == "xbar_s":
        return {"xbar": serie("X̄", limites["xbar"]), "s": serie("S", limites["s"])}
    if t == "imr":
        return {"i": serie("I", limites["i"]), "mr": serie("MR", limites["mr"])}
    # Atributos: límites para el tamaño de muestra configurado.
    simulado = ga.calcular_carta_atributos(t, [0.0], [float(v.n)], limites=limites, k=v.k_sigma)
    c = simulado["cartas"][t]
    return {t: {**c, "valores": [], "violaciones": []}}


def carta_variable(db: Session, v: Variable, fase: str | None = None, ultimos: int | None = None) -> dict:
    """Carta de la variable en la fase pedida (por defecto, la fase actual).

    Fase I: límites estimados con los subgrupos de Fase I no excluidos.
    Fase II: subgrupos de Fase II contra los límites congelados activos.
    `ultimos` limita la ventana graficada (p. ej. 25 en la vista de operario); en Fase I la
    ventana se aplica después de estimar los límites con todos los subgrupos.
    """
    fase = fase or v.fase
    activo = limites_activos(db, v)
    if fase == "II":
        if activo is None:
            raise HTTPException(409, "La variable no tiene límites congelados: complete la Fase I.")
        sgs = subgrupos_de(db, v, ("II",), ultimos)
        if sgs:
            res = _calcular_core(v, sgs, activo.datos)
        else:
            res = {"tipo": v.tipo_carta, "fase": "II", "cartas": _cartas_vacias(v, activo.datos), "excluidos": [],
                   "puntos_con_senal": [], "limites": activo.datos, "sigma_hat": activo.datos.get("sigma_hat"),
                   "estimador": {"xbar_r": "R̄/d2", "xbar_s": "s̄/c4", "imr": "MR̄/d2"}.get(v.tipo_carta)}
    else:
        sgs = subgrupos_de(db, v, ("I",))
        if not sgs:
            return {"tipo": v.tipo_carta, "fase": "I", "vacio": True, "cartas": {}, "subgrupos": [],
                    "etiquetas": [], "variable": variable_a_dict(v), "mensaje": "Aún no hay subgrupos en la Fase I."}
        try:
            res = _calcular_core(v, sgs, None)
        except ValueError as e:
            raise HTTPException(422, str(e))
        if ultimos and len(sgs) > ultimos:
            res = _recortar(res, len(sgs) - ultimos)
            sgs = sgs[-ultimos:]
    res["subgrupos"] = [subgrupo_a_dict(sg, v) for sg in sgs]
    res["etiquetas"] = [sg.numero for sg in sgs]
    res["variable"] = variable_a_dict(v)
    res["especificaciones"] = {"lei": v.lei, "objetivo": v.objetivo, "les": v.les}
    res["limites_congelados"] = _limites_a_dict(activo) if activo else None
    return res


def _recortar(res: dict, desde: int) -> dict:
    """Recorta un resultado a los puntos [desde:], reindexando las violaciones."""
    for c in res["cartas"].values():
        c["valores"] = c["valores"][desde:]
        for clave in ("lcs", "lci", "sigma", "lc"):
            if isinstance(c.get(clave), list):
                c[clave] = c[clave][desde:]
        c["violaciones"] = [
            {**x, "indice": x["indice"] - desde, "puntos": [p - desde for p in x["puntos"] if p >= desde]}
            for x in c["violaciones"] if x["indice"] >= desde
        ]
    res["puntos_con_senal"] = [i - desde for i in res["puntos_con_senal"] if i >= desde]
    res["excluidos"] = [i - desde for i in res["excluidos"] if i >= desde]
    return res


def _limites_a_dict(l: LimitesCarta) -> dict:
    return {"id": l.id, "tipo_carta": l.tipo_carta, "datos": l.datos, "m_usados": l.m_usados, "excluidos": l.excluidos,
            "activo": l.activo, "usuario": l.usuario, "motivo": l.motivo, "creado": l.creado, "archivado": l.archivado}


# ---------------------------------------------------------------------------
# Registro de subgrupos y alarmas
# ---------------------------------------------------------------------------

def registrar_subgrupo(db: Session, v: Variable, valores=None, conteo=None, tamano=None, timestamp=None,
                       operario=None, lote=None, comentario=None, origen="manual", evaluar=True,
                       numero: int | None = None) -> tuple[Subgrupo, list[Alarma]]:
    """Guarda un subgrupo con su timestamp en la fase actual y evalúa las reglas activas.

    Variables: se exigen `n` valores (X̄-R / I-MR) o al menos 2 (X̄-S).
    Atributos: se exige `conteo`; `tamano` vale por defecto el n configurado.
    `numero` (plantilla de carga): número de muestra a usar; si ya existe se rechaza.
    Devuelve el subgrupo y las alarmas nuevas.
    """
    if es_atributos(v):
        if conteo is None:
            raise HTTPException(422, "Indique el conteo (defectuosos o defectos).")
        tam = float(tamano) if tamano is not None else (float(v.n) if v.tipo_carta != "c" else None)
        if v.tipo_carta in ("p", "np") and tam is not None and conteo > tam:
            raise HTTPException(422, "El número de defectuosos no puede superar el tamaño de la muestra.")
        if v.tipo_carta == "np" and tam != v.n:
            raise HTTPException(422, f"La carta np requiere n = {v.n} constante.")
    else:
        vals = [float(x) for x in (valores or [])]
        if v.tipo_carta == "imr" and len(vals) != 1:
            raise HTTPException(422, "La carta I-MR registra una medición por subgrupo.")
        if v.tipo_carta == "xbar_r" and len(vals) != v.n:
            raise HTTPException(422, f"Se esperaban {v.n} mediciones y se recibieron {len(vals)}.")
        if v.tipo_carta == "xbar_s" and len(vals) < 2:
            raise HTTPException(422, "La carta X̄-S requiere al menos 2 mediciones.")

    if numero is None:
        numero = (db.scalar(select(func.max(Subgrupo.numero)).where(Subgrupo.variable_id == v.id)) or 0) + 1
    elif db.scalar(select(Subgrupo.id).where(Subgrupo.variable_id == v.id, Subgrupo.numero == numero)):
        raise HTTPException(409, f"Ya existe la muestra #{numero}.")
    momento_sg = timestamp or ahora()
    # Turno: una muestra tomada ahora va al turno abierto (sincronizando antes); una cargada con su
    # fecha y hora (plantilla, CSV) va al turno real que contenga ese momento, si existe.
    if timestamp is None:
        turno = sincronizar_turnos(db, momento_sg) if origen == "manual" else None
    else:
        turno = turno_de_momento(db, momento_sg)
    sg = Subgrupo(variable_id=v.id, numero=numero, timestamp=momento_sg, fase=v.fase, operario=operario,
                  lote=lote, comentario=comentario, origen=origen, turno_id=turno.id if turno else None)
    if es_atributos(v):
        sg.conteo, sg.tamano = float(conteo), tam
    else:
        sg.mediciones = [Medicion(posicion=i + 1, valor=x) for i, x in enumerate(vals)]
    db.add(sg)
    db.flush()
    nuevas = evaluar_alarmas(db, v, sg) if evaluar else []
    db.commit()
    return sg, nuevas


VENTANA_DESHACER_MIN = 10  # minutos durante los que el operario puede anular su último registro


def ultimo_subgrupo(db: Session, v: Variable) -> Subgrupo | None:
    """Último subgrupo registrado que sigue vigente (no anulado)."""
    return db.scalars(select(Subgrupo).where(Subgrupo.variable_id == v.id, Subgrupo.fase != "anulado")
                      .order_by(Subgrupo.numero.desc())).first()


def segundos_para_deshacer(sg: Subgrupo | None, momento: datetime | None = None) -> int:
    """Segundos que quedan para anular `sg` (0 si ya no se puede)."""
    if sg is None or sg.origen != "manual" or sg.fase not in ("I", "II"):
        return 0
    restante = sg.timestamp + timedelta(minutes=VENTANA_DESHACER_MIN) - (momento or ahora())
    return max(0, int(restante.total_seconds()))


def anular_ultimo_subgrupo(db: Session, v: Variable, usuario: str | None, motivo: str | None,
                           momento: datetime | None = None) -> dict:
    """Anula el último registro manual (error de digitación) dentro de la ventana permitida.

    No se borra: pasa a la fase "anulado" (deja de contar en cartas y análisis, el número no se
    reutiliza), sus alarmas se cierran con la causa "registro anulado" y queda una entrada en el
    historial de cambios con los valores anulados.
    """
    sg = ultimo_subgrupo(db, v)
    if sg is None:
        raise HTTPException(409, "No hay registros para deshacer.")
    if segundos_para_deshacer(sg, momento) <= 0:
        raise HTTPException(409, f"Ya pasaron más de {VENTANA_DESHACER_MIN} minutos desde el último registro (o no fue "
                                 "cargado a mano). Pide al ingeniero que lo revise y, si corresponde, lo excluya.")
    motivo = (motivo or "").strip() or "Error al cargar los valores"
    valores = sg.valores if not es_atributos(v) else {"conteo": sg.conteo, "tamano": sg.tamano}
    sg.fase = "anulado"
    sg.comentario = f"Anulado: {motivo}"
    for a in db.scalars(select(Alarma).where(Alarma.subgrupo_id == sg.id, Alarma.estado != "resuelta")):
        a.estado, a.causa, a.accion = "resuelta", f"Registro anulado: {motivo}", "Se anuló el registro de la muestra"
        a.usuario, a.cerrada, a.actualizada = usuario_o_anonimo(usuario), ahora(), ahora()
    registrar_cambio(db, v, f"anulación subgrupo #{sg.numero}", valores, None, usuario, motivo)
    db.commit()
    return {"anulado": sg.numero, "motivo": motivo}


def modo_demo(db: Session) -> bool:
    """Modo demostración: muestra en la vista Operario el botón para completar con valores simulados."""
    aj = db.get(Ajuste, "modo_demo")
    return bool(aj.valor.get("activo")) if aj else False


def guardar_modo_demo(db: Session, activo: bool) -> bool:
    aj = db.get(Ajuste, "modo_demo")
    if aj:
        aj.valor = {"activo": bool(activo)}
    else:
        db.add(Ajuste(clave="modo_demo", valor={"activo": bool(activo)}))
    db.commit()
    return bool(activo)


def evaluar_alarmas(db: Session, v: Variable, sg: Subgrupo) -> list[Alarma]:
    """Crea una alarma por cada regla que el subgrupo nuevo activa (sin duplicar rachas).

    Se calcula la carta de la fase actual y se toman las violaciones cuyo punto final es el
    subgrupo nuevo y que inician una secuencia (`inicio`), para no repetir la alarma mientras
    una racha continúa.
    """
    activo = limites_activos(db, v)
    if v.fase == "II" and activo is None:
        return []
    sgs = subgrupos_de(db, v, (v.fase,))
    try:
        res = _calcular_core(v, sgs, activo.datos if v.fase == "II" else None)
    except ValueError:
        return []  # aún no hay datos suficientes para estimar límites
    ultimo = len(sgs) - 1
    nuevas = []
    for clave, carta in res["cartas"].items():
        for viol in carta["violaciones"]:
            if viol["indice"] != ultimo or not viol["inicio"]:
                continue
            regla = CATALOGO[viol["regla"]]
            lado = {"+": " (lado superior)", "-": " (lado inferior)"}.get(viol["lado"] or "", "")
            dispersion = clave in ("r", "s", "mr")
            alarma = Alarma(
                variable_id=v.id, subgrupo_id=sg.id, tipo="regla", regla=regla.id, carta=clave,
                descripcion=f"Subgrupo #{sg.numero}, carta {carta['nombre']}: {regla.condicion}{lado}.",
                explicacion=_explicacion_alarma(regla.id, viol["lado"], dispersion),
                severidad=regla.severidad,
            )
            db.add(alarma)
            nuevas.append(alarma)
    db.flush()
    return nuevas


def _explicacion_alarma(regla: str, lado: str | None, dispersion: bool = False) -> str:
    """Texto para el operario. En las cartas de dispersión (R, S, MR) la señal habla de la
    diferencia entre las unidades de la muestra, no del valor."""
    if dispersion:
        return ("Las unidades de esta muestra son demasiado distintas entre sí: la variación del proceso aumentó."
                if lado != "-" else "Las unidades de esta muestra son inusualmente parecidas entre sí.")
    return explicar(regla, lado)


def _explicacion_de(a: Alarma) -> str:
    """Explicación guardada o, para alarmas anteriores a la columna, deducida de la descripción."""
    if a.explicacion:
        return a.explicacion
    if a.tipo != "regla":
        return a.descripcion
    lado = "+" if "lado superior" in a.descripcion else "-" if "lado inferior" in a.descripcion else None
    return _explicacion_alarma(a.regla, lado, a.carta in ("r", "s", "mr"))


def alarma_a_dict(a: Alarma) -> dict:
    return {
        "id": a.id, "variable_id": a.variable_id, "subgrupo_id": a.subgrupo_id,
        "subgrupo_numero": a.subgrupo.numero if a.subgrupo else None, "tipo": a.tipo, "regla": a.regla,
        "regla_nombre": CATALOGO[a.regla].nombre if a.regla in CATALOGO else "Evento manual", "carta": a.carta,
        "descripcion": a.descripcion, "explicacion": _explicacion_de(a),
        "severidad": a.severidad, "estado": a.estado, "causa": a.causa,
        "accion": a.accion, "usuario": a.usuario, "creada": a.creada, "actualizada": a.actualizada,
        "cerrada": a.cerrada,
    }


def actualizar_alarma(db: Session, a: Alarma, estado=None, causa=None, accion=None, usuario=None) -> Alarma:
    """Registra causa/acción y cambia el estado. Para resolver se exigen causa y acción."""
    if causa is not None:
        a.causa = causa.strip() or None
    if accion is not None:
        a.accion = accion.strip() or None
    if estado:
        if estado == "resuelta" and not (a.causa and a.accion):
            raise HTTPException(422, "Para resolver la alarma registre la causa y la acción tomada.")
        a.estado = estado
        a.cerrada = ahora() if estado == "resuelta" else None
    a.usuario = usuario_o_anonimo(usuario)
    a.actualizada = ahora()
    db.commit()
    return a


# ---------------------------------------------------------------------------
# Fase I → Fase II
# ---------------------------------------------------------------------------

def registrar_cambio(db: Session, v: Variable, parametro: str, anterior, nuevo, usuario: str | None,
                     justificacion: str | None) -> CambioConfiguracion:
    """Agrega una entrada al historial de auditoría con el hash de la configuración vigente."""
    def txt(x):
        if x is None:
            return None
        return json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else str(x)

    cambio = CambioConfiguracion(variable_id=v.id, usuario=usuario_o_anonimo(usuario), parametro=parametro,
                                 valor_anterior=txt(anterior), valor_nuevo=txt(nuevo), justificacion=justificacion,
                                 version=v.version, hash=hash_config(v))
    db.add(cambio)
    return cambio


def congelar_limites(db: Session, v: Variable, usuario: str | None, motivo: str | None) -> dict:
    """Congela los límites de la Fase I y pasa la variable a Fase II.

    Devuelve los límites y advertencias si quedan señales en la base o si hay menos de 20
    subgrupos útiles (Montgomery recomienda 20–25).
    """
    if v.fase != "I":
        raise HTTPException(409, "La variable ya está en Fase II.")
    sgs = subgrupos_de(db, v, ("I",))
    if len(sgs) < 2:
        raise HTTPException(422, "Se necesitan subgrupos en la Fase I para estimar los límites.")
    res = _calcular_core(v, sgs, None)
    senales = [sgs[i].numero for i in res["puntos_con_senal"] if not sgs[i].excluido]
    advertencias = []
    if senales:
        advertencias.append(f"Quedan señales sin excluir en los subgrupos {senales}.")
    m = res["limites"]["m_usados"]
    if m < 20:
        advertencias.append(f"Solo {m} subgrupos en la base (se recomiendan 20–25).")

    for previo in db.scalars(select(LimitesCarta).where(LimitesCarta.variable_id == v.id, LimitesCarta.activo)):
        previo.activo, previo.archivado = False, ahora()
    lim = LimitesCarta(variable_id=v.id, tipo_carta=v.tipo_carta, datos=res["limites"], m_usados=m,
                       excluidos=[sg.numero for sg in sgs if sg.excluido], usuario=usuario_o_anonimo(usuario),
                       motivo=motivo)
    db.add(lim)
    v.fase = "II"
    v.version += 1
    db.flush()
    registrar_cambio(db, v, "fase", "I", "II", usuario, motivo or "Congelamiento de límites de Fase I")
    registrar_cambio(db, v, "limites", None, _resumen_limites(res["limites"]), usuario,
                     f"Límites congelados con {m} subgrupos")
    db.commit()
    return {"limites": _limites_a_dict(lim), "advertencias": advertencias}


def _resumen_limites(lim: dict) -> dict:
    """Versión compacta de los límites para el historial."""
    salida = {}
    for clave in ("xbar", "r", "s", "i", "mr"):
        if clave in lim:
            salida[clave] = {k: round(float(x), 6) for k, x in lim[clave].items()}
    for clave in ("p_barra", "c_barra", "u_barra", "sigma_hat"):
        if clave in lim:
            salida[clave] = round(float(lim[clave]), 6)
    return salida


def volver_fase_i(db: Session, v: Variable, usuario: str | None, motivo: str | None, usar_fase_ii_como_base: bool) -> dict:
    """Archiva los límites activos y vuelve a la Fase I (motivo obligatorio).

    Si `usar_fase_ii_como_base`, los subgrupos de la Fase II pasan a ser la nueva base de Fase I
    y los de la base anterior se archivan.
    """
    if v.fase != "II":
        raise HTTPException(409, "La variable ya está en Fase I.")
    if not motivo or len(motivo.strip()) < 3:
        raise HTTPException(422, "Indique el motivo para volver a la Fase I.")
    for l in db.scalars(select(LimitesCarta).where(LimitesCarta.variable_id == v.id, LimitesCarta.activo)):
        l.activo, l.archivado = False, ahora()
    if usar_fase_ii_como_base:
        for sg in subgrupos_de(db, v, ("I",)):
            sg.fase = "archivo"
        for sg in subgrupos_de(db, v, ("II",)):
            sg.fase = "I"
    else:
        for sg in subgrupos_de(db, v, ("II",)):
            sg.fase = "archivo"
    v.fase = "I"
    v.version += 1
    db.flush()
    registrar_cambio(db, v, "fase", "II", "I", usuario, motivo)
    db.commit()
    return variable_a_dict(v)


def excluir_subgrupo(db: Session, sg: Subgrupo, excluido: bool, causa: str | None, accion: str | None,
                     usuario: str | None) -> Subgrupo:
    """Marca o desmarca un subgrupo como excluido (causa asignable obligatoria al excluir)."""
    v = sg.variable
    if excluido and not (causa and causa.strip()):
        raise HTTPException(422, "Para excluir un subgrupo indique la causa asignable.")
    if sg.fase != "I":
        raise HTTPException(409, "Solo se excluyen subgrupos de la Fase I (los de Fase II no recalculan límites).")
    anterior = sg.excluido
    sg.excluido = excluido
    sg.causa_exclusion = causa.strip() if excluido and causa else None
    sg.accion_exclusion = accion.strip() if excluido and accion else None
    if anterior != excluido:
        registrar_cambio(db, v, f"exclusion subgrupo #{sg.numero}", anterior, excluido, usuario,
                         causa or "Reincorporación del subgrupo")
    db.commit()
    return sg


def simular_exclusion(db: Session, v: Variable, numeros: list[int]) -> dict:
    """Impacto de excluir los subgrupos indicados (sin guardar): límites y Cpk antes y después."""
    sgs = subgrupos_de(db, v, ("I",))
    actuales = [i for i, sg in enumerate(sgs) if sg.excluido]
    nuevos = [i for i, sg in enumerate(sgs) if sg.numero in set(numeros)]
    kw = {"k": v.k_sigma, "reglas": _reglas(v)}
    try:
        if v.tipo_carta in TIPOS_VARIABLES:
            datos = [sg.valores for sg in sgs]
            res = gv.simular_exclusion(v.tipo_carta, datos, actuales, nuevos, **kw)
        else:
            conteos = [sg.conteo or 0 for sg in sgs]
            tam = [sg.tamano or v.n for sg in sgs]
            a = ga.calcular_carta_atributos(v.tipo_carta, conteos, tam, excluidos=actuales, **kw)
            d = ga.calcular_carta_atributos(v.tipo_carta, conteos, tam, excluidos=nuevos, **kw)
            ca, cd = a["cartas"][v.tipo_carta], d["cartas"][v.tipo_carta]
            m = lambda x: float(np.mean(x))
            res = {"antes": {k: m(ca[k]) for k in ("lc", "lcs", "lci")},
                   "despues": {k: m(cd[k]) for k in ("lc", "lcs", "lci")},
                   "senales_despues": d["puntos_con_senal"]}
            res["delta"] = {k: res["despues"][k] - res["antes"][k] for k in ("lc", "lcs", "lci")}
    except ValueError as e:
        raise HTTPException(422, str(e))
    res["senales_despues"] = [sgs[i].numero for i in res["senales_despues"] if i not in nuevos]
    if v.tipo_carta in TIPOS_VARIABLES and (v.lei is not None or v.les is not None):
        def cpk(excl):
            grupos = [sg.valores for i, sg in enumerate(sgs) if i not in excl]
            return _capacidad_core(v, grupos)["indices"]["cpk"]
        res["cpk_antes"], res["cpk_despues"] = cpk(set(actuales)), cpk(set(nuevos))
    return res


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

def actualizar_configuracion(db: Session, v: Variable, cambios: dict, borrar: list[str], usuario: str | None,
                             justificacion: str) -> dict:
    """Aplica los cambios de configuración, sube la versión y deja una entrada por parámetro."""
    nuevos = {k: val for k, val in cambios.items() if k in CAMPOS_CONFIG and val is not None}
    for campo in borrar:
        nuevos[campo] = None
    modificados = {k: val for k, val in nuevos.items() if getattr(v, k) != val}
    if not modificados:
        return {"variable": variable_a_dict(v), "cambios": []}
    if v.fase == "II":
        bloqueados = [k for k in modificados if k in CAMPOS_ESTRUCTURALES]
        if bloqueados:
            raise HTTPException(409, f"No se puede cambiar {', '.join(bloqueados)} con límites congelados; "
                                     "vuelva primero a la Fase I.")
    if "reglas" in modificados:
        desconocidas = [r for r in modificados["reglas"] if r not in CATALOGO]
        if desconocidas:
            raise HTTPException(422, f"Reglas desconocidas: {desconocidas}")
    if "tipo_carta" in modificados:
        nuevo_tipo = modificados["tipo_carta"]
        if (nuevo_tipo in TIPOS_ATRIBUTOS) != es_atributos(v) and v.subgrupos:
            raise HTTPException(409, "No se puede cambiar entre variables y atributos si ya hay subgrupos.")
        if (nuevo_tipo == "imr") != (v.tipo_carta == "imr") and v.subgrupos:
            raise HTTPException(409, "No se puede cambiar entre subgrupos (n > 1) e individuales (I-MR) si ya hay datos.")
    lei = modificados.get("lei", v.lei)
    les = modificados.get("les", v.les)
    if lei is not None and les is not None and lei >= les:
        raise HTTPException(422, "LEI debe ser menor que LES.")

    anteriores = {k: getattr(v, k) for k in modificados}
    for k, val in modificados.items():
        setattr(v, k, val)
    if "tipo_carta" in modificados:
        v.tipo_dato = "atributos" if v.tipo_carta in TIPOS_ATRIBUTOS else "variables"
    v.version += 1
    db.flush()
    registros = [registrar_cambio(db, v, k, anteriores[k], val, usuario, justificacion) for k, val in modificados.items()]
    db.commit()
    return {"variable": variable_a_dict(v), "cambios": [cambio_a_dict(c) for c in registros]}


# ---------------------------------------------------------------------------
# Plan de muestreo (n, frecuencia, k, σ) con ARL / ATS
# ---------------------------------------------------------------------------

def horas_por_turno(db: Session) -> float:
    """Duración del primer turno configurado (para expresar la carga muestral por turno)."""
    t = obtener_turnos(db)[0]
    h0, m0 = map(int, t["inicio"].split(":"))
    h1, m1 = map(int, t["fin"].split(":"))
    minutos = (h1 * 60 + m1 - h0 * 60 - m0) % (24 * 60) or 24 * 60
    return minutos / 60


def referencia_plan(db: Session, v: Variable) -> dict:
    """σ (variables) o nivel medio de defectos (atributos) con que se evalúa el plan.

    Orden: σ fijada por el ingeniero → límites congelados → estimación con la Fase I actual.
    """
    activo = limites_activos(db, v)
    if es_atributos(v):
        clave = {"p": "p_barra", "np": "p_barra", "c": "c_barra", "u": "u_barra"}[v.tipo_carta]
        if activo and clave in activo.datos:
            return {"centro": float(activo.datos[clave]), "origen": "límites congelados"}
        sgs = [sg for sg in subgrupos_de(db, v, ("I",)) if not sg.excluido]
        if sgs:
            try:
                lim = _calcular_core(v, sgs, None)["limites"]
                if lim.get(clave):
                    return {"centro": float(lim[clave]), "origen": "datos de la Fase I"}
            except (ValueError, HTTPException):
                pass
        return {"centro": None, "origen": "sin datos"}
    if v.sigma_monitoreo:
        return {"sigma": v.sigma_monitoreo, "origen": "fijada por el ingeniero"}
    if activo:
        return {"sigma": float(activo.datos["sigma_hat"]), "origen": "límites congelados"}
    sgs = subgrupos_de(db, v, ("I",))
    if len(sgs) >= 2:
        try:
            return {"sigma": float(_calcular_core(v, sgs, None)["sigma_hat"]), "origen": "datos de la Fase I"}
        except (ValueError, HTTPException):
            pass
    return {"sigma": None, "origen": "sin datos"}


def _evaluar_plan(v: Variable, n: int, frecuencia_min: float, k: float, delta: float, centro, centro_1,
                  sigma, horas_turno: float) -> dict:
    """Desempeño (ARL/ATS), carga muestral y explicación de un plan concreto."""
    from app.core import diseno_arl as core_arl

    h = frecuencia_min / 60
    carga = core_arl.carga_muestral(n, frecuencia_min, horas_turno)
    if es_atributos(v):
        if centro is None:  # sin datos todavía: solo se puede informar la carga muestral
            return {"n": n, "frecuencia_min": frecuencia_min, "k": k, "carga": carga, "diseno": None,
                    "textos": {"carga": core_arl.texto_carga(carga)}}
        d = core_arl.diseno_atributos(v.tipo_carta, centro, centro_1, n, k, h)
        textos = core_arl.textos_plan(d, carga, es_porcentaje=v.tipo_carta in ("p", "np"))
    else:
        d = core_arl.diseno(k, 1 if v.tipo_carta == "imr" else n, h, delta)
        textos = core_arl.textos_plan(d, carga, v.unidad, sigma)
    return {"n": n, "frecuencia_min": frecuencia_min, "k": k, "carga": carga, "diseno": d, "textos": textos}


def plan_muestreo(db: Session, v: Variable, n: int | None = None, frecuencia_min: float | None = None,
                  k: float | None = None, delta: float = 1.0, centro_1: float | None = None,
                  sigma: float | None = None, centro: float | None = None) -> dict:
    """Compara el plan vigente de la variable con uno propuesto (sin guardar nada).

    `centro` permite indicar el nivel de defectos esperado cuando aún no hay datos (atributos).
    """
    ref = referencia_plan(db, v)
    if centro is not None and es_atributos(v):
        ref = {"centro": centro, "origen": "indicado por el usuario"}
    sigma_ref = ref.get("sigma")
    centro = ref.get("centro")
    if es_atributos(v) and centro is not None and centro_1 is None:
        centro_1 = min(2 * centro, 0.99) if v.tipo_carta in ("p", "np") else 2 * centro
    ht = horas_por_turno(db)
    n_prop = 1 if v.tipo_carta == "imr" else (n or v.n)
    actual = _evaluar_plan(v, 1 if v.tipo_carta == "imr" else v.n, v.frecuencia_min, v.k_sigma, delta, centro,
                           centro_1, sigma_ref, ht)
    propuesto = _evaluar_plan(v, n_prop, frecuencia_min or v.frecuencia_min, k or v.k_sigma, delta, centro,
                              centro_1, sigma or sigma_ref, ht)
    return {"variable": variable_a_dict(v), "referencia": ref, "centro_1": centro_1, "delta": delta,
            "horas_turno": ht, "actual": actual, "propuesto": propuesto,
            "avisos": _avisos_plan(db, v, n_prop)}


def carga_objetivo(db: Session, v: Variable, carga: float | None = None, cambio: float | None = None, m: int = 5,
                   horizonte_h: float | None = None, k: float | None = None, sigma: float | None = None) -> dict:
    """Carga muestral objetivo: compara el plan vigente con los dos caminos para llegar a `carga`
    (unidades por hora): aumentar n o reducir el intervalo. Mide la potencia frente a un cambio de la
    media de `cambio` unidades de la variable. Solo para mediciones (cartas X̄ e I)."""
    from app.core import diseno_arl as core_arl

    if es_atributos(v):
        raise HTTPException(400, "La carga muestral objetivo con potencia está disponible para variables que se miden "
                                 "(gráficas de promedios o de valores individuales).")
    ref = referencia_plan(db, v)
    s = sigma or ref.get("sigma")
    if not s:
        raise HTTPException(400, "Todavía no hay datos para estimar la variabilidad del proceso (σ). Carga algunas "
                                 "muestras o fija la σ en el plan de muestreo.")
    individual = v.tipo_carta == "imr"
    n = 1 if individual else v.n
    k = k or v.k_sigma
    carga_actual = n * 60.0 / v.frecuencia_min
    carga = carga or 2 * carga_actual
    if cambio is None:
        cambio = round(s, v.decimales) or s
    T = horizonte_h * 60 if horizonte_h else None
    try:
        res = core_arl.comparar_carga(n, v.frecuencia_min, k, s, cambio, carga, m, T, n_fijo=individual)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ht = horas_por_turno(db)
    avisos = []
    a = res["planes"]["a"]
    if a and v.tipo_carta == "xbar_r" and a["n"] > 10:
        avisos.append(f"Con {a['n']} unidades por muestra conviene la gráfica de promedios y desviación (X̄-S); "
                      "el tipo de gráfica se cambia en la Fase I.")
    if a and a["n"] != v.n:
        avisos += _avisos_plan(db, v, a["n"])
    return {**res, "variable": variable_a_dict(v), "referencia": ref, "horas_turno": ht, "carga_actual": carga_actual,
            "textos": core_arl.textos_carga(res, v.unidad, v.decimales, ht), "avisos": avisos}


def _avisos_plan(db: Session, v: Variable, n_nuevo: int) -> list[str]:
    """Qué pasará con los datos ya registrados si se cambia n (en lenguaje simple)."""
    if n_nuevo == v.n or v.tipo_carta in ("p", "u", "c", "imr"):
        return []
    if v.fase == "II":
        cuantos = len(subgrupos_de(db, v, ("II",)))
        return [f"Los límites se recalculan para muestras de {n_nuevo} unidades con la misma variabilidad del proceso. "
                + (f"Las {cuantos} muestras de monitoreo tomadas con {v.n} unidades pasan al archivo (siguen en el "
                   "historial, pero la gráfica empieza de nuevo)." if cuantos else "")]
    if subgrupos_de(db, v, ("I",)) and v.tipo_carta in ("xbar_r", "np"):
        return [f"Ya hay muestras de {v.n} unidades en la Fase I. Para usar {n_nuevo} unidades hay que empezar la "
                "Fase I de nuevo (las muestras actuales pasan al archivo)."]
    return []


def aplicar_plan(db: Session, v: Variable, n: int | None, frecuencia_min: int | None, k_sigma: float | None,
                 sigma_monitoreo: float | None, borrar_sigma: bool, usuario: str | None, justificacion: str,
                 reiniciar_fase_i: bool = False) -> dict:
    """Guarda un plan de muestreo. En Fase II recalcula los límites congelados conservando el
    centro y la σ (o la σ nueva indicada por el ingeniero) con `limites_con_sigma`."""
    if not justificacion or len(justificacion.strip()) < 3:
        raise HTTPException(422, "Escriba brevemente por qué cambia el plan (queda en el historial).")
    if (sigma_monitoreo is not None or borrar_sigma) and es_atributos(v):
        raise HTTPException(422, "En las cartas de conteo la variación depende del promedio de defectos; "
                                 "no se fija a mano.")
    if sigma_monitoreo is not None and not sigma_monitoreo > 0:
        raise HTTPException(422, "La σ de monitoreo debe ser un número mayor que cero.")
    if v.tipo_carta == "imr" and n not in (None, 1):
        raise HTTPException(422, "Esta variable registra una medición por vez (carta I-MR); n es siempre 1.")
    if n is not None and n < 2 and v.tipo_carta in ("xbar_r", "xbar_s"):
        raise HTTPException(422, "Las cartas X̄ necesitan al menos 2 unidades por muestra. Para medir de a una, "
                                 "cree la variable con la carta I-MR.")
    nuevos = {"n": n, "frecuencia_min": frecuencia_min, "k_sigma": k_sigma,
              "sigma_monitoreo": None if borrar_sigma else sigma_monitoreo}
    modificados = {c: val for c, val in nuevos.items()
                   if (val is not None or (c == "sigma_monitoreo" and borrar_sigma)) and getattr(v, c) != val}
    if not modificados:
        return {"variable": variable_a_dict(v), "cambios": [], "limites_recalculados": False, "archivados": 0}

    archivados = 0
    cambia_n = "n" in modificados
    if v.fase == "I" and cambia_n and v.tipo_carta in ("xbar_r", "np"):
        previos = subgrupos_de(db, v, ("I",))
        if previos and not reiniciar_fase_i:
            raise HTTPException(409, _avisos_plan(db, v, modificados["n"])[0])
        for sg in previos:
            sg.fase = "archivo"
        archivados = len(previos)

    limites_nuevos = None
    activo = limites_activos(db, v) if v.fase == "II" else None
    if activo and any(c in modificados for c in ("n", "k_sigma", "sigma_monitoreo")):
        datos = dict(activo.datos)
        k_nuevo = modificados.get("k_sigma", v.k_sigma)
        n_nuevo = modificados.get("n", v.n)
        if es_atributos(v):
            datos["k"] = k_nuevo
            if v.tipo_carta == "np":
                datos["n"] = int(n_nuevo)
            limites_nuevos = datos
        else:
            if "sigma_monitoreo" in modificados:
                sigma = modificados["sigma_monitoreo"] or datos.get("sigma_estimada_datos", datos["sigma_hat"])
            else:
                sigma = datos["sigma_hat"]
            limites_nuevos = gv.limites_con_sigma(v.tipo_carta, gv.centro_de_limites(datos), sigma,
                                                  1 if v.tipo_carta == "imr" else n_nuevo, k_nuevo)
            limites_nuevos["m_usados"] = datos.get("m_usados")
            limites_nuevos["sigma_estimada_datos"] = datos.get("sigma_estimada_datos", datos["sigma_hat"])
        if cambia_n and v.tipo_carta in ("xbar_r", "xbar_s", "np"):
            previos = subgrupos_de(db, v, ("II",))
            for sg in previos:
                sg.fase = "archivo"
            archivados = len(previos)

    anteriores = {c: getattr(v, c) for c in modificados}
    for c, val in modificados.items():
        setattr(v, c, val)
    v.version += 1
    if limites_nuevos is not None:
        activo.activo, activo.archivado = False, ahora()
        db.add(LimitesCarta(variable_id=v.id, tipo_carta=v.tipo_carta, datos=limites_nuevos,
                            m_usados=activo.m_usados, excluidos=activo.excluidos,
                            usuario=usuario_o_anonimo(usuario), motivo=f"Cambio de plan: {justificacion}"))
    db.flush()
    registros = [registrar_cambio(db, v, c, anteriores[c], val, usuario, justificacion) for c, val in modificados.items()]
    if limites_nuevos is not None:
        registros.append(registrar_cambio(db, v, "limites", _resumen_limites(activo.datos),
                                          _resumen_limites(limites_nuevos), usuario,
                                          "Límites recalculados por cambio de plan"))
    if archivados:
        registros.append(registrar_cambio(db, v, "subgrupos archivados", None, archivados, usuario,
                                          f"Muestras tomadas con n = {anteriores.get('n')} pasan al archivo"))
    db.commit()
    return {"variable": variable_a_dict(v), "cambios": [cambio_a_dict(c) for c in registros],
            "limites_recalculados": limites_nuevos is not None, "archivados": archivados}


def cambio_a_dict(c: CambioConfiguracion) -> dict:
    return {"id": c.id, "variable_id": c.variable_id, "fecha": c.fecha, "usuario": c.usuario, "parametro": c.parametro,
            "valor_anterior": c.valor_anterior, "valor_nuevo": c.valor_nuevo, "justificacion": c.justificacion,
            "version": c.version, "hash": c.hash}


def obtener_turnos(db: Session) -> list[dict]:
    """Turnos programados (con días de trabajo y arranque completados por defecto)."""
    from app.core import turnos as core_t

    aj = db.get(Ajuste, "turnos")
    return core_t.normalizar(aj.valor if aj else TURNOS_POR_DEFECTO)


def guardar_turnos(db: Session, turnos: list[dict]) -> list[dict]:
    from app.core import turnos as core_t

    turnos = core_t.normalizar(turnos)
    errores = core_t.validar(turnos)
    if errores:
        raise HTTPException(422, " ".join(errores))
    aj = db.get(Ajuste, "turnos")
    if aj:
        aj.valor = turnos
    else:
        db.add(Ajuste(clave="turnos", valor=turnos))
    db.commit()
    return turnos


def turno_actual(turnos: list[dict], momento: datetime) -> dict:
    """Turno programado que contiene `momento` con sus fechas de inicio y fin (admite turnos que cruzan
    medianoche y respeta los días de trabajo); "Sin turno" si no hay ninguno."""
    from app.core import turnos as core_t

    v = core_t.ventana_en(core_t.normalizar(turnos), momento)
    if v:
        return v
    hoy = datetime.combine(momento.date(), time(0))
    return {"nombre": "Sin turno", "inicio": "00:00", "fin": "23:59", "desde": hoy, "hasta": hoy + timedelta(days=1)}


# ---------------------------------------------------------------------------
# Turnos reales: se abren y cierran solos según la programación, o a mano
# ---------------------------------------------------------------------------

def turno_a_dict(t: TurnoRegistro | None) -> dict | None:
    if t is None:
        return None
    return {"id": t.id, "numero": t.numero, "nombre": t.nombre, "inicio": t.inicio, "fin": t.fin,
            "inicio_programado": t.inicio_programado, "fin_programado": t.fin_programado,
            "abierto": t.fin is None, "cierre": t.cierre, "arranque_min": t.arranque_min,
            "abierto_por": t.abierto_por, "cerrado_por": t.cerrado_por}


def turno_abierto(db: Session) -> TurnoRegistro | None:
    return db.scalar(select(TurnoRegistro).where(TurnoRegistro.fin.is_(None)).order_by(TurnoRegistro.id.desc()))


def _nuevo_turno(db: Session, nombre: str, inicio: datetime, inicio_prog: datetime, fin_prog: datetime,
                 arranque: int | None, usuario: str) -> TurnoRegistro:
    numero = (db.scalar(select(func.max(TurnoRegistro.numero))) or 0) + 1
    t = TurnoRegistro(numero=numero, nombre=nombre, inicio=inicio, inicio_programado=inicio_prog,
                      fin_programado=fin_prog, arranque_min=arranque, abierto_por=usuario)
    db.add(t)
    db.flush()
    return t


def sincronizar_turnos(db: Session, momento: datetime | None = None) -> TurnoRegistro | None:
    """Pone los turnos reales al día "al despertar" (al consultar o registrar):

    1. Si el turno abierto ya pasó su hora de fin, se cierra a esa hora (cierre "hora").
    2. Si no hay turno abierto y `momento` cae en un turno programado cuya ventana todavía no tiene
       registro, se abre uno nuevo desde el inicio programado. Una ventana cerrada a mano no se reabre.

    Si nadie usó el programa durante un turno, ese turno no queda registrado (no se inventan turnos).
    """
    from app.core import turnos as core_t

    momento = momento or ahora()
    abierto = turno_abierto(db)
    cambio = False
    if abierto and momento >= abierto.fin_programado:
        abierto.fin, abierto.cierre, abierto.cerrado_por = abierto.fin_programado, "hora", "Automático"
        abierto, cambio = None, True
    if abierto is None:
        v = core_t.ventana_en(obtener_turnos(db), momento)
        if v and not db.scalar(select(TurnoRegistro.id).where(TurnoRegistro.inicio_programado == v["desde"],
                                                              TurnoRegistro.nombre == v["nombre"])):
            abierto = _nuevo_turno(db, v["nombre"], v["desde"], v["desde"], v["hasta"], v["arranque_min"], "Automático")
            cambio = True
    if cambio:
        db.commit()
    return abierto


def estado_turno(db: Session, momento: datetime | None = None) -> dict:
    """Turno abierto (si hay), próximo turno programado y la programación vigente."""
    from app.core import turnos as core_t

    momento = momento or ahora()
    abierto = sincronizar_turnos(db, momento)
    programados = obtener_turnos(db)
    prox = core_t.proxima_ventana(programados, momento)
    return {"momento": momento, "abierto": turno_a_dict(abierto),
            "proximo": {"nombre": prox["nombre"], "desde": prox["desde"], "hasta": prox["hasta"]} if prox else None,
            "programados": [{**t, "dias_texto": core_t.texto_dias(t["dias"])} for t in programados]}


def iniciar_turno(db: Session, nombre: str | None, usuario: str | None, momento: datetime | None = None) -> dict:
    """Abre un turno a mano (por ejemplo, si la línea arranca antes o en un día no programado).

    Si `momento` cae dentro de la ventana de ese turno programado, el turno termina a su hora de fin;
    si no, dura lo mismo que el turno programado a partir de ahora.
    """
    from app.core import turnos as core_t

    momento = momento or ahora()
    if sincronizar_turnos(db, momento):
        raise HTTPException(409, "Ya hay un turno abierto. Termínalo antes de iniciar otro.")
    programados = obtener_turnos(db)
    if not nombre:
        prox = core_t.proxima_ventana(programados, momento)
        nombre = prox["nombre"] if prox else programados[0]["nombre"]
    prog = next((t for t in programados if t["nombre"].lower() == nombre.strip().lower()), None)
    if prog is None:
        raise HTTPException(422, f"No hay un turno programado llamado «{nombre}». Revisa los turnos en Límites y reglas.")
    v = core_t.ventana_en([{**prog, "dias": core_t.TODOS_LOS_DIAS}], momento)
    if v:
        inicio_prog, fin_prog = v["desde"], v["hasta"]
    else:
        inicio_prog, fin_prog = momento, momento + timedelta(minutes=core_t.duracion_min(prog))
    t = _nuevo_turno(db, prog["nombre"], momento, inicio_prog, fin_prog, prog["arranque_min"], usuario_o_anonimo(usuario))
    db.commit()
    return turno_a_dict(t)


def terminar_turno(db: Session, usuario: str | None, momento: datetime | None = None) -> dict:
    """Cierra a mano el turno abierto (cierre "manual"): la cuenta regresiva se detiene."""
    momento = momento or ahora()
    t = sincronizar_turnos(db, momento)
    if t is None:
        raise HTTPException(409, "No hay un turno abierto.")
    t.fin, t.cierre, t.cerrado_por = momento, "manual", usuario_o_anonimo(usuario)
    db.commit()
    return turno_a_dict(t)


def historial_turnos(db: Session, limite: int = 30, momento: datetime | None = None) -> list[dict]:
    """Últimos turnos reales con la cantidad de muestras registradas en cada uno."""
    sincronizar_turnos(db, momento)
    filas = list(db.scalars(select(TurnoRegistro).order_by(TurnoRegistro.id.desc()).limit(limite)))
    cuentas = dict(db.execute(select(Subgrupo.turno_id, func.count(Subgrupo.id)).where(
        Subgrupo.turno_id.in_([t.id for t in filas]), Subgrupo.fase != "anulado").group_by(Subgrupo.turno_id)).all())
    return [{**turno_a_dict(t), "muestras": cuentas.get(t.id, 0)} for t in filas]


def turno_de_momento(db: Session, momento: datetime) -> TurnoRegistro | None:
    """Turno real que contiene `momento` (para asociar muestras cargadas con su fecha y hora)."""
    return db.scalar(select(TurnoRegistro).where(
        TurnoRegistro.inicio <= momento,
        func.coalesce(TurnoRegistro.fin, TurnoRegistro.fin_programado) > momento).order_by(TurnoRegistro.id.desc()))


# ---------------------------------------------------------------------------
# Análisis (supuestos y capacidad) sobre una variable
# ---------------------------------------------------------------------------

def _metodo_sigma(v: Variable) -> str:
    if v.tipo_carta == "imr":
        return "mr"
    return v.estimador_sigma if v.estimador_sigma in ("rbar", "sbar") else ("sbar" if v.tipo_carta == "xbar_s" else "rbar")


def _capacidad_core(v: Variable, grupos: list, en_control: bool | None = None, metodo: str | None = None) -> dict:
    """Capacidad de la variable: usa la σ fijada por el ingeniero si existe; si no, σ dentro."""
    return core_cap.analizar_capacidad(grupos, v.lei, v.les, v.objetivo, metodo or _metodo_sigma(v), en_control,
                                       sigma=None if metodo else v.sigma_monitoreo)


MIN_SUBGRUPOS_FASE_II = 20


def grupos_para_analisis(db: Session, v: Variable, fase: str | None) -> list[Subgrupo]:
    """Subgrupos para supuestos/capacidad: Fase I sin excluidos, o la Fase II.

    Sin fase explícita se usa la Fase II solo si ya tiene al menos 20 subgrupos; si no, la
    base de la Fase I (es la referencia con la que se congelaron los límites).
    """
    if fase is None:
        n_ii = len(subgrupos_de(db, v, ("II",))) if v.fase == "II" else 0
        fase = "II" if n_ii >= MIN_SUBGRUPOS_FASE_II else "I"
    return [sg for sg in subgrupos_de(db, v, (fase,)) if not sg.excluido]


def supuestos_variable(db: Session, v: Variable, fase: str | None, alfa: float, rezagos: int) -> dict:
    """Diagnóstico de supuestos sobre las observaciones individuales en orden temporal."""
    if es_atributos(v):
        raise HTTPException(400, "La validación de normalidad se aplica a datos por variables.")
    sgs = grupos_para_analisis(db, v, fase)
    valores = [x for sg in sgs for x in sg.valores]
    try:
        res = core_sup.diagnostico(valores, alfa, rezagos)
    except ValueError as e:
        raise HTTPException(422, str(e))
    res["N"] = len(valores)
    res["k_subgrupos"] = len(sgs)
    res["variable"] = variable_a_dict(v)
    return res


def capacidad_variable(db: Session, v: Variable, fase: str | None, metodo: str | None) -> dict:
    """Estudio de capacidad con los subgrupos de la fase indicada + histograma y normalidad."""
    if es_atributos(v):
        raise HTTPException(400, "El análisis de capacidad Cp/Cpk se aplica a datos por variables.")
    if v.lei is None and v.les is None:
        raise HTTPException(422, "Defina al menos un límite de especificación en Configuración.")
    sgs = grupos_para_analisis(db, v, fase)
    grupos = [sg.valores for sg in sgs]
    if not grupos:
        raise HTTPException(422, "No hay subgrupos para analizar.")
    en_control = None
    try:
        carta = carta_variable(db, v)
        en_control = not carta.get("puntos_con_senal")
    except HTTPException:
        pass
    try:
        res = _capacidad_core(v, grupos, en_control, metodo)
    except ValueError as e:
        raise HTTPException(422, str(e))
    valores = [x for g in grupos for x in g]
    res["histograma"] = core_sup.histograma(valores)
    res["normalidad"] = core_sup.normalidad(valores) if len(valores) >= 8 else None
    res["qq"] = core_sup.qq_normal(valores) if len(valores) >= 8 else None
    res["k_subgrupos"] = len(grupos)
    res["en_control"] = en_control
    res["variable"] = variable_a_dict(v)
    from app.core.reportes import conclusiones_capacidad
    res["conclusiones"] = conclusiones_capacidad(res)
    return res


# ---------------------------------------------------------------------------
# Vista de operario
# ---------------------------------------------------------------------------

def alarmas_abiertas(db: Session, v: Variable, desde: datetime | None = None) -> list[Alarma]:
    q = select(Alarma).where(Alarma.variable_id == v.id, Alarma.estado != "resuelta")
    if desde:
        q = q.where(Alarma.creada >= desde)
    return list(db.scalars(q.order_by(Alarma.creada.desc())))


def _semaforo(v: Variable, abiertas: list[Alarma]) -> dict:
    """Estado del proceso en palabras para el operario, con lo que tiene que hacer."""
    if v.fase == "I":
        return {"color": "gris", "texto": "Fase I — límites provisionales",
                "titulo": "Conociendo el proceso",
                "que_hacer": "Registra las muestras como siempre. Con 20 a 25 muestras el ingeniero fijará los "
                             "límites normales del proceso."}
    if any(a.severidad == "critica" for a in abiertas):
        return {"color": "rojo", "texto": "Fuera de control", "titulo": "Detener y avisar",
                "que_hacer": "El proceso se salió de lo normal. Avisa al supervisor o al ingeniero antes de seguir "
                             "y anota en la alerta qué pudo haber pasado."}
    if abiertas:
        return {"color": "ambar", "texto": "En advertencia", "titulo": "Revisar",
                "que_hacer": "Hay señales de que algo está cambiando. Revisa la alerta, observa la máquina y anota "
                             "lo que encuentres."}
    return {"color": "verde", "texto": "Bajo control", "titulo": "El proceso va bien",
            "que_hacer": "Sigue tomando las muestras a tiempo."}


def _resumen_ventana(v: Variable, carta: dict) -> dict:
    """Resumen de las muestras graficadas (últimas 25) en términos simples.

    Variables: % de unidades dentro de especificación y promedio. Atributos: nivel medio de
    defectos (p̄ como %, o defectos por muestra / por unidad). También cuántas muestras tienen señal.
    """
    sgs = carta.get("subgrupos") or []
    salida = {"muestras": len(sgs), "con_senal": len(carta.get("puntos_con_senal") or [])}
    if not sgs:
        return salida
    if es_atributos(v):
        conteo = sum(sg["conteo"] or 0 for sg in sgs)
        tamano = sum((sg["tamano"] or v.n) for sg in sgs)
        if v.tipo_carta in ("p", "np"):
            salida["pct_defectuosos"] = conteo / tamano if tamano else None
        elif v.tipo_carta == "u":
            salida["defectos_por_unidad"] = conteo / tamano if tamano else None
        else:
            salida["defectos_por_muestra"] = conteo / len(sgs)
        return salida
    vals = np.array([x for sg in sgs for x in (sg.get("valores") or [])], dtype=float)
    salida["promedio"] = float(vals.mean()) if vals.size else None
    if vals.size and (v.lei is not None or v.les is not None):
        ok = np.ones(vals.size, bool)
        if v.lei is not None:
            ok &= vals >= v.lei
        if v.les is not None:
            ok &= vals <= v.les
        salida.update({"unidades": int(vals.size), "dentro": int(ok.sum()), "pct_dentro": float(ok.mean())})
    return salida


def _rango_habitual(v: Variable, carta: dict) -> dict | None:
    """Centro y σ de un valor individual, para avisar en la captura si un dato parece mal escrito."""
    lim = carta.get("limites") or {}
    if es_atributos(v) or not lim.get("sigma_hat"):
        return None
    try:
        centro = gv.centro_de_limites(lim)
    except (KeyError, TypeError):
        return None
    return {"centro": centro, "sigma": float(lim["sigma_hat"])}


def resumen_operario(db: Session, v: Variable, momento: datetime | None = None) -> dict:
    """Todo lo que muestra la vista de operario para la variable activa.

    - Carta en vivo con los últimos 25 subgrupos de la fase actual.
    - Semáforo: rojo si hay alarmas abiertas críticas; ámbar si hay otras abiertas; verde si no;
      gris si la variable aún está en Fase I (límites provisionales).
    - Cuenta regresiva: último subgrupo + frecuencia − ahora.
    - Turno actual: subgrupos tomados/programados, % conforme, Cpk y alarmas del turno.
    """
    momento = momento or ahora()
    try:
        carta = carta_variable(db, v, ultimos=25)
    except HTTPException as e:
        carta = {"error": e.detail, "cartas": {}}
    activo = limites_activos(db, v)
    desde_fase = activo.creado if (v.fase == "II" and activo) else None
    abiertas = alarmas_abiertas(db, v, desde_fase)
    semaforo = _semaforo(v, abiertas)

    from app.core import turnos as core_t

    ultimo = ultimo_subgrupo(db, v)
    est_turno = estado_turno(db, momento)          # sincroniza los turnos reales
    abierto = turno_abierto(db)
    if abierto:
        ultima_turno = db.scalar(select(Subgrupo).where(
            Subgrupo.variable_id == v.id, Subgrupo.turno_id == abierto.id, Subgrupo.fase != "anulado")
            .order_by(Subgrupo.timestamp.desc()))
        pm = core_t.proxima_muestra(abierto.inicio, abierto.fin_programado, ultima_turno.timestamp if ultima_turno else None,
                                    v.frecuencia_min, abierto.arranque_min, momento)
        estado_muestreo, proxima, segundos = pm["estado"], pm["vence"], pm["segundos"]
        ref = abierto
    else:
        estado_muestreo, proxima, segundos = "fuera_de_turno", None, None
        ref = db.scalar(select(TurnoRegistro).order_by(TurnoRegistro.id.desc()))  # último turno, para el resumen

    if ref:
        fin_ref = ref.fin or ref.fin_programado
        del_turno = list(db.scalars(select(Subgrupo).where(
            Subgrupo.variable_id == v.id, Subgrupo.turno_id == ref.id, Subgrupo.fase != "anulado")
            .order_by(Subgrupo.numero)))
        programados = core_t.muestras_programadas(ref.inicio, fin_ref, v.frecuencia_min, ref.arranque_min)
        alarmas_turno = list(db.scalars(select(Alarma).where(
            Alarma.variable_id == v.id, Alarma.creada >= ref.inicio, Alarma.creada < min(fin_ref, momento + timedelta(seconds=1)))
            .order_by(Alarma.creada.desc())))
        turno = {"id": ref.id, "numero": ref.numero, "nombre": ref.nombre, "abierto": ref.fin is None,
                 "inicio": ref.inicio.strftime("%H:%M"), "fin": fin_ref.strftime("%H:%M"),
                 "desde": ref.inicio, "hasta": fin_ref, "cierre": ref.cierre}
    else:
        del_turno, programados, alarmas_turno = [], 0, []
        turno = {"id": None, "numero": None, "nombre": "Sin turno", "abierto": False, "inicio": None, "fin": None,
                 "desde": None, "hasta": None, "cierre": None}

    conforme = None
    if del_turno:
        if es_atributos(v):
            if v.tipo_carta in ("p", "np"):
                d = sum(sg.conteo or 0 for sg in del_turno)
                n = sum(sg.tamano or v.n for sg in del_turno)
                conforme = 1 - d / n if n else None
        elif v.lei is not None or v.les is not None:
            vals = np.array([x for sg in del_turno for x in sg.valores])
            ok = np.ones(vals.size, bool)
            if v.lei is not None:
                ok &= vals >= v.lei
            if v.les is not None:
                ok &= vals <= v.les
            conforme = float(ok.mean()) if vals.size else None

    cap = None
    if not es_atributos(v) and (v.lei is not None or v.les is not None):
        # Capacidad "instantánea": ventana móvil de los últimos 25 subgrupos válidos (base de Fase I
        # + Fase II), para que el índice reaccione a un corrimiento sin depender de 2–3 subgrupos.
        fases = ("I", "II") if v.fase == "II" else ("I",)
        grupos = [sg.valores for sg in subgrupos_de(db, v, fases) if not sg.excluido][-25:]
        try:
            if len(grupos) >= 2:
                r = _capacidad_core(v, grupos)
                cap = {"cp": r["indices"]["cp"], "cpk": r["indices"]["cpk"], "sigma_dentro": r["sigma_dentro"],
                       "ppm_esperado": r["ppm_esperado"]["ppm"], "veredicto": r["veredicto"],
                       "k_subgrupos": len(grupos)}
        except ValueError:
            cap = None

    reglas_carta = {}
    for clave, c in carta.get("cartas", {}).items():
        activas = _reglas(v) if clave in ("xbar", "i") or es_atributos(v) else [r for r in _reglas(v) if r in REGLAS_DISPERSION]
        reglas_carta[clave] = {r: sum(1 for x in c["violaciones"] if x["regla"] == r) for r in activas}

    return {
        "ventana": _resumen_ventana(v, carta),
        "rango_habitual": _rango_habitual(v, carta),
        "segundos_para_deshacer": segundos_para_deshacer(ultimo, momento),
        "modo_demo": modo_demo(db),
        "variable": variable_a_dict(v),
        "proceso": proceso_a_dict(v.proceso, con_variables=False),
        "momento": momento,
        "semaforo": semaforo,
        "carta": carta,
        "violaciones_por_regla": reglas_carta,
        "ultimo_subgrupo": subgrupo_a_dict(ultimo, v) if ultimo else None,
        # Igual que en registrar_subgrupo: los números anulados no se reutilizan.
        "proximo_numero": (db.scalar(select(func.max(Subgrupo.numero)).where(Subgrupo.variable_id == v.id)) or 0) + 1,
        "proxima_muestra": proxima,
        "segundos_para_muestra": segundos,
        "muestra_atrasada": segundos is not None and segundos < 0,
        # en_turno | sin_mas_muestras | fuera_de_turno
        "estado_muestreo": estado_muestreo,
        "turno_abierto": est_turno["abierto"],
        "proximo_turno": est_turno["proximo"],
        "turno": {**turno, "subgrupos_tomados": len(del_turno), "subgrupos_programados": programados,
                  "fraccion_conforme": conforme, "alarmas": len(alarmas_turno),
                  "alarmas_resueltas": sum(a.estado == "resuelta" for a in alarmas_turno)},
        "capacidad": cap,
        "alarmas_abiertas": [alarma_a_dict(a) for a in abiertas],
        "alarmas_turno": [alarma_a_dict(a) for a in alarmas_turno],
    }


def simular_valores(db: Session, v: Variable, delta: float = 0.0, semilla: int | None = None) -> dict:
    """Valores de prueba para la captura (demostración): N(LC + δσ̂, σ̂) para variables,
    o un conteo binomial/Poisson para atributos, usando los límites vigentes."""
    rng = np.random.default_rng(semilla)
    activo = limites_activos(db, v)
    if activo is None:
        try:
            lim = _calcular_core(v, subgrupos_de(db, v, ("I",)), None)["limites"]
        except (ValueError, IndexError):
            raise HTTPException(409, "No hay límites para simular valores.")
    else:
        lim = activo.datos
    if v.tipo_carta in TIPOS_VARIABLES:
        clave = "i" if v.tipo_carta == "imr" else "xbar"
        centro = lim[clave]["lc"] if clave in lim else lim["x_barra"]
        sigma = lim["sigma_hat"]
        n = 1 if v.tipo_carta == "imr" else v.n
        vals = rng.normal(centro + delta * sigma, sigma, n)
        return {"valores": [round(float(x), v.decimales) for x in vals]}
    if v.tipo_carta in ("p", "np"):
        p = min(1.0, lim["p_barra"] * (1 + delta))
        return {"conteo": int(rng.binomial(v.n, p)), "tamano": v.n}
    media = lim.get("c_barra", lim.get("u_barra", 1.0) * v.n)
    return {"conteo": int(rng.poisson(media * (1 + delta))), "tamano": None if v.tipo_carta == "c" else v.n}
