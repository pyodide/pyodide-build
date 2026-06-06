# Tutorial: Meson Package

Many scientific Python packages use [Meson](https://mesonbuild.com/) via [meson-python](https://meson-python.readthedocs.io/) as their build system. pyodide-build supports Meson out of the box.

## Basic usage

For most Meson packages, just run:

```bash
pyodide build .
```

pyodide-build automatically intercepts `meson setup` calls and injects the Meson cross file, which tells Meson the build is targeting Emscripten. No manual configuration is needed.

## Passing Meson options

Use `-Csetup-args=` to pass options to Meson:

```bash
pyodide build . \
    -Csetup-args=-Dsome-option=value \
    -Csetup-args=-Danother-option=false
```

Each Meson option needs its own `-Csetup-args=` prefix.

## Real-world example: NumPy

NumPy uses meson-python. Here's how to build it for WebAssembly:

```bash
pyodide build . -Csetup-args=-Dallow-noblas=true
```

The `-Dallow-noblas=true` disables BLAS/LAPACK (which aren't available as Emscripten libraries by default). This pattern — disabling optional native dependencies — is common when cross-compiling.

## What the cross file provides

The Meson cross file that pyodide-build injects tells Meson:

- The host machine is `emscripten` / `wasm32`
- Use `node` as the executable wrapper
- Skip the compiler sanity check (Emscripten's output can't run natively)

```{tip}
If automatic cross file injection doesn't work for your setup, you can pass it explicitly:

    MESON_CROSS_FILE=$(pyodide config get meson_cross_file)
    pyodide build . -Csetup-args=--cross-file="$MESON_CROSS_FILE"

Or via the `MESON_CROSS_FILE` environment variable:

    export MESON_CROSS_FILE=$(pyodide config get meson_cross_file)
    pyodide build .
```

## What's next?

- [Tutorial: CMake Package](cmake.md) — building packages with CMake / scikit-build-core
- [Tutorial: Rust Package](rust.md) — building packages with PyO3/Maturin
- [Customizing Compiler Flags](../how-to/compiler-flags.md) — fine-tuning compiler and linker flags
