# CLI Reference

All commands are accessed through the `pyodide` CLI, provided by the [pyodide-cli](https://pypi.org/project/pyodide-cli/) package (installed automatically with pyodide-build).

## pyodide build

```{click} pyodide_build.cli.build:main
:prog: pyodide build
```

## pyodide venv

```{click} pyodide_build.cli.venv:main
:prog: pyodide venv
```

## pyodide config

```{click} pyodide_build.cli.config:app
:prog: pyodide config
:nested: full
```

## pyodide xbuildenv

```{click} pyodide_build.cli.xbuildenv:app
:prog: pyodide xbuildenv
:nested: full
```
