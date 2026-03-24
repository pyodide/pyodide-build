# Testing with `pyodide venv`

After building a WebAssembly wheel, you'll want to verify it actually works. `pyodide venv` creates a virtual environment where `python` runs on [Pyodide](https://pyodide.org/) via Node.js, so you can test your package in a real WebAssembly runtime without opening a browser.

## Create a Pyodide virtual environment

```bash
pyodide venv .venv-pyodide
```

This creates a virtual environment at `.venv-pyodide/`. Under the hood, it:

1. Creates a virtualenv using the Pyodide interpreter (which runs on Node.js)
2. Configures `pip` to only accept WebAssembly-compatible wheels
3. Installs the Pyodide standard library and [micropip](https://micropip.pyodide.org/)

## Activate and install your wheel

```bash
source .venv-pyodide/bin/activate
pip install dist/your_package-*.whl
```

## Run your code

Once activated, `python` runs on Pyodide/Node.js:

```bash
python -c "import your_package; print('it works!')"
```

Run your test suite (install pytest first — it's not pre-installed in the venv):

```bash
pip install pytest
python -m pytest tests/
```

```{important}
Use `python -m pytest` (not bare `pytest`). CLI entry points may not work correctly inside the Pyodide venv — always invoke tools as Python modules.
```

## How the venv works

The Pyodide venv looks like a normal virtualenv, but there are important differences:

| | Standard venv | Pyodide venv |
|---|---|---|
| `python` | Runs CPython natively | Runs Pyodide on Node.js |
| `pip` | Runs on host Python | Runs on **host Python**, but installs WebAssembly-compatible packages |
| Package compatibility | Any wheel for your platform | Only pure-Python wheels or `pyemscripten_*_wasm32` wheels |

Key things to know:

- **`pip` runs on host Python** — it uses your system Python to resolve and download packages, but only installs wheels compatible with WebAssembly. This means `pip install` is fast (no cross-compilation at install time).
- **`python` runs on Pyodide/Node.js** — when you run `python` or `python -c "..."`, it launches Node.js with the Pyodide runtime. This is the real WebAssembly environment.
- **Only binary-compatible wheels are installable** — `pip install` is configured with `only-binary=:all:`, so it won't attempt to build packages from source. If a WebAssembly wheel isn't available, the install will fail.

## Limitations

- **Requires Node.js** — the Pyodide venv needs Node.js to run the WebAssembly interpreter. Node.js >= 24 is recommended.
- **No threading** — `threading` and `multiprocessing` are not available in Pyodide.
- **No networking** — `socket`, `http.client`, and similar networking modules don't work. Use `pyodide.http` or `micropip` for HTTP requests.
- **Some tests may need skipping** — tests that rely on threads, subprocesses, networking, or platform-specific behavior will need to be skipped or adapted. Use markers like `@pytest.mark.skipif(sys.platform == "emscripten", ...)`.

## Recreating the venv

To recreate the venv from scratch (e.g., after updating pyodide-build):

```bash
pyodide venv --clear .venv-pyodide
```

## What's next?

- [CI with cibuildwheel](../how-to/cibuildwheel.md) — automate building and testing in CI
- [CI without cibuildwheel](../how-to/ci-direct.md) — set up GitHub Actions directly
- [Debugging Build Failures](../how-to/debugging.md) — troubleshooting when things go wrong
