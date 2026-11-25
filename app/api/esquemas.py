"""Esquemas Pydantic de entrada de la API (validación de los cuerpos JSON)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TipoCarta = Literal["xbar_r", "xbar_s", "imr", "p", "np", "c", "u"]


class ProcesoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    planta: str | None = None
    linea: str | None = None
    descripcion: str | None = None


class VariableCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    unidad: str = ""
    tipo_carta: TipoCarta = "xbar_r"
    n: int = Field(5, ge=1, le=10_000)
    frecuencia_min: int = Field(30, ge=1)
    lei: float | None = None
    objetivo: float | None = None
    les: float | None = None
    k_sigma: float = Field(3.0, gt=0, le=6)
    estimador_sigma: Literal["rbar", "sbar", "mr"] | None = None
    sigma_monitoreo: float | None = Field(None, gt=0)
    reglas: list[str] | None = None
    decimales: int = Field(2, ge=0, le=6)
    usuario: str | None = None


class PlanMuestreo(BaseModel):
    """Plan de muestreo a guardar. Solo se aplican los campos enviados."""

    n: int | None = Field(None, ge=1, le=10_000)
    frecuencia_min: int | None = Field(None, ge=1, le=24 * 60)
    k_sigma: float | None = Field(None, ge=1, le=6)
    sigma_monitoreo: float | None = Field(None, gt=0, description="σ fijada por el ingeniero")
    borrar_sigma: bool = Field(False, description="Volver a estimar σ con los datos")
    reiniciar_fase_i: bool = Field(False, description="Confirmar que las muestras de la Fase I con otro n pasan al archivo")
    usuario: str | None = None
    justificacion: str = Field(min_length=3)


class VariableActualizar(BaseModel):
    """Cambios de configuración. Solo se aplican los campos enviados."""

    nombre: str | None = None
    unidad: str | None = None
    tipo_carta: TipoCarta | None = None
    n: int | None = Field(None, ge=1, le=10_000)
    frecuencia_min: int | None = Field(None, ge=1)
    lei: float | None = None
    objetivo: float | None = None
    les: float | None = None
    k_sigma: float | None = Field(None, gt=0, le=6)
    estimador_sigma: Literal["rbar", "sbar", "mr"] | None = None
    sigma_monitoreo: float | None = Field(None, gt=0)
    reglas: list[str] | None = None
    decimales: int | None = Field(None, ge=0, le=6)
    usuario: str | None = None
    justificacion: str = Field(min_length=3, description="Motivo del cambio (obligatorio, queda en el historial)")
    # Para poder borrar un límite de especificación (dejarlo unilateral) hay que nombrarlo aquí.
    borrar: list[Literal["lei", "objetivo", "les", "sigma_monitoreo"]] = []


class SubgrupoCrear(BaseModel):
    """Registro de un subgrupo: `valores` (variables) o `conteo` + `tamano` (atributos)."""

    valores: list[float] | None = None
    conteo: float | None = Field(None, ge=0)
    tamano: float | None = Field(None, gt=0)
    timestamp: datetime | None = None
    operario: str | None = None
    lote: str | None = None
    comentario: str | None = None
    usuario: str | None = None


class DeshacerRegistro(BaseModel):
    usuario: str | None = None
    motivo: str | None = Field(None, description="Por qué se anula (p. ej. «escribí 5000 en vez de 500,0»)")


class ModoDemo(BaseModel):
    activo: bool


class SubgrupoExclusion(BaseModel):
    excluido: bool
    causa: str | None = None
    accion: str | None = None
    usuario: str | None = None


class AccionFase(BaseModel):
    usuario: str | None = None
    motivo: str | None = None
    usar_fase_ii_como_base: bool = False


class SimularExclusion(BaseModel):
    excluidos: list[int] = Field(default_factory=list, description="Números de subgrupo a excluir")


class AlarmaActualizar(BaseModel):
    estado: Literal["abierta", "en_investigacion", "resuelta"] | None = None
    causa: str | None = None
    accion: str | None = None
    usuario: str | None = None


class EventoManual(BaseModel):
    tipo: Literal["parada", "retencion", "anomalia"]
    descripcion: str = Field(min_length=3)
    usuario: str | None = None


class Turno(BaseModel):
    """Turno programado. Días como datetime.weekday() (0 = lunes); arranque = minutos hasta la primera
    muestra (vacío: un intervalo de muestreo después del inicio)."""

    nombre: str = Field(min_length=1, max_length=40)
    inicio: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    fin: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    dias: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    arranque_min: int | None = Field(None, ge=0, le=600)


class AccionTurno(BaseModel):
    nombre: str | None = Field(None, description="Turno programado a iniciar (por defecto el próximo)")
    usuario: str | None = None


class SimulacionARL(BaseModel):
    k: float = Field(3.0, gt=0)
    n: int = Field(5, ge=1, le=100)
    delta: float = Field(1.0, ge=0)
    replicas: int = Field(2000, ge=100, le=20_000)
    semilla: int | None = 12345


class DisenoPlan(BaseModel):
    aql: float = Field(gt=0, lt=1)
    ltpd: float = Field(gt=0, lt=1)
    alfa: float = Field(0.05, gt=0, lt=1)
    beta: float = Field(0.10, gt=0, lt=1)
    modelo: Literal["binomial", "hipergeometrica", "poisson"] = "binomial"
    N: int | None = Field(None, ge=2)


class LoteCrear(BaseModel):
    codigo: str = Field(min_length=1)
    descripcion: str | None = None
    N: int = Field(ge=1)
    n: int = Field(ge=1)
    c: int = Field(ge=0)
    defectos: int = Field(ge=0)
    usuario: str | None = None


class CartaAtributosAdHoc(BaseModel):
    tipo: Literal["p", "np", "c", "u"]
    conteos: list[float]
    tamanos: list[float] | float | None = None
    excluidos: list[int] = []
    k: float = 3.0
    reglas: list[str] | None = None
