# Tutorial: Package with C Extension

This tutorial walks through building a Python package with a C extension for WebAssembly. We'll start with a minimal example, build it, test it, and then cover what to do when things go wrong.

## Example package

Consider a package `fastcount` with this layout:

```
fastcount/
├── pyproject.toml
├── fastcount/
│   ├── __init__.py
│   └── _core.c
```

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "fastcount"
version = "1.0.0"

[tool.setuptools]
ext-modules = [
    {name = "fastcount._core", sources = ["fastcount/_core.c"]}
]
```

`fastcount/__init__.py`:

```python
from fastcount._core import count_chars
```

`fastcount/_core.c`:

```c
#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject* count_chars(PyObject* self, PyObject* args) {
    const char* str;
    char target;
    if (!PyArg_ParseTuple(args, "sC", &str, &target))
        return NULL;

    long count = 0;
    for (const char* p = str; *p; p++) {
        if (*p == target) count++;
    }
    return PyLong_FromLong(count);
}

static PyMethodDef methods[] = {
    {"count_chars", count_chars, METH_VARARGS, "Count occurrences of a character."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT, "_core", NULL, -1, methods
};

PyMODINIT_FUNC PyInit__core(void) {
    return PyModule_Create(&module);
}
```

## Build it

```bash
pyodide build .
```

That's it. pyodide-build:

1. Invokes setuptools to compile `_core.c`
2. Intercepts the `gcc`/`cc` call and redirects it to Emscripten's `emcc`
3. Links the compiled WebAssembly into a `.so` file (which is actually a Wasm binary)
4. Packages everything into a wheel with the `pyemscripten_*_wasm32` platform tag

Output:

```
dist/fastcount-1.0.0-cp314-cp314-pyemscripten_2026_0_wasm32.whl
```

## Test it

```bash
pyodide venv .venv-pyodide
source .venv-pyodide/bin/activate
pip install dist/fastcount-*.whl
python -c "from fastcount import count_chars; print(count_chars('hello world', 'l'))"
# Output: 3
```

## What happens under the hood

When pyodide-build intercepts a compiler call, it does more than just swap `gcc` for `emcc`. It also:

- **Filters incompatible flags** — flags like `-pthread`, `-mpopcnt`, `-mno-sse2`, and macOS-specific flags (`-bundle`, `-undefined dynamic_lookup`) are silently removed because they don't apply to WebAssembly.
- **Adds Emscripten flags** — flags like `-s SIDE_MODULE=1` are added to produce a loadable WebAssembly module.

You can see exactly what compiler commands are being run by setting `EMCC_DEBUG=1`:

```bash
EMCC_DEBUG=1 pyodide build .
```

## Export modes

When linking a `.so` file for WebAssembly, pyodide-build needs to know which symbols to export (make visible to the Python runtime). The `--exports` flag controls this:

| Mode | What it exports | When to use |
|---|---|---|
| `pyinit` | Only `PyInit_*` functions | Minimal exports. Works for standard Python C extensions that don't need to share symbols. |
| `requested` | All public symbols from object files | **Default.** Use when other extensions or packages may need to link against your symbols at runtime. |
| `whole_archive` | Everything | No filtering at all. Use for shared libraries or when the other modes cause missing symbol errors. Produces larger files. |

The default is `requested`. For most packages, you don't need to change this:

```bash
# Only if you need a different export mode:
pyodide build . --exports pyinit
pyodide build . --exports whole_archive
```

You can also export specific symbols by name:

```bash
pyodide build . --exports "my_func1,my_func2"
```

## Common build issues

### Missing header files

```
fatal error: 'some_library.h' file not found
```

This means your C code includes a header that isn't available in the Emscripten.

If it's a system library, it needs to be cross-compiled for Emscripten first. pyodide-build does not allow reading headers from the host system's include paths.
This is because linking the library built for the host system to the WebAssembly module will cause build time / runtime errors.

### Undefined symbols at link time

```
wasm-ld: error: undefined symbol: some_function
```

This usually means your extension depends on a C library that hasn't been compiled for WebAssembly. Check:
- Is the library available in the Emscripten by default?
- Does the library need to be cross-compiled for WebAssembly first?
- Try `--exports whole_archive` if the symbol should be coming from your own code.

### Unsupported compiler features

```
error: unsupported option '-pthread'
```

This means Emscripten does not support the flag you are passing to the compiler.
Since WASM is a different architecture from native systems, some compiler flags are not supported.

pyodide-build filters out most incompatible flags automatically, but some may slip through.
You may need to conditionally disable them:

```python
# setup.py
import os

extra_compile_args = ["-O2"]
if os.environ.get("PYODIDE"):
    # Skip flags that don't work in WebAssembly
    pass
else:
    extra_compile_args.append("-pthread")
```

The `PYODIDE` environment variable is set by pyodide-build during the build process.

### Function pointer type mismatch

```
RuntimeError: function signature mismatch
```

WebAssembly enforces strict function pointer typing. If your C code casts function pointers to incompatible types (common in older C code), you'll get this error at runtime, not at build time. The fix is to ensure function pointer types match exactly.

```{Tip}
This error is very common but often very tricky to debug by human eyes. Usually coding agents are quite helpful in identifying and fixing this issue.
```

## Using Cython

Cython extensions work the same way — pyodide-build intercepts the C compilation step that Cython generates:

```toml
[build-system]
requires = ["setuptools", "cython"]
build-backend = "setuptools.build_meta"
```

No special configuration is needed for Cython. Just run `pyodide build .` as usual.

## What's next?

- [Tutorial: Meson Package](meson.md) — building packages with Meson
- [Tutorial: CMake Package](cmake.md) — building packages with CMake
- [Tutorial: Rust Package](rust.md) — building packages with PyO3/Maturin
- [Customizing Compiler Flags](../how-to/compiler-flags.md) — fine-tuning the build
- [Debugging Build Failures](../how-to/debugging.md) — systematic troubleshooting
