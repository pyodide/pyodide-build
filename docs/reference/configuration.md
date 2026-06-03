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

These keys can be set in `pyproject.toml` under `[tool.pyodide.build]` or via environment variables:

| pyproject.toml key | Env variable | Description |
|---|---|---|
| `cflags` | `CFLAGS` | C compiler flags |
| `cxxflags` | `CXXFLAGS` | C++ compiler flags |
| `ldflags` | `LDFLAGS` | Linker flags |
| `rustflags` | `RUSTFLAGS` | Rust compiler flags |
| `rust_toolchain` | `RUST_TOOLCHAIN` | Required Rust nightly toolchain |
| `meson_cross_file` | `MESON_CROSS_FILE` | Path to the Meson cross file |
| `xbuildenv_path` | `PYODIDE_XBUILDENV_PATH` | Path to the cross-build environment |
| `ignored_build_requirements` | `IGNORED_BUILD_REQUIREMENTS` | Space-separated PEP 508 build requirements to ignore |
| `skip_emscripten_version_check` | `SKIP_EMSCRIPTEN_VERSION_CHECK` | Skip Emscripten version compatibility check (`0`/`1`) |
| `default_cross_build_env_url` | `DEFAULT_CROSS_BUILD_ENV_URL` | URL override for the cross-build environment archive |
| `use_legacy_platform` | `USE_LEGACY_PLATFORM` | Use the legacy `pyodide_*` platform tag instead of `pyemscripten_*` (`0`/`1`) |

Run `pyodide config list` to see all available variables and their current values.


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
