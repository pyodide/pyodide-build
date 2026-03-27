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
pyodide xbuildenv install 0.27.0

# Install from a custom URL
pyodide xbuildenv install --url https://example.com/xbuildenv-0.27.0.tar

# Force install even if version compatibility check fails
pyodide xbuildenv install --force
```

## Listing installed versions

```bash
# List all installed versions (active version marked with *)
pyodide xbuildenv versions
```

Output:

```
* 0.27.0
  0.26.4
```

## Switching between versions

```bash
pyodide xbuildenv use 0.26.4
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
pyodide xbuildenv uninstall 0.26.4
```

## Searching for available versions

```bash
# Show versions compatible with your Python and pyodide-build
pyodide xbuildenv search

# Show all available versions
pyodide xbuildenv search --all

# Output as JSON (useful for scripting)
pyodide xbuildenv search --json
```

The search output shows version compatibility information:

```
┌────────────┬────────────┬────────────┬───────────────────────────┬────────────┐
│ Version    │ Python     │ Emscripten │ pyodide-build             │ Compatible │
├────────────┼────────────┼────────────┼───────────────────────────┼────────────┤
│ 0.27.7     │ 3.12.7     │ 3.1.58     │ 0.26.0 -                  │ Yes        │
│ 0.27.6     │ 3.12.7     │ 3.1.58     │ 0.26.0 -                  │ Yes        │
└────────────┴────────────┴────────────┴───────────────────────────┴────────────┘
```

## Where the xbuildenv is stored

pyodide-build resolves the xbuildenv path in this order:

1. `PYODIDE_XBUILDENV_PATH` environment variable
2. `xbuildenv_path` in `pyproject.toml` under `[tool.pyodide.build]`
3. Platform cache directory (`~/.cache/pyodide` on Linux, `~/Library/Caches/pyodide` on macOS)

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

- [Concepts](../getting-started/concepts.md) — understand what the cross-build environment provides
- [Customizing Compiler Flags](compiler-flags.md) — fine-tuning build flags
- [Configuration Reference](../reference/configuration.md) — all configuration options
