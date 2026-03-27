# Platform Tags & Compatibility

The Emscripten/WebAssembly platform for Python is standardized by [PEP 783](https://peps.python.org/pep-0783/).

## Platform tag format

Wheels built by pyodide-build use the platform tag:

```
pyemscripten_{year}_{patch}_wasm32
```

A complete wheel filename:

```
numpy-2.2.0-cp313-cp313-pyemscripten_2025_0_wasm32.whl
       │      │     │           │
       │      │     │           └── platform tag
       │      │     └── Python ABI tag
       │      └── Python version tag
       └── package version
```

## Compatibility matrix

Each platform version is tied to a specific Python version and Emscripten SDK version. Wheels built for one platform version are **not** compatible with another.

| Platform tag | Python | Emscripten | Notes |
|---|---|---|---|
| `pyodide_2024_0_wasm32` | 3.12 | 3.1.58 | Legacy tag name |
| `pyemscripten_2025_0_wasm32` | 3.13 | 4.0.9 | PEP 783 standardized name |
| `pyemscripten_2026_0_wasm32` | 3.14 | TBD | Under development |

```{note}
Older Pyodide versions used the tag `pyodide_{year}_{patch}_wasm32`. The `pyemscripten_*` tag is the standardized form going forward per PEP 783.
```

## ABI compatibility rules

- Wheels are **not cross-version compatible** — a wheel built for `pyemscripten_2025_0_wasm32` will not work with `pyemscripten_2024_0_wasm32` or `pyemscripten_2026_0_wasm32`.
- Pure-Python wheels (`py3-none-any`) work on all versions.
- The ABI version determines which Emscripten SDK and CPython build are used. Mixing versions will cause load-time or runtime errors.

## cibuildwheel identifiers

When using [cibuildwheel](../how-to/cibuildwheel.md), the platform identifiers are:

| cibuildwheel identifier | Platform tag |
|---|---|
| `cp312-pyodide_wasm32` | `pyodide_2024_0_wasm32` |
| `cp313-pyodide_wasm32` | `pyemscripten_2025_0_wasm32` |

## Checking your platform version

```bash
pyodide config get pyodide_abi_version
```

## Further reading

- [PEP 783 — The Emscripten Platform](https://peps.python.org/pep-0783/) — formal specification
- [Concepts — Platform Tags](../getting-started/concepts.md) — introductory explanation
