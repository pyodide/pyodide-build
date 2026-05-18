# Configuration Reference

pyodide-build reads configuration from multiple sources. This page documents all available settings.

## Precedence

Configuration is resolved in this order (highest priority first):

1. **Environment variables**
2. **`pyproject.toml`** under `[tool.pyodide.build]`
3. **Cross-build environment** defaults
4. **Built-in defaults**

## pyproject.toml

Add configuration under `[tool.pyodide.build]`:

```toml
[tool.pyodide.build]
cflags = "-O2"
cxxflags = "-O2"
ldflags = "-s SIDE_MODULE=1 -O2"
xbuildenv_path = "/path/to/xbuildenv"
```

## User-overridable settings

These keys can be set in `pyproject.toml` or via environment variables:

| pyproject.toml key | Env variable | Description |
|---|---|---|
| `cflags` | `CFLAGS` | C compiler flags |
| `cxxflags` | `CXXFLAGS` | C++ compiler flags |
| `ldflags` | `LDFLAGS` | Linker flags |
| `rustflags` | `RUSTFLAGS` | Rust compiler flags |
| `rust_toolchain` | `RUST_TOOLCHAIN` | Rust nightly toolchain version |
| `meson_cross_file` | `MESON_CROSS_FILE` | Path to Meson cross file |
| `xbuildenv_path` | `PYODIDE_XBUILDENV_PATH` | Path to cross-build environment |
| `ignored_build_requirements` | `IGNORED_BUILD_REQUIREMENTS` | Build requirements to ignore |

## Environment variables

### Querying configuration

Use `pyodide config` to inspect active values:

```bash
# List all settings
pyodide config list

# Get a specific value
pyodide config get cflags
pyodide config get meson_cross_file
pyodide config get rust_toolchain
```

See the [CLI Reference](cli.md) for details.
