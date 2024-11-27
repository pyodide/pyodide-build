#!/bin/bash

set -e

URL="https://files.pythonhosted.org/packages/65/6e/09db70a523a96d25e115e71cc56a6f9031e7b8cd166c1ac8438307c14058/numpy-1.26.4.tar.gz"

wget $URL
tar -xvf numpy-1.26.4.tar.gz
cd numpy-1.26.4

pyodide build