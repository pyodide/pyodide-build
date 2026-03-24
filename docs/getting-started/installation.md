# Installation

## Requirements

- **Linux or macOS** — pyodide-build works best on Linux and macOS. Windows is not supported.
- **Python 3.12 or later** — **must** match the Python version targeted by the Pyodide cross-build environment you install.
- **Node.js** — required for testing with [`pyodide venv`](testing.md). Not needed for building. Node.js >= 24 is recommended.

## Install pyodide-build

::::{tab-set}

:::{tab-item} pip
```bash
pip install pyodide-build
```
:::

:::{tab-item} pipx
```bash
pipx install pyodide-build
```
:::

:::{tab-item} uv
```bash
uv tool install pyodide-cli --with pyodide-build
```
:::

::::

Verify the installation:

```bash
pyodide --version
```

## What's next?

- [Concepts](concepts.md) — understand cross-compilation, the cross-build environment, and platform tags
- [Quick Start](quickstart.md) — build your first WebAssembly wheel
