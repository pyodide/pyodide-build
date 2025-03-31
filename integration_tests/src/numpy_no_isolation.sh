#!/bin/bash

# The same as "numpy.sh", but without the isolation.

set -e

VERSION="2.0.2"
URL="https://files.pythonhosted.org/packages/source/n/numpy/numpy-${VERSION}.tar.gz"

wget $URL
tar -xf numpy-${VERSION}.tar.gz
cd numpy-${VERSION}

MESON_CROSS_FILE=$(pyodide config get meson_cross_file)

# Build in a persistent build directory
${UV_RUN_PREFIX} pyodide build \
    -Csetup-args=-Dallow-noblas=true \
    -Csetup-args=--cross-file="${MESON_CROSS_FILE}" \
    -Cinstall-args=--tags=runtime,python-runtime,devel \
    -Cbuild-dir="build" \
    --no-isolation --skip-dependency-check

sed -i 's/numpy/numpy-tests/g' pyproject.toml

${UV_RUN_PREFIX} pyodide build \
    -Csetup-args=-Dallow-noblas=true \
    -Csetup-args=--cross-file="${MESON_CROSS_FILE}" \
    -Cinstall-args=--tags=tests \
    -Cbuild-dir="build" \
    --no-isolation --skip-dependency-check

echo "Successfully built wheels for numpy-${VERSION} and numpy-tests-${VERSION}."
