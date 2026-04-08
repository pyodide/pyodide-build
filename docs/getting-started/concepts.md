# Concepts

This page explains the key ideas behind pyodide-build. Understanding these concepts will help you debug build issues and make sense of the configuration options.

## Why cross-compilation?

When you run `python -m build` on your laptop, your C extensions are compiled for your machine's architecture — x86_64 on most desktops, arm64 on Apple Silicon. The resulting wheel only works on that platform.

Pyodide runs Python inside WebAssembly, which is a completely different compilation target. You can't run `gcc` or `clang` and get a `.so` that works in WebAssembly — you need [Emscripten](https://emscripten.org/), a compiler toolchain that produces WebAssembly output from C/C++ source code.

pyodide-build automates this cross-compilation. When you run `pyodide build`, it:

1. Invokes your package's normal build system (setuptools, meson-python, scikit-build-core, etc.)
2. Intercepts all compiler and linker calls
3. Redirects them through Emscripten with the right flags for WebAssembly
4. Produces a standard wheel tagged for the Emscripten platform

Your build scripts don't need to change — pyodide-build handles the translation transparently.

## The cross-build environment

Cross-compilation needs more than just a compiler. Your package's build system needs to find Python headers, link against the right libraries, and query Python's `sysconfig` for the target platform — not the host. The **cross-build environment** (xbuildenv) provides all of this:

- **CPython headers and sysconfig data** compiled for Emscripten/WebAssembly
- **Pre-built package stubs** for packages like NumPy and SciPy that other packages link against at build time
- **Emscripten SDK** — the compiler toolchain itself (installed automatically)

When you run `pyodide build`, pyodide-build automatically downloads and sets up the cross-build environment if one isn't already installed. It's cached in your platform's user cache directory so subsequent builds are fast.

You can also manage the cross-build environment explicitly:

```bash
pyodide xbuildenv install          # install (or update) the cross-build environment
pyodide xbuildenv install 0.27.0   # install a specific Pyodide version
pyodide xbuildenv versions         # list installed versions
```

See [Managing Cross-Build Environments](../how-to/xbuildenv.md) for more details.

## Emscripten

[Emscripten](https://emscripten.org/) is the compiler toolchain that turns C and C++ code into WebAssembly. It provides drop-in replacements for standard compilers:

| Standard tool | Emscripten equivalent |
|---|---|
| `gcc` / `cc` | `emcc` |
| `g++` / `c++` | `em++` |
| `ar` | `emar` |
| `ranlib` | `emranlib` |

pyodide-build manages Emscripten automatically — it installs the correct version as part of the cross-build environment and handles all compiler redirection. You don't need to install or configure Emscripten yourself.

```{important}
Each Pyodide version requires a **specific** Emscripten version. pyodide-build enforces this to ensure ABI compatibility. You can check the required version with `pyodide config get emscripten_version`.
```

## Platform tags

Python wheels include a [platform tag](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/) that identifies which systems they can run on. For example:

- `manylinux_2_17_x86_64` — Linux on x86_64
- `macosx_14_0_arm64` — macOS on Apple Silicon
- `pyemscripten_2025_0_wasm32` — Emscripten/WebAssembly

The Emscripten platform tag, standardized by [PEP 783](https://peps.python.org/pep-0783/), has the format:

```
pyemscripten_{year}_{patch}_wasm32
```

Where `{year}_{patch}` is the platform ABI version (e.g., `2026_0`). This version determines which Emscripten SDK version and CPython build are used. Wheels built for one ABI version are **not** compatible with another.

A complete wheel filename looks like:

```
numpy-2.2.0-cp313-cp313-pyemscripten_2026_0_wasm32.whl
       │      │     │           │
       │      │     │           └── platform tag
       │      │     └── Python ABI tag
       │      └── Python version tag
       └── package version
```

```{note}
Older Pyodide versions (before PEP 783) used the tag `pyodide_{year}_{patch}_wasm32`. The `pyemscripten_*` tag is the standardized form going forward.
```

## `pyodide build` vs `python -m build`

`pyodide build` is designed to be a drop-in replacement for `python -m build` when targeting WebAssembly. Here's what's the same and what's different:

**The same:**
- Uses your existing `pyproject.toml` build configuration
- Supports the same build backends (setuptools, meson-python, scikit-build-core, hatchling, etc.)
- Produces a standard `.whl` file
- Supports `-C` / `--config-setting` to pass options to the build backend
- Supports `--no-isolation` for custom build environments

**Different:**
- Compiler calls are intercepted and redirected to Emscripten
- Some compiler flags are filtered out (e.g., `-pthread`, x86 SIMD flags) because they don't apply to WebAssembly
- The output wheel has an Emscripten platform tag instead of a native one
- A cross-build environment must be available (installed automatically on first use)

## What's next?

- [Quick Start](quickstart.md) — build your first WebAssembly wheel
- [Managing Cross-Build Environments](../how-to/xbuildenv.md) — advanced xbuildenv management
- [Platform Tags & Compatibility](../reference/platform.md) — full compatibility matrix
