# Publishing Wasm Wheels

WebAssembly wheels built by pyodide-build are standard Python wheels — they follow the same packaging format and can be published to PyPI like any other wheel.

```{note} PEP 783
The Emscripten/WebAssembly platform tags are standardized by [PEP 783](https://peps.python.org/pep-0783/).
```

## Publishing to PyPI

Upload with [twine](https://twine.readthedocs.io/) or any standard publishing tool:

```bash
twine upload dist/your_package-*.whl
```

__Recommended__: or use [trusted publishing](https://docs.pypi.org/trusted-publishers/) in GitHub Actions (no API tokens needed):

```yaml
  publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: wheels
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

## How users install your package

Once published, Pyodide users can install your package in two ways:

### In the browser (via micropip)

```python
import micropip
await micropip.install("your-package")
```

[micropip](https://micropip.pyodide.org/) fetches the wheel from PyPI and installs it in the running Pyodide environment.

### In a Pyodide venv (via pip)

```bash
pyodide venv .venv-pyodide
source .venv-pyodide/bin/activate
pip install your-package
```

pip resolves the correct `pyemscripten_*_wasm32` wheel automatically.

## What's next?

- [CI with cibuildwheel](cibuildwheel.md) — automate building for all platforms
- [CI without cibuildwheel](ci-direct.md) — GitHub Actions with pyodide build directly
