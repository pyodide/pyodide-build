# Customizing Compiler Flags

pyodide-build sets default compiler and linker flags required/optimized for WebAssembly modules.
You can inspect, override, and extend these flags for your build.

## Default flags

You can inspect the default values we use by running:

```bash
pyodide config get cflags
pyodide config get cxxflags
pyodide config get ldflags
```

Note that the default flag differs per Pyodide version you target.

## Overriding flags

You can override flags in multiple ways:

### via pyproject.toml

```toml
[tool.pyodide.build]
cflags = "-O2 -g2"
cxxflags = "-O2 -g2"
ldflags = "-O2 -g2"
```

## via environment variables

Set environment variables before running `pyodide build`:

```bash
export CFLAGS="$(pyodide config get cflags) -DMY_DEFINE=1"
pyodide build .
```

Environment variables take precedence over `pyproject.toml` settings.

## Configuration precedence

Flags are resolved in this order (highest priority first):

1. Environment variables
2. `pyproject.toml` `[tool.pyodide.build]`
3. Cross-build environment defaults

## Flags that are automatically filtered

pyodide-build's compiler wrapper automatically removes flags that are incompatible with Emscripten/WebAssembly:

These are the non-exhaustive list of flags that are filtered.
If you find any flags that are not filtered but should be or vice versa, please let us know.

| Filtered flag | Reason |
|---|---|
| `-pthread` | Threading is not supported |
| `-bundle`, `-undefined dynamic_lookup` | macOS-specific linker flags |
| `-mpopcnt`, `-mno-sse2`, `-mno-avx2` | x86 SIMD flags (not applicable to Wasm) |
| `-Bsymbolic-functions` | GCC-specific flag not supported by Clang |
| `-fstack-protector` | Not supported in Emscripten |
| `-L/usr/*` | System library paths (not valid for cross-compilation) |

These are stripped silently — you don't need to remove them from your build scripts.

## Rust flags

Rust compiler flags are configured separately:

```bash
pyodide config get rustflags
# e.g., -C link-arg=-sSIDE_MODULE=2 -C link-arg=-sWASM_BIGINT
```

Override in `pyproject.toml`:

```toml
[tool.pyodide.build]
rustflags = "-C link-arg=-sSIDE_MODULE=2 -C link-arg=-sWASM_BIGINT -C opt-level=2"
```

## What's next?

- [Debugging Build Failures](debugging.md) — troubleshooting when the build fails
- [Configuration Reference](../reference/configuration.md) — all configuration options
- [How pyodide-build Works](../explanation/architecture.md) — how the compiler wrapper works
