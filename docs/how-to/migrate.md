# Migrating from Native Builds

If you already build native wheels with `python -m build` and want to add Pyodide/WebAssembly support, this guide shows what to change and what to watch out for.

## The short version

For many packages, the migration is just:

```bash
pip install pyodide-build
pyodide build .
```

Your existing `pyproject.toml`, `setup.py`, `CMakeLists.txt`, or `meson.build` works as-is — pyodide-build handles the cross-compilation transparently. If the build succeeds, you're done.

This page covers what to do when it doesn't.

## What works differently in WebAssembly

WebAssembly (via Emscripten) is a different platform with different capabilities than Linux, macOS, or Windows. Some things your code may rely on are not available:

### No threading

`pthread`, `std::thread`, Python's `threading`, and `multiprocessing` are not available. Code that uses them will fail at runtime if not handled properly.

You need to guard threaded code paths like this:

```python
import sys

if sys.platform != "emscripten":
    import threading
    # threaded implementation
else:
    # single-threaded fallback
```

### No networking

`socket`, `http.client`, `urllib.request` (with network I/O), and similar modules don't work. Network access in Pyodide goes through the browser's fetch API.

**Fix** — guard network code or provide alternative implementations:

```python
import sys

if sys.platform == "emscripten":
    from pyodide.http import pyfetch
    # use pyfetch for HTTP
else:
    import urllib.request
    # standard networking
```


```{note}
Third party networking libraries such as `requests`, `aiohttp`, `urllib3`, `httpx`
has a Pyodide-specific code path that uses `pyodide.http.pyfetch` or similar alternatives.

Therefore, if you are using these libraries, your code should work for common use cases.
```

### No subprocesses

`subprocess`, `os.system`, `os.popen`, and related calls don't work in WebAssembly.

**Fix** — skip or mock subprocess-dependent functionality on Emscripten.

### 32-bit integers

WebAssembly is a 32-bit platform. Code that assumes 64-bit pointer sizes or uses pointer-to-int casts may behave differently.

## Detecting Pyodide at build time

pyodide-build sets the `PYODIDE` environment variable during the build. Use it to conditionally adjust your build configuration:

```python
# setup.py or build script
import os

if os.environ.get("PYODIDE"):
    # WebAssembly-specific build adjustments
    ...
```

For C/C++ code, use the Emscripten preprocessor macro:

```c
#ifdef __EMSCRIPTEN__
// WebAssembly-specific code
#else
// Native code
#endif
```

## Detecting Pyodide at runtime

```python
import sys

if sys.platform == "emscripten":
    # Running on Pyodide
    ...
```

## Common migration patterns

### Skipping unsupported tests

Mark tests that require threads, networking, subprocesses, or platform-specific behavior:

```python
import sys
import pytest

@pytest.mark.skipif(sys.platform == "emscripten", reason="No threads on Emscripten")
def test_concurrent_access():
    ...

@pytest.mark.skipif(sys.platform == "emscripten", reason="No sockets on Emscripten")
def test_http_client():
    ...
```

## Adding Pyodide to your CI

Once your build works locally, add it to CI alongside your native builds:

- [CI with cibuildwheel](cibuildwheel.md) — add Pyodide as a platform in your existing cibuildwheel config
- [CI without cibuildwheel](ci-direct.md) — add a separate GitHub Actions job

## What's next?

- [Debugging Build Failures](debugging.md) — systematic troubleshooting
- [Customizing Compiler Flags](compiler-flags.md) — fine-tuning the build
