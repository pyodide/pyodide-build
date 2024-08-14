# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## [0.28.0] - 2024/08/14

- `pyodide xbuildenv` subcommand is now publicly available.
  [#15](https://github.com/pyodide/pyodide-build/pull/15)

## [0.27.3] - 2024/07/17

- It is now possible to override `_f2c_fixes.py` file, with `_f2c_fixes_wrapper` variable.
  [#8](https://github.com/pyodide/pyodide-build/pull/8)

## [0.27.2] - 2024/07/11

## Changed

- `pyodide py-compile` command now accepts `excludes` flag.
  [#9](https://github.com/pyodide/pyodide-build/pull/9)

- `cpython_module` type recipes now should output wheels
  [#10](https://github.com/pyodide/pyodide-build/pull/10)

## [0.27.1] - 2024/06/28

## Changed

- ported f2c_fixes patch from https://github.com/pyodide/pyodide/pull/4822

## [0.27.0] - 2024/06/18

- pyodide-build is now developed under https://github.com/pyodide/pyodide-build.
