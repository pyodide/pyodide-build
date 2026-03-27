# pyodide-build

**Build Python packages for WebAssembly.**

pyodide-build is the build toolchain for compiling Python packages to [WebAssembly](https://webassembly.org/) via [Emscripten](https://emscripten.org/). It is the reference implementation of the build toolchain for the [Emscripten/WebAssembly Python platform](https://peps.python.org/pep-0783/).

This tool is designed to be used with [Pyodide](https://pyodide.org/), but it can also be used with other Emscripten-based Python runtimes that support the same platform tags.

If you're familiar with `python -m build`, pyodide-build works the same way — just replace it with `pyodide build`:

```bash
pip install pyodide-build
pyodide build .
```

This produces a `.whl` file tagged for the Emscripten platform (e.g., `your_package-1.0-cp313-cp313-pyemscripten_2025_0_wasm32.whl`) that can be published to PyPI and installed in [Pyodide](https://pyodide.org/).

## Who is this for?

```{note}
**Pure-Python packages do not need pyodide-build.** A standard wheel built with `python -m build`, `hatch`, `flit`, or any PEP 517 build frontend is already compatible with Pyodide. pyodide-build is for packages that contain compiled extensions.
```

pyodide-build is for **Python package maintainers** who want their package to work in WebAssembly environments — the browser, Node.js, or any Emscripten-based Python runtime. Typical users include:

- **Package authors** adding Pyodide/WebAssembly to their platform support matrix
- **Library maintainers** whose users need the package in [JupyterLite](https://jupyterlite.readthedocs.io/), [Pyodide](https://pyodide.org/), or other browser-based Python environments

## How it works

pyodide-build wraps [pypa/build](https://build.pypa.io/) with a cross-compilation layer. When you run `pyodide build`, it:

1. Sets up a cross-build environment with Emscripten-compiled CPython headers and sysconfig data
2. Intercepts compiler calls (`gcc`, `g++`, `ld`, etc.) and redirects them to Emscripten (`emcc`, `em++`)
3. Translates compiler flags for WebAssembly compatibility
4. Produces a standard wheel with the appropriate platform tag

Your existing `setup.py`, `pyproject.toml`, CMakeLists.txt, or `meson.build` works as-is — pyodide-build handles the cross-compilation transparently.

## Where to start

::::{grid} 1 1 2 3
:gutter: 2

:::{grid-item-card} Quick Start
:link: getting-started/quickstart
Build your first WebAssembly wheel in 5 minutes.
:::

:::{grid-item-card} CI with cibuildwheel
:link: how-to/cibuildwheel
Add Pyodide to your existing cibuildwheel CI pipeline.
:::

:::{grid-item-card} Testing with `pyodide venv`
:link: getting-started/testing
Verify your wheel works in a Pyodide environment.
:::

::::

```{toctree}
:maxdepth: 2
:hidden:
:caption: Getting Started

getting-started/installation
getting-started/concepts
getting-started/quickstart
getting-started/testing
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: Tutorials

tutorials/c-extension
tutorials/meson
tutorials/cmake
tutorials/rust
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: How-to Guides

how-to/cibuildwheel
how-to/ci-direct
how-to/publishing
how-to/migrate
how-to/xbuildenv
how-to/compiler-flags
how-to/debugging
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: Reference

reference/cli
reference/configuration
reference/platform
explanation/architecture
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: Appendix

faq
changelog
```

## Communication

- Discord: [Pyodide Discord](https://dsc.gg/pyodide)
- Blog: [blog.pyodide.org](https://blog.pyodide.org/)
- Mailing list: [mail.python.org/mailman3/lists/pyodide.python.org/](https://mail.python.org/mailman3/lists/pyodide.python.org/)
- X: [x.com/pyodide](https://x.com/pyodide)
- Stack Overflow: [stackoverflow.com/questions/tagged/pyodide](https://stackoverflow.com/questions/tagged/pyodide)
