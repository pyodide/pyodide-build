# Managing Cross-Build Environments

The cross-build environment (xbuildenv) contains everything needed to cross-compile Python packages for WebAssembly:
CPython headers, sysconfig data, and the Emscripten SDK. pyodide-build installs it automatically on first use, but you can also manage it explicitly.

## Installing

The `pyodide xbuildenv install` command installs the cross-build environment.

You *must* have the same host Python version as the one used to build the cross-build environment.
If you have a different Python version, the installation will fail.

We recommend using `uv` or `pyenv` to manage your Python versions.

```bash
# Install the latest compatible version
pyodide xbuildenv install

# Install a specific Pyodide version
pyodide xbuildenv install 0.29.3

# Install from a custom URL
pyodide xbuildenv install --url https://example.com/xbuildenv-0.27.0.tar

# Force install even if version compatibility check fails
pyodide xbuildenv install --force

# Install the latest nightly release
pyodide xbuildenv install --nightly

# Install a specific nightly version
pyodide xbuildenv install 20260520 --nightly

# Install the debug variant of the latest nightly release
pyodide xbuildenv install --debug
```

## Listing installed versions

```bash
# List all installed versions (active version marked with *)
pyodide xbuildenv versions
```

Output:

```
* 0.29.3
  314.0.0
```

## Switching between versions

```bash
pyodide xbuildenv use 0.29.3
```

## Checking the current version

```bash
pyodide xbuildenv version
```

## Uninstalling

```bash
# Uninstall the current version
pyodide xbuildenv uninstall

# Uninstall a specific version
pyodide xbuildenv uninstall 0.29.3
```

## Searching for available versions

```bash
# Show versions compatible with your Python and pyodide-build
pyodide xbuildenv search

# Show all available versions (including incompatible ones)
pyodide xbuildenv search --all

# Search nightly releases
pyodide xbuildenv search --nightly

# Search nightly debug releases
pyodide xbuildenv search --debug

# Combine flags: show all nightly and debug releases
pyodide xbuildenv search --nightly --debug --all

# Output as JSON (useful for scripting)
pyodide xbuildenv search --json
```

## Where the xbuildenv is stored

pyodide-build resolves the xbuildenv path in this order:

1. `PYODIDE_XBUILDENV_PATH` environment variable
2. `xbuildenv_path` in `pyproject.toml` under `[tool.pyodide.build]`
3. Platform cache directory inside a `pyodide-build` cache folder. The default path is scoped to the current Python environment and `pyodide-build` installation, for example `~/.cache/pyodide-build/.pyodide-xbuildenv-<install-id>/0.29.4` on Linux.

Therefore, to pin a custom location for caching, etc:

```bash
export PYODIDE_XBUILDENV_PATH=/path/to/xbuildenv
```

Or in `pyproject.toml`:

```toml
[tool.pyodide.build]
xbuildenv_path = "/path/to/xbuildenv"
```

## Emscripten SDK

Each Pyodide version requires a specific Emscripten version. The Emscripten SDK is installed automatically when you run `pyodide build`.
You can also install it manually:

```bash
pyodide xbuildenv install-emscripten
```

Check the required Emscripten version:

```bash
pyodide config get emscripten_version
```

## What's next?

- [Concepts](../explanation/concepts.md) — understand what the cross-build environment provides
- [Customizing Compiler Flags](compiler-flags.md) — fine-tuning build flags
- [Configuration Reference](../reference/configuration.md) — all configuration options
