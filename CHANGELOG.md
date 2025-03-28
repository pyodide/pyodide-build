# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Added basic support for uv. `uv tool install pyodide-cli --with pyodide-build`, or `uvx --from pyodide-cli --with pyodide-build pyodide --help`, or using `pyodide-build` in `uv`-managed virtual environments will now work.
  [#132](https://github.com/pyodide/pyodide-build/pull/132)

### Changed

- The Rust toolchain version has been updated to `nightly-2025-01-18`.
  [#103](https://github.com/pyodide/pyodide-build/pull/103)

- Removed `cmake` dependency from the package.
  The Pyodide build system now uses the `cmake` package specified in the `pyproject.toml` file
  of the target package.
  [#141](https://github.com/pyodide/pyodide-build/pull/141)

### Fixed

- Fixed Pyodide venv `sys_platform` marker evaluation with pip >= 25.
  [#108](https://github.com/pyodide/pyodide-build/pull/108)

## [0.29.3] - 2025/02/04

### Added

- Added new configuration variable `default_cross_build_env_url`.
  [#85](https://github.com/pyodide/pyodide-build/pull/85)

- Added a new recipe key `requirement.constraint` to set the package-level constraints.
  [#97](https://github.com/pyodide/pyodide-build/pull/97)

- The `pyodide venv` command now supports more `virtualenv` command-line flags
  to customise the virtual environment creation behaviour (experimental)
  [#117](https://github.com/pyodide/pyodide-build/pull/117)

## [0.29.2] - 2024/11/29

### Fixed

- Fixed `pyodide venv` command not loading the shared libraries correctly, resulting in the package load failure.
  This bug was introduced in version 0.28.
  [#67](https://github.com/pyodide/pyodide-build/pull/67)

## [0.29.1] - 2024/11/27

### Added

- Add `skip_emscripten_version_check` flag and SKIP_EMSCRIPTEN_VERSION_CHECK environment
  variable to skip emscripten version check.
  [#53](https://github.com/pyodide/pyodide-build/pull/53)
- Set the `EM_PKG_CONFIG_PATH` environment variable used by emscripten/`pkg-config` to discover dependencies
  [#52](https://github.com/pyodide/pyodide-build/pull/52)

### Changed

- Source tar files are now extracted with python's [data filter](https://docs.python.org/3/library/tarfile.html#tarfile.data_filter)
  [#52](https://github.com/pyodide/pyodide-build/pull/52)

- The `pyodide build` command will now raise an error if the local Python version has been changed,
  after the cross-build environment has been set up.
  [#62](https://github.com/pyodide/pyodide-build/pull/62)

## [0.29.0] - 2024/09/19

### Added

- The `pyodide xbuildenv search` command now accepts a `--json` flag to output the
  search results in JSON format that is machine-readable. The design for the regular
  tabular output has been improved.
  [#28](https://github.com/pyodide/pyodide-build/pull/28)

### Changed

- The `pyodide skeleton pypi --update` command and the `--update-patched` variant now
  validate the version and the source checksum when updating a package's recipe.
  [#27](https://github.com/pyodide/pyodide-build/pull/27)

- `pyo3_config_file` is no longer available in `pyodide config` command.
  Pyodide now sets `PYO3_CROSS_PYTHON_VERSION`, `PYO3_CROSS_LIB_DIR` to specify the cross compilation environment
  for PyO3.
  [#19](https://github.com/pyodide/pyodide-build/pull/19)

## [0.28.0] - 2024/08/14

- `pyodide xbuildenv` subcommand is now publicly available.
  [#15](https://github.com/pyodide/pyodide-build/pull/15)

## [0.27.3] - 2024/07/17

- It is now possible to override `_f2c_fixes.py` file, with `_f2c_fixes_wrapper` variable.
  [#8](https://github.com/pyodide/pyodide-build/pull/8)

## [0.27.2] - 2024/07/11

### Changed

- `pyodide py-compile` command now accepts `excludes` flag.
  [#9](https://github.com/pyodide/pyodide-build/pull/9)

- `cpython_module` type recipes now should output wheels
  [#10](https://github.com/pyodide/pyodide-build/pull/10)

## [0.27.1] - 2024/06/28

### Changed

- ported f2c_fixes patch from https://github.com/pyodide/pyodide/pull/4822

## [0.27.0] - 2024/06/18

- pyodide-build is now developed under https://github.com/pyodide/pyodide-build.
