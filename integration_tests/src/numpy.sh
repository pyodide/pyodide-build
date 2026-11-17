#!/bin/bash

set -e

# Keep in sync with the version in integration_tests/src/numpy_no_isolation.sh
VERSION="2.2.5"
URL="https://files.pythonhosted.org/packages/source/n/numpy/numpy-${VERSION}.tar.gz"

wget $URL
tar -xf numpy-${VERSION}.tar.gz
cd numpy-${VERSION}

# A pkg-config file for a host Python
#
# This is used as a regression test for https://github.com/pyodide/pyodide-build/pull/449.
# We should use the pkg-config file from the xbuildenv (which either is available in it
# or is retroactively added) and not this one below.
# See also:
# - https://github.com/pypa/cibuildwheel/issues/2950
# - https://github.com/pypa/cibuildwheel/issues/2566
PYTHON_VERSION=$(pyodide config get python_version | cut -d. -f1,2)
HOST_PKGCONFIG_DIR=$(mktemp -d)
cat > "${HOST_PKGCONFIG_DIR}/python-${PYTHON_VERSION}.pc" << EOF
Name: Python
Description: A host Python
Version: ${PYTHON_VERSION}
Cflags: -I${HOST_PKGCONFIG_DIR}/include/python${PYTHON_VERSION}
EOF
export PKG_CONFIG_PATH="${HOST_PKGCONFIG_DIR}${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"

MESON_CROSS_FILE=$(pyodide config get meson_cross_file)
${UV_RUN_PREFIX} pyodide build -vv -Csetup-args=-Dallow-noblas=true -Csetup-args=--cross-file="${MESON_CROSS_FILE}"
