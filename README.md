# pyodide-build

Tools for building packages for use with Pyodide. You may be interested in using
this with [cibuildwheel](https://github.com/pypa/cibuildwheel)

See [http://github.com/pyodide/pyodide](https://github.com/pyodide/pyodide) for
more information about the Pyodide project.

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

Pyodide uses the
[Mozilla Public License Version 2.0](https://choosealicense.com/licenses/mpl-2.0/).
