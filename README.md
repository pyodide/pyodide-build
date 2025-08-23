# pyodide-build

Tools for building Pyodide.

See [http://github.com/pyodide/pyodide](http://github.com/pyodide/pyodide) for
more information.

## Quickstart

### Usage

> [!TIP]
> Currently, installing `pyodide-build` is the recommended to use it, instead of running it directly.

#### Install it

```bash
pip install pyodide-build  # in an environment
pipx install --include-deps pyodide-build  # globally
```

> [!NOTE]
> Currently `pyodide-build` does not work well in virtual environments managed by `uv`, see #58.

#### or run it

- with `uv`/`uvx`

```bash
uvx --from pyodide-cli --with pyodide-build pyodide --help
```

## License

Pyodide uses the [Mozilla Public License Version
2.0](https://choosealicense.com/licenses/mpl-2.0/).
