#!/usr/bin/env bash
# Instala buscaclientes en una Mac, un Linux o una VPS. No necesita root ni toca el Python del sistema.
#   ./instalar.sh
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
if ! command -v "$PY" >/dev/null; then
  echo "Falta Python 3.10 o más nuevo (python3)."; exit 1
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "Necesitás Python 3.10 o más nuevo. Tenés: $("$PY" --version)"; exit 1; }

if "$PY" -m venv .venv >/dev/null 2>&1; then
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -r requirements.txt
  echo "Entorno creado en .venv"
else
  # Ubuntu/Debian sin python3-venv: las librerías van a ./lib, sin instalar nada en el sistema
  rm -rf .venv
  "$PY" -m pip install -q --target ./lib -r requirements.txt
  echo "Librerías instaladas en ./lib (no había python3-venv)"
fi

[ -f .env ] || { cp .env.example .env; chmod 600 .env; echo "Creado .env: completá APIFY_TOKEN"; }
chmod +x clientes
./clientes --help >/dev/null && echo "Listo. Probá: ./clientes nuevo mi-negocio"
echo "Para usarlo desde cualquier carpeta: ln -s \"$PWD/clientes\" ~/.local/bin/clientes"
