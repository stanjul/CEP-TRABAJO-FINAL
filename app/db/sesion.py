"""Motor y sesiones de SQLAlchemy.

Por defecto la base es `data/cep.db` (SQLite). Se puede cambiar con la variable de entorno
`CEP_DB_URL` o llamando a `configurar(url)` (lo usan los tests con una base temporal).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

RAIZ = Path(__file__).resolve().parents[2]
DIR_DATOS = RAIZ / "data"
URL_POR_DEFECTO = f"sqlite:///{(DIR_DATOS / 'cep.db').as_posix()}"


class Base(DeclarativeBase):
    """Clase base de todos los modelos."""


engine: Engine
SesionLocal: sessionmaker[Session]


def configurar(url: str | None = None) -> None:
    """(Re)crea el motor y la fábrica de sesiones para la URL indicada."""
    global engine, SesionLocal
    url = url or os.environ.get("CEP_DB_URL") or URL_POR_DEFECTO
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _activar_fk(conexion, _):  # SQLite no aplica claves foráneas si no se activa
            cur = conexion.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    SesionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def crear_tablas() -> None:
    """Crea las tablas que no existan."""
    from . import modelos  # noqa: F401  (registra los modelos en Base.metadata)

    Base.metadata.create_all(engine)
    migrar_columnas()


# Columnas agregadas después de la primera versión: (tabla, columna, tipo SQL).
COLUMNAS_NUEVAS = [
    ("variables", "sigma_monitoreo", "FLOAT"),
    ("alarmas", "explicacion", "TEXT"),
    ("subgrupos", "turno_id", "INTEGER"),
]


def migrar_columnas() -> None:
    """Agrega a una base existente las columnas nuevas que `create_all` no crea
    (create_all solo crea tablas que faltan, no columnas)."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as con:
        for tabla, columna, tipo in COLUMNAS_NUEVAS:
            if tabla in insp.get_table_names() and columna not in {c["name"] for c in insp.get_columns(tabla)}:
                con.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}"))


def obtener_sesion() -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesión por petición y la cierra al terminar."""
    sesion = SesionLocal()
    try:
        yield sesion
    finally:
        sesion.close()


configurar()
