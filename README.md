# pyodide-build

Tools for building Pyodide.

See [http://github.com/pyodide/pyodide](http://github.com/pyodide/pyodide) for
more information.

## Quickstart

### Usage

> [!TIP]
> Currently, installing `pyodide-build` is preferred to running it.

#### Install it

```bash
pip install pyodide-build
pyodide --help
pyodide build --help
```

#### Install it globally

```bash
pipx install --include-deps pyodide-build
pyodide --help
pyodide build --help
```

or, alternatively

```bash
pipx install pyodide-cli
pipx inject pyodide-cli pyodide-build
pyodide --help
pyodide build --help
```

> [!NOTE]
> If installing `pyodide-build` and its dependencies in virtual environments, we recommend
using ones that are managed by `venv` or `virtualenv` at the moment; see #58.

### or run it

- with `uv`/`uvx`

```bash
uvx --from pyodide-cli --with pyodide-build pyodide --help
```

## License

Pyodide uses the [Mozilla Public License Version
2.0](https://choosealicense.com/licenses/mpl-2.0/).
