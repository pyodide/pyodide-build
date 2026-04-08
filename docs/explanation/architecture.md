# How pyodide-build Works

This page explains how pyodide-build cross compiles normal Linux-compatible Python packages into wheels that can be used with Pyodide.

## The build pipeline

When you run `pyodide build .`, the following happens:

```
┌────────────────┐
│ pyodide-build  │  CLI entry point
└───────┬────────┘
        │
        ▼
┌────────────────┐
│  Environment   │  Install cross-build environment (if needed)
│    setup       │  Set up headers, env vars
└───────┬────────┘
        │
        ▼
┌────────────────┐
│   pypa/build   │  Standard PEP 517 build frontend
│                │  Invokes your build backend (setuptools, meson-python, etc.)
└───────┬────────┘
        │  Build backend calls gcc, g++, cmake, meson, cargo...
        ▼
┌────────────────┐
│  pywasmcross   │  Compiler wrapper — intercepts all tool calls
│                │  Redirects to Emscripten (emcc, em++, emar, etc.)
│                │  Filters incompatible flags, adds Wasm flags
└───────┬────────┘
        │
        ▼
┌────────────────┐
│   Emscripten   │  Compiles C/C++ → WebAssembly (.o, .a, .so)
│  (emcc/em++)   │  Links as SIDE_MODULE
└───────┬────────┘
        │
        ▼
┌────────────────┐
│  Wheel output  │  .so files (Wasm) + Python files → .whl
│                │  Tagged: pyemscripten_YYYY_P_wasm32
└────────────────┘
```

## The compiler wrapper

The core of pyodide-build is a compiler wrapper that transparently redirects native compiler calls to Emscripten.

### How it works

When pyodide-build sets up the build environment, it adds overrides for `gcc` and other compiler toolchain tools to the beginning of the path.

| Tool | override |
|---|---|
| `cc`, `gcc` | `emcc` |
| `c++`, `g++` | `em++` |
| `ar` | `emar` |
| `ranlib` | `emranlib` |
| `strip` | `emstrip` |
| `cmake` | `emcmake cmake` (with toolchain flags) |
| `meson` | `meson` (with cross file injected) |
| `cargo` | `cargo` (with Emscripten target) |

When the compiler wrapper is invoked:

1. Detects which tool it's impersonating
2. Rewrites the command line for Emscripten
3. Filters out native flags that emcc cannot handle
4. Adds WebAssembly-specific flags
5. Executes the real Emscripten tool

When `pyodide build` runs:

1. Set compiler flags, paths, and environment variables
2. The `sysconfig` module is patched to return target-platform values instead of host values
3. `PATH` is modified so compiler wrappers take priority over native compilers
4. Environment variables (`CMAKE_TOOLCHAIN_FILE`, `MESON_CROSS_FILE`, etc.) are set

## Build isolation

By default, `pyodide build` uses [pypa/build](https://build.pypa.io/) in isolated mode — just like `python -m build`. This means:

1. A temporary virtual environment is created
2. Build dependencies from `[build-system].requires` are installed
3. The build backend is invoked
4. The virtual environment is discarded

The `--no-isolation` flag skips this and uses the current environment, which is useful for complex builds where you need to manage dependencies yourself.

## Further reading

- [Emscripten documentation](https://emscripten.org/docs/) — the underlying compiler toolchain
- [PEP 517](https://peps.python.org/pep-0517/) — Python build system interface
