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
- [How pyodide-build Works](../explanation/architecture.md) — how the compiler wrapper handles your build
- [Customizing Compiler Flags](../how-to/compiler-flags.md) — fine-tuning the build
- [Debugging Build Failures](../how-to/debugging.md) — common error messages and systematic troubleshooting
- [CLI Reference — Export modes](../reference/cli.md) — controlling which symbols are exported (`--exports`)
