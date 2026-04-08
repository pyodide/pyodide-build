# CI with cibuildwheel

[cibuildwheel](https://cibuildwheel.pypa.io/) automates building Python wheels for multiple platforms in CI. Since v2.19.0, it supports Pyodide as a build target — meaning you can build native wheels for Linux, macOS, **and** WebAssembly wheels for Pyodide in the same CI pipeline.

## Minimal configuration

Add Pyodide to your `pyproject.toml`:

```toml
[tool.cibuildwheel]
# Build for CPython 3.13 on all platforms
build = "cp313-*"

[tool.cibuildwheel.pyodide]
# Test inside a Pyodide venv
test-requires = ["pytest"]
test-command = "python -m pytest {project}/tests -x"
```

```{important}
- Use `python -m pytest`, not bare `pytest` — CLI entry points may not work in the Pyodide venv.
```

## GitHub Actions workflow

Pyodide builds must run as a **separate job** with `CIBW_PLATFORM=pyodide` — cibuildwheel won't auto-detect the Pyodide platform.

```yaml
# .github/workflows/wheels.yml
name: Build wheels

on:
  push:
    tags: ["v*"]
  pull_request:

jobs:
  build-native:
    name: Build wheels on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
    steps:
      - uses: actions/checkout@v4
      - uses: pypa/cibuildwheel@v3.4.0
      - uses: actions/upload-artifact@v4
        with:
          name: wheels-${{ matrix.os }}
          path: wheelhouse/*.whl

  build-pyodide:
    name: Build Pyodide wheels
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: pypa/cibuildwheel@v3.4.0
        env:
          CIBW_PLATFORM: pyodide
      - uses: actions/upload-artifact@v7
        with:
          name: wheels-pyodide
          path: wheelhouse/*.whl
```

## Key constraints

| Constraint | Details |
|---|---|
| **Explicit platform** | Must set `CIBW_PLATFORM=pyodide` — auto-detection won't select Pyodide |
| **Wheel repair** | No default repair command — set `repair-wheel-command = ""` if needed |

## Publishing the wheels

Combine native and Pyodide wheels in a single publish step:

```yaml
  publish:
    needs: [build-native, build-pyodide]
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')
    permissions:
      id-token: write  # trusted publishing
    steps:
      - uses: actions/download-artifact@v4
        with:
          pattern: wheels-*
          merge-multiple: true
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

## Real-world examples

These projects use cibuildwheel with Pyodide:

- **NumPy** — [cibuildwheel config](https://github.com/numpy/numpy/blob/main/pyproject.toml)
- **pandas** — [CI workflow](https://github.com/pandas-dev/pandas/blob/main/.github/workflows/wheels.yml)

## Further reading

- [cibuildwheel documentation — Pyodide platform](https://cibuildwheel.pypa.io/en/stable/options/#platform)

## What's next?

- [CI without cibuildwheel](ci-direct.md) — set up GitHub Actions with `pyodide build` directly
- [Publishing Wasm Wheels](publishing.md) — distribute your wheels to PyPI
