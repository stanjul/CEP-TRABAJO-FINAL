#!/usr/bin/env bash
# ============================================================
#  CEP - Control Estadístico de Procesos
#  Arranque con un solo comando (Linux / macOS): ./run.sh
# ============================================================
set -e
cd "$(dirname "$0")"

PY=python3
command -v $PY >/dev/null 2>&1 || PY=python

if [ ! -x ".venv/bin/python" ]; then
    echo "[1/3] Creando entorno virtual .venv ..."
    $PY -m venv .venv
fi

if ! cmp -s requirements.txt .venv/requirements.instalado; then
    echo "[2/3] Instalando dependencias ..."
    .venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt --retries 10 --timeout 60
    cp requirements.txt .venv/requirements.instalado
fi

echo "[3/3] Iniciando servidor ..."
exec .venv/bin/python -m app.iniciar "$@"
