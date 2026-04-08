# FAQ

## Which packages work with Pyodide?

- **Pure Python** — does not need a separate build. Usually work out of the box, though may need changes if they use subprocesses, threads, or other unsupported features.
    - **Threading / multiprocessing** — not supported. Packages that require threads will not work.
    - **Networking (sockets)** — not supported. Packages that open raw sockets will not work. High-level HTTP libraries like `requests` and `httpx` have Pyodide-specific fallbacks.
    - **Subprocesses** — not supported. Packages that call `subprocess.run()` will not work.
- **C/C++ extensions** — usually work with pyodide-build. Some packages need adjustments (e.g., disabling optional native dependencies, guarding platform-specific code). Some need more substantial changes.
- **Rust extensions (PyO3)** — generally easier to port than C/C++ packages (note that the `wasm32-unknown-emscripten` needs to be enabled).


## Do I need the full Pyodide repository?

No. pyodide-build is a standalone package. Install it with `pip install pyodide-build` and you're ready to build. You don't need to clone the Pyodide repository.

## Do I need pyodide-build for pure Python packages?

No. A pure Python wheel built with `python -m build`, `hatch`, `flit`, or any standard build frontend is already compatible with Pyodide. pyodide-build is only needed for packages with compiled extensions (C, C++, Rust).

## Should I use `pyodide build` directly or cibuildwheel?

For most users we recommend cibuildwheel since it handles the whole process of building, testing, and distributing packages with the least configuration. For some complex use cases using pyodide-build directly may be preferable.

See [CI with cibuildwheel](how-to/cibuildwheel.md) and [CI without cibuildwheel](how-to/ci-direct.md).

## Can I use meson-python / scikit-build-core / maturin?

Yes. pyodide-build supports all major Python build backends.

- **setuptools** — works out of the box
- **meson-python** — cross file injected automatically. See [Tutorial: Meson](tutorials/meson.md).
- **scikit-build-core** — CMake toolchain handled automatically. See [Tutorial: CMake](tutorials/cmake.md).
- **maturin** — Rust target and flags set automatically. See [Tutorial: Rust](tutorials/rust.md).
- **hatchling / flit** — pure Python only (no compiled extensions), so no pyodide-build needed.

## What Node.js version do I need?

Node.js >= 24 is recommended for `pyodide venv`. Node.js is only needed for testing — not for building.

## What Python versions are supported?

pyodide-build requires Python 3.12 or later. The Python version must match the target Pyodide cross-build environment version.

## What's the difference between `pyodide build` and `python -m build`?

`python -m build` is commonly used to invoke [pypa/build](https://build.pypa.io/). `pyodide build` wraps `python -m build`, i.e., `pypa/build`, with a cross-compilation layer. Your build configuration stays the same — pyodide-build intercepts compiler calls and redirects them to Emscripten. See [Concepts](getting-started/concepts.md) for a detailed comparison.
