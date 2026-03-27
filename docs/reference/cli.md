# CLI Reference

All commands are accessed through the `pyodide` CLI, provided by the [pyodide-cli](https://pypi.org/project/pyodide-cli/) package (installed automatically with pyodide-build).

## pyodide build

Build a Python package for WebAssembly.

```
pyodide build [OPTIONS] [SOURCE_LOCATION]
```

**Arguments:**

| Argument | Description |
|---|---|
| `SOURCE_LOCATION` | Build source: a directory. Defaults to the current directory. |

**Options:**

| Option | Default | Description |
|---|---|---|
| `-o`, `--outdir` | `./dist` | Output directory for the built wheel |
| `--exports` | `requested` | Symbol export mode: `pyinit`, `requested`, `whole_archive`, or comma-separated list |
| `-C`, `--config-setting` | | Pass settings to the build backend (same as `pypa/build`) |
| `-n`, `--no-isolation` | `false` | Disable build isolation; build deps must be installed manually |
| `-x`, `--skip-dependency-check` | `false` | Skip build dependency check (only with `--no-isolation`) |
| `--compression-level` | `6` | Zip compression level for the wheel |
| `--xbuildenv-path` | platform cache | Path to the cross-build environment, inferred from platform cache if not specified |

## pyodide venv

Create a Pyodide virtual environment for testing.

```
pyodide venv [OPTIONS] DEST
```

**Arguments:**

| Argument | Description |
|---|---|
| `DEST` | Directory to create the virtualenv at |

**Options:**

| Option | Default | Description |
|---|---|---|
| `--clear` / `--no-clear` | `no-clear` | Remove destination directory if it exists |
| `--no-vcs-ignore` | | Don't create VCS ignore directive (e.g., `.gitignore`) |
| `--download` / `--no-download` | | Enable/disable download of latest pip/setuptools from PyPI |
| `--extra-search-dir` | | Path containing additional wheels |
| `--pip` | `bundle` | pip version: `embed`, `bundle`, or exact version |
| `--setuptools` | | setuptools version: `embed`, `bundle`, `none`, or exact version |
| `--no-setuptools` | | Do not install setuptools |

## pyodide config

Query build configuration values.

### pyodide config list

```
pyodide config list
```

Lists all config variables and their current values.

### pyodide config get

```
pyodide config get CONFIG_VAR
```

Get a single config variable's value. Common variables:

| Variable | Description |
|---|---|
| `cflags` | C compiler flags |
| `cxxflags` | C++ compiler flags |
| `ldflags` | Linker flags |
| `rustflags` | Rust compiler flags |
| `cmake_toolchain_file` | Path to CMake toolchain file |
| `meson_cross_file` | Path to Meson cross file |
| `rust_toolchain` | Required Rust nightly toolchain |
| `emscripten_version` | Required Emscripten version |
| `python_version` | Target Python version |
| `xbuildenv_path` | Cross-build environment path |
| `pyodide_abi_version` | Pyodide ABI version |

## pyodide xbuildenv

Manage the cross-build environment.

### pyodide xbuildenv install

```
pyodide xbuildenv install [OPTIONS] [VERSION]
```

| Option | Env var | Description |
|---|---|---|
| `--path` | `PYODIDE_XBUILDENV_PATH` | Destination directory |
| `--url` | | Download from a custom URL |
| `-f`, `--force` | | Force install even if version is incompatible |

### pyodide xbuildenv version

```
pyodide xbuildenv version [--path PATH]
```

Print the current active version.

### pyodide xbuildenv versions

```
pyodide xbuildenv versions [--path PATH]
```

List all installed versions. Active version is marked with `*`.

### pyodide xbuildenv use

```
pyodide xbuildenv use VERSION [--path PATH]
```

Switch to a specific installed version.

### pyodide xbuildenv uninstall

```
pyodide xbuildenv uninstall [VERSION] [--path PATH]
```

Uninstall a version. Defaults to the current version if not specified.

### pyodide xbuildenv search

```
pyodide xbuildenv search [OPTIONS]
```

| Option | Description |
|---|---|
| `--metadata` | Custom metadata file URL or path |
| `-a`, `--all` | Show all versions, including incompatible ones |
| `--json` | Output as JSON |
