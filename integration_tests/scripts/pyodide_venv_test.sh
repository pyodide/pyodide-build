#!/bin/bash
set -ex

rm -rf test-cmdline-runner
mkdir test-cmdline-runner
cd test-cmdline-runner || exit

python -m venv .venv-host
# shellcheck source=/dev/null
source .venv-host/bin/activate

pyodide venv .venv-pyodide
# shellcheck source=/dev/null
source .venv-pyodide/bin/activate

git clone https://github.com/python-attrs/attrs --depth 1 --branch 25.3.0
cd attrs || exit
pip install ".[tests]"
# mypy_plugins uses pty and stuff that isn't supported on Emscripten.
../.venv-pyodide/bin/pip uninstall pytest-mypy-plugins -y
python -m pytest -k 'not mypy'
