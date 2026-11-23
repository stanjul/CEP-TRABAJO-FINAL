"""Programa de escritorio: base vacía sin demostración, respaldos, restauración y copia de la base."""
import pytest
from fastapi.testclient import TestClient

from app.db import sesion


@pytest.fixture
def c(tmp_path, monkeypatch):
    sesion.configurar(f"sqlite:///{(tmp_path / 'cep.db').as_posix()}")
    from app.main import app

    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def vacia(tmp_path, monkeypatch):
    """Como el programa de escritorio: la base arranca sin datos de demostración."""
    monkeypatch.setenv("CEP_SIN_DEMO", "1")
    monkeypatch.setenv("CEP_MODO", "escritorio")
    sesion.configurar(f"sqlite:///{(tmp_path / 'cep.db').as_posix()}")
    from app.main import app

    with TestClient(app) as cliente:
        yield cliente


def test_escritorio_arranca_vacio_y_carga_demo(vacia):
    info = vacia.get("/api/sistema/info").json()
    assert info["modo"] == "escritorio" and info["procesos"] == 0 and info["puede_abrir_carpeta"] in (True, False)
    assert vacia.post("/api/sistema/demo").status_code == 201
    assert vacia.get("/api/sistema/info").json()["variables"] == 6
    assert vacia.post("/api/sistema/demo").status_code == 409  # solo con la base vacía


def test_respaldar_y_restaurar(c, tmp_path):
    r = c.post("/api/sistema/respaldos", json={"motivo": "manual"}).json()
    assert r["nombre"].startswith("cep_") and r["motivo"] == "Hecho a mano"
    assert (tmp_path / "respaldos" / r["nombre"]).exists()
    # Se registra una muestra y se vuelve al respaldo: la muestra desaparece.
    c.post("/api/variables/1/subgrupos", json={"valores": [500.0] * 5})
    assert len(c.get("/api/variables/1/carta").json()["subgrupos"]) == 1
    rest = c.post(f"/api/sistema/respaldos/{r['nombre']}/restaurar").json()
    assert rest["respaldo_previo"].endswith("_antes_de_restaurar.db") and rest["variables"] == 6
    assert c.get("/api/variables/1/carta").json()["subgrupos"] == []
    nombres = [x["nombre"] for x in c.get("/api/sistema/info").json()["respaldos"]]
    assert r["nombre"] in nombres and rest["respaldo_previo"] in nombres


def test_nombres_de_respaldo_seguros(c):
    assert c.post("/api/sistema/respaldos/..%2Fcep.db/restaurar").status_code in (404, 422)
    assert c.post("/api/sistema/respaldos/cep_20260101_000000_manual.db/restaurar").status_code == 422  # no existe
    assert c.get("/api/sistema/respaldos/otro.db/descargar").status_code == 404


def test_descargar_copia_y_restaurar_desde_archivo(c):
    copia = c.get("/api/sistema/base/descargar")
    assert copia.status_code == 200 and copia.content[:16] == b"SQLite format 3\x00"
    c.post("/api/procesos", json={"nombre": "Proceso temporal"})
    r = c.post("/api/sistema/base/restaurar", files={"archivo": ("CEP_base.db", copia.content, "application/octet-stream")})
    assert r.status_code == 200 and r.json()["restaurado"] == "CEP_base.db"
    assert "Proceso temporal" not in [p["nombre"] for p in c.get("/api/procesos").json()]


def test_restaurar_rechaza_archivos_ajenos(c):
    r = c.post("/api/sistema/base/restaurar", files={"archivo": ("x.db", b"no es sqlite", "application/octet-stream")})
    assert r.status_code == 422 and "no es una base de datos" in r.json()["detail"]


def test_limite_de_respaldos(c, monkeypatch):
    from app.db import respaldos
    monkeypatch.setattr(respaldos, "MAXIMO", 3)
    import time
    for _ in range(5):
        respaldos.crear("manual")
        time.sleep(1.05)  # el nombre lleva segundos: así no se pisan
    assert len(respaldos.listar()) == 3


def test_carpeta_de_datos(monkeypatch, tmp_path):
    from app import escritorio
    monkeypatch.setenv("CEP_DATOS", str(tmp_path / "datos"))
    assert escritorio.carpeta_datos() == tmp_path / "datos"
    monkeypatch.delenv("CEP_DATOS")
    # Fuera de Documentos (que suele estar en OneDrive): C:\Users\<usuario>\CEP
    from pathlib import Path
    assert escritorio.carpeta_datos() == Path.home() / "CEP"


def test_migracion_desde_documentos(tmp_path):
    from app import escritorio
    vieja, nueva = tmp_path / "Documentos" / "CEP", tmp_path / "CEP"
    (vieja / "respaldos").mkdir(parents=True)
    (vieja / "cep.db").write_bytes(b"base")
    (vieja / "respaldos" / "cep_20261123_100000_inicio.db").write_bytes(b"r")
    assert escritorio.migrar_datos_anteriores(nueva, vieja)
    assert (nueva / "cep.db").read_bytes() == b"base" and (nueva / "respaldos" / "cep_20261123_100000_inicio.db").exists()
    assert (vieja / "cep.db").exists() and "se movieron a" in (vieja / "LEEME - datos movidos.txt").read_text(encoding="utf-8")
    # Si la carpeta nueva ya tiene base, no se vuelve a copiar (no pisa datos nuevos).
    (vieja / "cep.db").write_bytes(b"otra")
    assert not escritorio.migrar_datos_anteriores(nueva, vieja)
    assert (nueva / "cep.db").read_bytes() == b"base"
