# Auditing and Repairing Wheels

When a Python extension links against shared libraries (`.so` files), those libraries must be available at runtime. On native platforms, `auditwheel` handles this by copying the shared libraries into the wheel. For WebAssembly wheels, pyodide-build uses [auditwheel-emscripten](https://github.com/pyodide/auditwheel-emscripten) via the `pyodide auditwheel` command.

## Install

`auditwheel-emscripten` is included as a dependency of pyodide-build and is available as a `pyodide` CLI plugin:

```bash
pip install pyodide-build
pyodide auditwheel --help
```

## When do you need this?

If your package links against a shared library that isn't included in the wheel after running `python -m build`,
you need to vendor that library into the wheel. Otherwise, the `.so` file will fail to load at runtime with an error like:

```
ImportError: unable to load shared library 'libfoo.so'
```

## Inspecting a wheel

Before repairing, inspect the wheel to see what shared libraries it depends on:

```bash
pyodide auditwheel show dist/your_package-*.whl
```

This lists all shared library dependencies of the wheel's `.so` files and shows which are already included and which need to be vendored.

## Repairing a wheel

The `repair` command finds the shared library dependencies and copies them into the wheel:

```bash
pyodide auditwheel repair dist/your_package-*.whl --libdir /path/to/libdir
```

The `--libdir` option specifies the directory where the shared libraries are located.

By default, the wheel is repaired in place, but you can specify an output directory with `-o`:

```bash
pyodide auditwheel repair dist/your_package-*.whl -o repaired/
```

The repair process:
1. Scans all `.so` files in the wheel for shared library dependencies
2. Locates the required libraries in the specified `--libdir`
3. Copies them into a `<package>.libs/` directory inside the wheel
4. Updates the RPATH of the `.so` files to point to the vendored libraries

## Typical workflow

```bash
# 1. Build the wheel
pyodide build .

# 2. Inspect shared library dependencies
pyodide auditwheel show dist/your_package-*.whl

# 3. Vendor shared libraries into the wheel
pyodide auditwheel repair dist/your_package-*.whl --libdir /path/to/libdir

# 4. Test the repaired wheel
pyodide venv .venv-pyodide
source .venv-pyodide/bin/activate
pip install dist/your_package-*.whl
python -m pytest tests/
```

## In cibuildwheel

Unlike manylinux, cibuildwheel doesn't automatically run auditwheel repair for Pyodide.
This is because we don't know where to locate the shared libraries that the `.so` files depend on.
We cannot find them from the host system paths since we need cross-compiled libraries not the host's libraries.

Therefore, you need to set the libdir explicitly in the cibuildwheel configuration.

```toml
[tool.cibuildwheel.pyodide]
repair-wheel-command = "pyodide auditwheel repair --libdir /path/to/libraries --output-dir {dest_dir} {wheel}"
```

## What's next?

- [CI with cibuildwheel](cibuildwheel.md) — cibuildwheel can run auditwheel repair automatically via `repair-wheel-command`
- [Debugging Build Failures](debugging.md) — troubleshooting shared library errors
