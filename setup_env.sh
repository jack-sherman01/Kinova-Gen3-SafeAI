#!/usr/bin/env bash
# Create .venv with the Kortex Python API and workspace dependencies.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

WHEEL=kortex_api-2.6.0.post3-py3-none-any.whl
URL=https://artifactory.kinovaapps.com/artifactory/generic-public/kortex/API/2.6.0/$WHEEL

git submodule update --init
python3 -m venv .venv
mkdir -p wheels
[[ -f wheels/$WHEEL ]] || curl -fsSL -o "wheels/$WHEEL" "$URL"
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q "wheels/$WHEEL"
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -c "import kortex_api, pygame; print('Environment ready')"
