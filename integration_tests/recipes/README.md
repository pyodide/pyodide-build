This directory contains a few curated recipes to test the build process of pyodide-build.

### List of recipes and their purpose

- numpy: The most popular and widely used library in the scientific computing community.
- orjson: Tests rust extension modules.
- zlib: Tests static libraries.
- geos: Tests shared libraries.
- pydoc_data: Unvendored cpython module
- boost-histogram: Tests scikit-build-core and cmake build system.

### For maintainers

- Do not put too many recipes in this directory. It is meant to be a small collection of recipes that are representative of the build process.
- The recipes in this directory is originally copied from `pyodide/pyodide`. It does not need to be updated frequently unless there is a change in the build process.
