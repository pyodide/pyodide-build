#!/bin/bash

set -e

URL="https://files.pythonhosted.org/packages/65/6e/09db70a523a96d25e115e71cc56a6f9031e7b8cd166c1ac8438307c14058/numpy-1.26.4.tar.gz"

wget $URL
tar -xf numpy-1.26.4.tar.gz
cd numpy-1.26.4

MESON_CROSS_FILE=`pyodide config get meson_cross_file`
pyodide build -Csetup-args=-Dallow-noblas=true -Csetup-args=--cross-file=${MESON_CROSS_FILE}
