"""Modelos de la base de datos.

Proceso 1─* Variable 1─* Subgrupo 1─* Medicion
                    1─* LimitesCarta      (historial; uno activo cuando la variable está en Fase II)
                    1─* Alarma            (violaciones de reglas y eventos manuales)
                    1─* CambioConfiguracion (historial de auditoría)
LoteInspeccion   (muestreo de aceptación)
ReporteGenerado  (historial de reportes exportados)
Ajuste           (clave/valor global: turnos programados, etc.)
TurnoRegistro 1─* Subgrupo  (turnos reales: se abren y cierran solos según la programación o a mano)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .sesion import Base


def ahora() -> datetime:
    """Fecha y hora local sin zona (la app corre en una sola máquina)."""
    return datetime.now().replace(microsecond=0)


class Proceso(Base):
    __tablename__ = "procesos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    planta: Mapped[str | None] = mapped_column(String(120))
    linea: Mapped[str | None] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text)
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)

    variables: Mapped[list["Variable"]] = relationship(back_populates="proceso", cascade="all, delete-orphan",
                                                       order_by="Variable.id")


class Variable(Base):
    """Característica de calidad controlada y su configuración de CEP."""

    __tablename__ = "variables"

    id: Mapped[int] = mapped_column(primary_key=True)
    proceso_id: Mapped[int] = mapped_column(ForeignKey("procesos.id", ondelete="CASCADE"))
    nombre: Mapped[str] = mapped_column(String(120))
    unidad: Mapped[str] = mapped_column(String(30), default="")
    tipo_dato: Mapped[str] = mapped_column(String(12), default="variables")  # variables | atributos
    tipo_carta: Mapped[str] = mapped_column(String(10), default="xbar_r")  # xbar_r|xbar_s|imr|p|np|c|u
    n: Mapped[int] = mapped_column(Integer, default=5)  # tamaño de subgrupo (o de muestra en p/np)
    frecuencia_min: Mapped[int] = mapped_column(Integer, default=30)
    lei: Mapped[float | None] = mapped_column(Float)
    objetivo: Mapped[float | None] = mapped_column(Float)
    les: Mapped[float | None] = mapped_column(Float)
    k_sigma: Mapped[float] = mapped_column(Float, default=3.0)
    estimador_sigma: Mapped[str] = mapped_column(String(8), default="rbar")  # rbar | sbar | mr
    # σ fijada por el ingeniero (historial o norma de la empresa). None = se estima con los datos.
    sigma_monitoreo: Mapped[float | None] = mapped_column(Float, nullable=True)
    reglas: Mapped[list] = mapped_column(JSON, default=lambda: ["N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8"])
    fase: Mapped[str] = mapped_column(String(2), default="I")
    decimales: Mapped[int] = mapped_column(Integer, default=2)
    version: Mapped[int] = mapped_column(Integer, default=1)
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)

    proceso: Mapped[Proceso] = relationship(back_populates="variables")
    subgrupos: Mapped[list["Subgrupo"]] = relationship(back_populates="variable", cascade="all, delete-orphan",
                                                       order_by="Subgrupo.numero")
    limites: Mapped[list["LimitesCarta"]] = relationship(back_populates="variable", cascade="all, delete-orphan",
                                                         order_by="LimitesCarta.id")


class Subgrupo(Base):
    """Un subgrupo racional (variables) o una muestra con su conteo (atributos)."""

    __tablename__ = "subgrupos"
    __table_args__ = (UniqueConstraint("variable_id", "numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    variable_id: Mapped[int] = mapped_column(ForeignKey("variables.id", ondelete="CASCADE"), index=True)
    numero: Mapped[int] = mapped_column(Integer)  # correlativo por variable (1, 2, …)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    fase: Mapped[str] = mapped_column(String(8), default="I")  # I | II | archivo
    conteo: Mapped[float | None] = mapped_column(Float)  # defectuosos o defectos (atributos)
    tamano: Mapped[float | None] = mapped_column(Float)  # n de la muestra o unidades inspeccionadas
    operario: Mapped[str | None] = mapped_column(String(80))
    lote: Mapped[str | None] = mapped_column(String(80))
    origen: Mapped[str] = mapped_column(String(12), default="manual")  # manual | importado | semilla
    excluido: Mapped[bool] = mapped_column(Boolean, default=False)
    causa_exclusion: Mapped[str | None] = mapped_column(Text)
    accion_exclusion: Mapped[str | None] = mapped_column(Text)
    comentario: Mapped[str | None] = mapped_column(Text)
    # Turno real en que se tomó (None: fuera de turno o cargada sin turno, p. ej. datos históricos)
    turno_id: Mapped[int | None] = mapped_column(ForeignKey("turnos.id", ondelete="SET NULL"), index=True)
    turno: Mapped["TurnoRegistro | None"] = relationship()

    variable: Mapped[Variable] = relationship(back_populates="subgrupos")
    mediciones: Mapped[list["Medicion"]] = relationship(back_populates="subgrupo", cascade="all, delete-orphan",
                                                        order_by="Medicion.posicion", lazy="selectin")

    @property
    def valores(self) -> list[float]:
        return [m.valor for m in self.mediciones]


class Medicion(Base):
    __tablename__ = "mediciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    subgrupo_id: Mapped[int] = mapped_column(ForeignKey("subgrupos.id", ondelete="CASCADE"), index=True)
    posicion: Mapped[int] = mapped_column(Integer)
    valor: Mapped[float] = mapped_column(Float)

    subgrupo: Mapped[Subgrupo] = relationship(back_populates="mediciones")


class LimitesCarta(Base):
    """Límites estimados en Fase I y congelados para la Fase II (con historial)."""

    __tablename__ = "limites"

    id: Mapped[int] = mapped_column(primary_key=True)
    variable_id: Mapped[int] = mapped_column(ForeignKey("variables.id", ondelete="CASCADE"), index=True)
    tipo_carta: Mapped[str] = mapped_column(String(10))
    datos: Mapped[dict] = mapped_column(JSON)  # el diccionario `limites` del core
    m_usados: Mapped[int] = mapped_column(Integer, default=0)
    excluidos: Mapped[list] = mapped_column(JSON, default=list)  # números de subgrupo excluidos
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    usuario: Mapped[str | None] = mapped_column(String(80))
    motivo: Mapped[str | None] = mapped_column(Text)
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    archivado: Mapped[datetime | None] = mapped_column(DateTime)

    variable: Mapped[Variable] = relationship(back_populates="limites")


class Alarma(Base):
    """Violación de una regla (o evento manual) con su seguimiento causa/acción."""

    __tablename__ = "alarmas"
    __table_args__ = (UniqueConstraint("subgrupo_id", "regla", "carta"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    variable_id: Mapped[int] = mapped_column(ForeignKey("variables.id", ondelete="CASCADE"), index=True)
    subgrupo_id: Mapped[int | None] = mapped_column(ForeignKey("subgrupos.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(12), default="regla")  # regla | parada | retencion | anomalia
    regla: Mapped[str] = mapped_column(String(8))  # N1…N8, WE4 o MANUAL
    carta: Mapped[str] = mapped_column(String(8), default="")  # xbar, r, s, i, mr, p, …
    descripcion: Mapped[str] = mapped_column(Text)
    explicacion: Mapped[str | None] = mapped_column(Text, nullable=True)  # en palabras simples (Operario)
    severidad: Mapped[str] = mapped_column(String(12), default="advertencia")
    estado: Mapped[str] = mapped_column(String(16), default="abierta")  # abierta | en_investigacion | resuelta
    causa: Mapped[str | None] = mapped_column(Text)
    accion: Mapped[str | None] = mapped_column(Text)
    usuario: Mapped[str | None] = mapped_column(String(80))
    creada: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    actualizada: Mapped[datetime | None] = mapped_column(DateTime)
    cerrada: Mapped[datetime | None] = mapped_column(DateTime)

    subgrupo: Mapped[Subgrupo | None] = relationship()


class CambioConfiguracion(Base):
    """Registro de auditoría: qué parámetro cambió, de qué valor a cuál, quién y por qué."""

    __tablename__ = "cambios_configuracion"

    id: Mapped[int] = mapped_column(primary_key=True)
    variable_id: Mapped[int] = mapped_column(ForeignKey("variables.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    usuario: Mapped[str] = mapped_column(String(80))
    parametro: Mapped[str] = mapped_column(String(60))
    valor_anterior: Mapped[str | None] = mapped_column(Text)
    valor_nuevo: Mapped[str | None] = mapped_column(Text)
    justificacion: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    hash: Mapped[str] = mapped_column(String(64))  # SHA-256 de la configuración resultante


class LoteInspeccion(Base):
    """Lote evaluado con un plan de muestreo de aceptación simple."""

    __tablename__ = "lotes_inspeccion"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(80))
    descripcion: Mapped[str | None] = mapped_column(String(200))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    # SQLite no distingue mayúsculas en nombres de columna: N y n se guardan con nombres distintos.
    N: Mapped[int] = mapped_column("tamano_lote", Integer)
    n: Mapped[int] = mapped_column("tamano_muestra", Integer)
    c: Mapped[int] = mapped_column(Integer)
    defectos: Mapped[int] = mapped_column(Integer)
    p_hat: Mapped[float] = mapped_column(Float)
    dictamen: Mapped[str] = mapped_column(String(12))
    usuario: Mapped[str | None] = mapped_column(String(80))


class ReporteGenerado(Base):
    __tablename__ = "reportes"

    id: Mapped[int] = mapped_column(primary_key=True)
    variable_id: Mapped[int | None] = mapped_column(ForeignKey("variables.id", ondelete="SET NULL"))
    nombre_archivo: Mapped[str] = mapped_column(String(200))
    plantilla: Mapped[str] = mapped_column(String(40))
    formato: Mapped[str] = mapped_column(String(8))
    tamano_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    ruta: Mapped[str] = mapped_column(Text)
    usuario: Mapped[str | None] = mapped_column(String(80))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Ajuste(Base):
    """Ajustes globales clave → valor JSON (por ejemplo los turnos)."""

    __tablename__ = "ajustes"

    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[dict | list] = mapped_column(JSON)


class TurnoRegistro(Base):
    """Turno real: se abre al llegar la hora de un turno programado (o a mano) y se cierra a su hora de
    fin (o antes, a mano). Las muestras registradas mientras está abierto quedan asociadas a él."""

    __tablename__ = "turnos"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(Integer)  # consecutivo: Turno #1, #2, …
    nombre: Mapped[str] = mapped_column(String(80))  # nombre del turno programado (Mañana, Tarde…)
    inicio_programado: Mapped[datetime] = mapped_column(DateTime, index=True)
    fin_programado: Mapped[datetime] = mapped_column(DateTime)
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fin: Mapped[datetime | None] = mapped_column(DateTime)  # None mientras está abierto
    cierre: Mapped[str | None] = mapped_column(String(10))  # hora | manual
    arranque_min: Mapped[int | None] = mapped_column(Integer)
    abierto_por: Mapped[str | None] = mapped_column(String(80))
    cerrado_por: Mapped[str | None] = mapped_column(String(80))
