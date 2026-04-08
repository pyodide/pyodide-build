# Tutorial: Rust Package

Python packages with Rust extensions — typically built with [PyO3](https://pyo3.rs/) and [Maturin](https://www.maturin.rs/) — can be cross-compiled for WebAssembly using pyodide-build.

```{note}
Rust support in pyodide-build requires some manual setup compared to C/C++ packages. You need to install the correct Rust toolchain and Emscripten target yourself.
```

## Prerequisites

### 1. Install Rust

If you don't have Rust installed, use [rustup](https://rustup.rs/) to install it.

### 2. Install the correct Rust toolchain (optional)

Depending on the Pyodide/Python version you're targeting, you may need a specific Rust toolchain version.
This might not be necessary in all cases for Python 3.14 or later, but if you encounter issues, you can try installing the correct toolchain.

Query it with:

```bash
pyodide config get rust_toolchain
```

Install and activate it:

```bash
RUST_TOOLCHAIN=$(pyodide config get rust_toolchain)
rustup toolchain install "$RUST_TOOLCHAIN"
rustup default "$RUST_TOOLCHAIN"
```

### 3. Add the Emscripten target

The `wasm32-unknown-emscripten` target must be available for your Rust toolchain:

```bash
RUST_TOOLCHAIN=$(pyodide config get rust_toolchain)
rustup target add wasm32-unknown-emscripten --toolchain "$RUST_TOOLCHAIN"
```

## Build a Rust package

With the toolchain set up, build your Maturin/PyO3 package:

```bash
pyodide build .
```

pyodide-build sets the following environment variables automatically during the build:

| Variable | Value | Purpose |
|---|---|---|
| `CARGO_BUILD_TARGET` | `wasm32-unknown-emscripten` | Tells Cargo to cross-compile for Emscripten |
| `CARGO_TARGET_WASM32_UNKNOWN_EMSCRIPTEN_LINKER` | `emcc` | Uses Emscripten as the linker |
| `PYO3_CROSS_INCLUDE_DIR` | `<xbuildenv>/include` | PyO3 cross-compilation: Python headers location |
| `PYO3_CROSS_LIB_DIR` | `<xbuildenv>/lib` | PyO3 cross-compilation: Python library location |
| `PYO3_CROSS_PYTHON_VERSION` | `3.x` | PyO3 cross-compilation: target Python version |

You don't need to set these manually — they come from the cross-build environment.

## Querying Rust configuration

Use `pyodide config` to inspect the Rust-related build settings:

```bash
pyodide config get rust_toolchain              # e.g., 1.93.0
pyodide config get rustflags                   # e.g., -C link-arg=-sSIDE_MODULE=2 ...
```

## Limitations

- **Nightly Rust required** — Before Python 3.14, the `wasm32-unknown-emscripten` target is not available on stable Rust. The specific nightly version must match what pyodide-build expects.

## What's next?

- [Tutorial: C Extension](c-extension.md) — building packages with C extensions
- [Customizing Compiler Flags](../how-to/compiler-flags.md) — fine-tuning compiler and linker flags
- [Configuration Reference](../reference/configuration.md) — all `pyodide config` values
