#!/bin/bash

set -e

URL="https://files.pythonhosted.org/packages/source/n/numpy/numpy-1.26.4.tar.gz"

wget $URL
tar -xf numpy-1.26.4.tar.gz
cd numpy-1.26.4

MESON_CROSS_FILE=$(pyodide config get meson_cross_file)
pyodide build -Csetup-args=-Dallow-noblas=true -Csetup-args=--cross-file="${MESON_CROSS_FILE}"
