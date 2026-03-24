# Quick Start

This guide walks you through building a Python package with C extensions for WebAssembly using pyodide-build.

```{note}
**Pure-Python packages do not need pyodide-build.** If your package has no C, C++, or Rust extensions, a standard wheel built with `python -m build` already works with Pyodide.
```

## Build from your source tree

If you have a package with compiled extensions locally, build it the same way you would with `python -m build`:

```bash
pyodide build .
```

The output wheel is placed in `./dist/` by default:

```
dist/your_package-1.0.0-cp313-cp313-pyemscripten_2025_0_wasm32.whl
```

On the first run, pyodide-build automatically downloads and sets up the cross-build environment and Emscripten SDK. This may take a minute — subsequent builds are fast.

You can specify a different output directory with `--outdir` / `-o`:

```bash
pyodide build . -o wheelhouse/
```

## Passing options to the build backend

Use `-C` / `--config-setting` to pass options to your build backend, just like with `python -m build`:

```bash
# Meson project: pass the cross-compilation file
pyodide build . -C setup-args=-Dblas=none -C setup-args=-Dlapack=none

# setuptools project: pass extra compile args
pyodide build . -C "--build-option=--some-flag"
```

## Verify the wheel

You can inspect the built wheel to confirm it has the correct platform tag:

```bash
unzip -l dist/your_package-*.whl | head -20
```

The wheel should contain `.so` files (compiled extensions) alongside your Python source, and the filename should include the `pyemscripten_*_wasm32` platform tag.

## Test the wheel

Create a [Pyodide virtual environment](testing.md) to test the wheel:

```bash
pyodide venv .venv-pyodide
source .venv-pyodide/bin/activate
pip install dist/your_package-*.whl
python -c "import your_package; print('it works!')"
```

See [Testing with `pyodide venv`](testing.md) for a full walkthrough.

## What's next?

- [Testing with `pyodide venv`](testing.md) — verify your wheel in a Pyodide environment
- [CI with cibuildwheel](../how-to/cibuildwheel.md) — automate Pyodide builds in CI
- [Tutorial: Meson Package](../tutorials/meson.md) — building packages with Meson
- [Tutorial: CMake Package](../tutorials/cmake.md) — building packages with CMake
- [Tutorial: Rust Package](../tutorials/rust.md) — building packages with Rust/PyO3 extensions
