#!/bin/bash

set -e

NO_ISOLATION=""
SKIP_DEPS=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --no-isolation) NO_ISOLATION="--no-isolation"; shift ;;
        --skip-dependency-check) SKIP_DEPS="--skip-dependency-check"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
done

VERSION="2.0.2"
URL="https://files.pythonhosted.org/packages/source/n/numpy/numpy-${VERSION}.tar.gz"

wget $URL
tar -xf numpy-${VERSION}.tar.gz
cd numpy-${VERSION}

MESON_CROSS_FILE=$(pyodide config get meson_cross_file)
${UV_RUN_PREFIX} pyodide build -Csetup-args=-Dallow-noblas=true -Csetup-args=--cross-file="${MESON_CROSS_FILE}" $NO_ISOLATION $SKIP_DEPS
