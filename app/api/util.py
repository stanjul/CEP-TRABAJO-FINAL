"""Utilidades comunes de la API."""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any

import numpy as np
from fastapi.responses import JSONResponse


def limpiar_json(obj: Any) -> Any:
    """Convierte recursivamente a tipos JSON estándar.

    - NaN / ±inf → None (JSON no los admite).
    - Tipos numpy → tipos de Python.
    - datetime → texto ISO 8601.
    """
    if isinstance(obj, dict):
        return {str(k): limpiar_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [limpiar_json(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [limpiar_json(v) for v in obj.tolist()]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


class JSONSeguro(JSONResponse):
    """JSONResponse que limpia NaN, inf y tipos numpy antes de serializar."""

    def render(self, content: Any) -> bytes:
        return json.dumps(limpiar_json(content), ensure_ascii=False, allow_nan=False).encode("utf-8")


def usuario_o_anonimo(usuario: str | None) -> str:
    """Nombre del usuario que firma la acción (no hay login: lo envía la interfaz)."""
    return (usuario or "").strip() or "Anónimo"
