"""Respaldos de la base de datos SQLite (una sola base para todos los procesos).

Los respaldos se guardan en `<carpeta de la base>/respaldos/cep_AAAAMMDD_HHMMSS_<motivo>.db` y se
hacen con la API de respaldo de SQLite (copia consistente aunque la app esté en uso). Se conservan
los últimos `MAXIMO` respaldos.

Restaurar copia el respaldo **dentro** de la base en uso (sin reemplazar el archivo), después de
guardar un respaldo «antes_de_restaurar», y aplica las migraciones por si el respaldo es de una
versión anterior.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from . import sesion

MAXIMO = 20
PATRON = re.compile(r"^cep_\d{8}_\d{6}(_[a-z_]+)?\.db$")
TABLAS_REQUERIDAS = {"procesos", "variables", "subgrupos", "mediciones"}


class ErrorRespaldo(ValueError):
    """Archivo inválido o respaldo inexistente."""


def ruta_base() -> Path:
    bd = sesion.engine.url.database
    if not bd or bd == ":memory:":
        raise ErrorRespaldo("La base de datos no está en un archivo.")
    return Path(bd)


def carpeta() -> Path:
    c = ruta_base().parent / "respaldos"
    c.mkdir(parents=True, exist_ok=True)
    return c


def _copiar(origen: Path, destino: Path) -> None:
    """Copia consistente de una base SQLite a otra con la API de respaldo.

    `closing`: el `with` de sqlite3 solo confirma la transacción; sin cerrar, Windows deja el
    archivo bloqueado y no se puede borrar ni reemplazar.
    """
    with closing(sqlite3.connect(origen)) as src, closing(sqlite3.connect(destino)) as dst:
        src.backup(dst)


def crear(motivo: str = "manual") -> dict:
    """Guarda un respaldo de la base actual y borra los más antiguos que excedan MAXIMO."""
    base = ruta_base()
    if not base.exists():
        raise ErrorRespaldo("Todavía no hay base de datos para respaldar.")
    motivo = re.sub(r"[^a-z_]", "", motivo.lower().replace(" ", "_"))[:30] or "manual"
    nombre = f"cep_{datetime.now():%Y%m%d_%H%M%S}_{motivo}.db"
    destino = carpeta() / nombre
    _copiar(base, destino)
    for viejo in listar()[MAXIMO:]:
        (carpeta() / viejo["nombre"]).unlink(missing_ok=True)
    return _info(destino)


def _info(ruta: Path) -> dict:
    m = re.match(r"^cep_(\d{8})_(\d{6})(?:_([a-z_]+))?\.db$", ruta.name)
    fecha = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S") if m else None
    motivos = {"inicio": "Al abrir la aplicación", "manual": "Hecho a mano", "antes_de_restaurar": "Antes de restaurar"}
    motivo = (m.group(3) if m else None) or "manual"
    return {"nombre": ruta.name, "fecha": fecha.isoformat() if fecha else None, "tamano_bytes": ruta.stat().st_size,
            "motivo": motivos.get(motivo, motivo.replace("_", " ").capitalize())}


def listar() -> list[dict]:
    """Respaldos disponibles, del más reciente al más antiguo."""
    archivos = [p for p in carpeta().glob("cep_*.db") if PATRON.match(p.name)]
    return [_info(p) for p in sorted(archivos, key=lambda p: p.name, reverse=True)]


def ruta_respaldo(nombre: str) -> Path:
    """Ruta de un respaldo por nombre (valida el nombre para no salir de la carpeta)."""
    if not PATRON.match(nombre):
        raise ErrorRespaldo("Nombre de respaldo no válido.")
    ruta = carpeta() / nombre
    if not ruta.exists():
        raise ErrorRespaldo("El respaldo ya no existe.")
    return ruta


def validar(ruta: Path) -> dict:
    """Comprueba que el archivo sea una base de CEP y devuelve cuántos procesos/variables/muestras trae."""
    try:
        with closing(sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True)) as con:
            tablas = {f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not TABLAS_REQUERIDAS <= tablas:
                raise ErrorRespaldo("El archivo no es una base de datos de CEP.")
            return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("procesos", "variables", "subgrupos")}
    except sqlite3.DatabaseError as e:
        raise ErrorRespaldo("El archivo no es una base de datos válida (.db de CEP).") from e


def restaurar(origen: Path) -> dict:
    """Reemplaza el contenido de la base actual por el de `origen` (guardando antes un respaldo)."""
    conteos = validar(origen)
    previo = crear("antes_de_restaurar") if ruta_base().exists() else None
    sesion.engine.dispose()  # cierra las conexiones abiertas antes de copiar
    _copiar(origen, ruta_base())
    sesion.engine.dispose()
    sesion.crear_tablas()  # migraciones si el respaldo es de una versión anterior
    return {"restaurado": origen.name, "respaldo_previo": previo["nombre"] if previo else None, **conteos}
