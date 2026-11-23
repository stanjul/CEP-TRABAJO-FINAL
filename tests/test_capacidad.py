"""Índices de capacidad (Montgomery, cap. 6 y 8)."""
import numpy as np
import pytest

from app.core import capacidad as cap
from tests.datos_montgomery import ANILLOS


def test_cp_anillos_libro():
    """Anillos con especificación 74.000 ± 0.05 y σ̂ = 0.0099 ⇒ Cp = 1.68 (libro)."""
    assert cap.indices(74.001, 0.0099, 73.95, 74.05)["cp"] == pytest.approx(1.68, abs=5e-3)


def test_cp_anillos_desde_datos():
    """Con R̄ sin redondear (0.02324) se obtiene Cp ≈ 1.67; el libro redondea σ̂ a 0.0099."""
    res = cap.analizar_capacidad(ANILLOS, 73.95, 74.05, 74.0)
    assert res["sigma_dentro"] == pytest.approx(0.0099, abs=1e-4)
    assert res["indices"]["cp"] == pytest.approx(1.68, abs=0.015)
    assert res["veredicto"]["nivel"] == "capaz"


def test_cpk_descentrado():
    """μ = 53, σ = 2, LEI = 38, LES = 62: Cp = 2.0, Cpu = 1.5, Cpl = 2.5, Cpk = 1.5 (Montgomery cap. 8)."""
    r = cap.indices(53, 2, 38, 62)
    assert r["cp"] == pytest.approx(2.0)
    assert r["cpu"] == pytest.approx(1.5)
    assert r["cpl"] == pytest.approx(2.5)
    assert r["cpk"] == pytest.approx(1.5)


def test_unilateral():
    """Resistencia de botellas: LEI = 200, x̄ = 264.06, s = 32.02 ⇒ Cpl = 0.67 (Montgomery cap. 8)."""
    r = cap.indices(264.06, 32.02, lei=200)
    assert r["cp"] is None
    assert r["cpl"] == pytest.approx(0.67, abs=5e-3)
    assert r["cpk"] == r["cpl"]


def test_ppm_cpk_1():
    """Proceso centrado con Cp = 1 ⇒ 2700 ppm (0.27 %)."""
    f = cap.fraccion_no_conforme(0, 1, -3, 3)
    assert f["ppm"] == pytest.approx(2699.8, abs=0.5)


def test_veredictos():
    assert cap.veredicto(1.5)["nivel"] == "capaz"
    assert cap.veredicto(1.1)["nivel"] == "marginal"
    assert cap.veredicto(0.8)["nivel"] == "no_capaz"


def test_sin_indices_de_desempeno():
    """Alcance del curso: solo Cp, Cpk, Cpu y Cpl (no se calculan Pp ni Ppk)."""
    r = cap.analizar_capacidad(ANILLOS, 73.95, 74.05, 74.0)
    assert set(r["indices"]) == {"cp", "cpk", "cpu", "cpl"}
    assert not any("pp" in clave.lower() and clave != "ppm_esperado" for clave in r)
    assert "largo_plazo" not in r
    # s de todos los datos queda solo como dato descriptivo.
    assert r["desviacion_estandar"] == pytest.approx(np.std(np.concatenate(ANILLOS), ddof=1))


def test_sigma_fijada_por_el_ingeniero():
    """Con σ fijada, Cp = (LES − LEI)/6σ usa esa σ y no la estimada con R̄/d2."""
    r = cap.analizar_capacidad(ANILLOS, 73.95, 74.05, 74.0, sigma=0.01)
    assert r["metodo_sigma"] == "fijada"
    assert r["indices"]["cp"] == pytest.approx(0.10 / 0.06)
    with pytest.raises(ValueError):
        cap.analizar_capacidad(ANILLOS, 73.95, 74.05, sigma=0)


def test_observados_por_lado():
    grupos = [[1.0, 5.0, 9.5], [5.0, 0.5, 5.0]]
    r = cap.analizar_capacidad(grupos, 2, 9, metodo="sbar")
    assert r["observado"] == {"fuera": 3, "bajo_lei": 2, "sobre_les": 1, "ppm": pytest.approx(5e5)}


def test_advertencia_fuera_de_control():
    r = cap.analizar_capacidad(ANILLOS, 73.95, 74.05, en_control=False)
    assert r["advertencias"]
    assert not cap.analizar_capacidad(ANILLOS, 73.95, 74.05, en_control=True)["advertencias"]


def test_sigma_dentro_metodos():
    s_r = cap.sigma_dentro(ANILLOS, "rbar")
    s_s = cap.sigma_dentro(ANILLOS, "sbar")
    assert s_r == pytest.approx(s_s, rel=0.05)
    with pytest.raises(ValueError):
        cap.sigma_dentro(ANILLOS, "xx")


def test_sin_especificaciones_falla():
    with pytest.raises(ValueError):
        cap.indices(0, 1)
