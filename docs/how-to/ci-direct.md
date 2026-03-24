# CI without cibuildwheel

If you don't use [cibuildwheel](cibuildwheel.md), you can set up GitHub Actions (or any CI) to build Pyodide wheels directly with `pyodide build`.

## GitHub Actions workflow

```yaml
# .github/workflows/pyodide.yml
name: Build Pyodide wheel

on:
  push:
    tags: ["v*"]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - uses: actions/setup-node@v4
        with:
          node-version: "24"

      - name: Install pyodide-build
        run: pip install pyodide-build

      - name: Build wheel
        run: pyodide build .

      - name: Test wheel
        run: |
          pyodide venv .venv-pyodide
          source .venv-pyodide/bin/activate
          pip install dist/*.whl
          pip install pytest
          python -m pytest tests/ -x

      - uses: actions/upload-artifact@v4
        with:
          name: pyodide-wheel
          path: dist/*.whl
```

## Caching the cross-build environment

The cross-build environment and Emscripten SDK are downloaded on first use and can be large. Cache them to speed up subsequent runs:

```yaml
      - name: Cache xbuildenv
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/pyodide
            ~/.cache/emsdk
          key: pyodide-xbuildenv-${{ hashFiles('**/pyproject.toml') }}
          restore-keys: |
            pyodide-xbuildenv-
```

Place this step before the "Build wheel" step.

## Passing build options

Pass options the same way you would locally:

```yaml
      # Meson project
      - name: Build wheel
        run: pyodide build . -Csetup-args=-Dsome-option=value

      # Custom export mode
      - name: Build wheel
        run: pyodide build . --exports pyinit
```

## Publishing

Add a publish job that runs on tags:

```yaml
  publish:
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: pyodide-wheel
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

## What's next?

- [Publishing Wasm Wheels](publishing.md) — more details on distribution
- [CI with cibuildwheel](cibuildwheel.md) — if you also build native wheels
