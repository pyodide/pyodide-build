# Tutorial: CMake Package

Python packages that use [CMake](https://cmake.org/) — typically via [scikit-build-core](https://scikit-build-core.readthedocs.io/) — are supported by pyodide-build.

## Basic usage

If your package uses scikit-build-core or another build system that invokes CMake, you can build it directly with pyodide-build:

```bash
pyodide build .
```

pyodide-build automatically intercepts `cmake` calls and configures the Emscripten toolchain, including compiler paths and build flags.

## What the toolchain provides

pyodide-build has a custom CMake toolchain that is used to configure the build to target Emscripten.

The CMake toolchain that pyodide-build injects:

- Inherits from Emscripten's own CMake toolchain
- It sets the compiler and linkers
- Sets up library search paths for the cross-build environment

```{tip}
If automatic toolchain injection doesn't work for your setup, you can pass it explicitly:

    CMAKE_TOOLCHAIN_FILE=$(pyodide config get cmake_toolchain_file)
    pyodide build . -Ccmake.toolchain="$CMAKE_TOOLCHAIN_FILE"

Or via the `CMAKE_ARGS` environment variable:

    export CMAKE_ARGS="-DCMAKE_TOOLCHAIN_FILE=$(pyodide config get cmake_toolchain_file)"
    pyodide build .
```

## What's next?

- [Tutorial: Meson Package](meson.md) — building packages with Meson / meson-python
- [Tutorial: Rust Package](rust.md) — building packages with PyO3/Maturin
- [Customizing Compiler Flags](../how-to/compiler-flags.md) — fine-tuning compiler and linker flags
