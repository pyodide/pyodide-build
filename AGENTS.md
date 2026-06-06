# AGENTS.md — pyodide-build

This file helps AI coding agents understand the `pyodide-build` repository.

## Project Overview

`pyodide-build` is the build toolchain for [Pyodide](https://pyodide.org/) — a CPython distribution compiled to WebAssembly (Wasm) via Emscripten. This package provides the `pyodide` CLI and associated Python library that:

- Cross-compiles Python packages (pure and native) for Wasm/Emscripten
- Manages cross-build environments (`xbuildenv`) for out-of-tree builds
- Creates Pyodide virtual environments (`pyodide venv`)
- Handles recipe-based package builds (via `meta.yaml` files)

---

## Repository Structure

```
pyodide-build/
├── pyodide_build/           # Main Python package
│   ├── cli/                 # Click CLI commands (entrypoints)
│   │   ├── build.py         # `pyodide build` — build a package from source/PyPI/URL
│   │   ├── build_recipes.py # `pyodide build-recipes` — build multiple recipe packages
│   │   ├── clean.py         # `pyodide clean` — clean build artifacts
│   │   ├── config.py        # `pyodide config` — query build configuration
│   │   ├── py_compile.py    # `pyodide py-compile` — compile .py to .pyc
│   │   ├── skeleton.py      # `pyodide skeleton` — generate meta.yaml from PyPI
│   │   ├── venv.py          # `pyodide venv` — create Pyodide virtual environments
│   │   └── xbuildenv.py     # `pyodide xbuildenv` — manage cross-build environments
│   ├── recipe/              # Recipe build system
│   │   ├── spec.py          # Pydantic models for meta.yaml recipe specs
│   │   ├── builder.py       # RecipeBuilder — orchestrates recipe builds
│   │   ├── graph_builder.py # Dependency graph resolution for recipes
│   │   ├── loader.py        # Load and parse meta.yaml files
│   │   ├── skeleton.py      # Generate meta.yaml from PyPI package info
│   │   ├── cleanup.py       # Clean recipe build artifacts
│   │   ├── unvendor.py      # Remove test/example files from wheels
│   │   └── bash_runner.py   # Execute build/post scripts
│   ├── out_of_tree/         # Out-of-tree (user) build logic
│   │   ├── build.py         # Core out-of-tree build logic
│   │   ├── pypi.py          # Fetch/build packages from PyPI
│   │   ├── venv.py          # Pyodide venv creation and management
│   │   └── app_data.py      # Application data directory management
│   ├── vendor/              # Vendored third-party code (excluded from linting)
│   │   ├── loky.py          # CPU count utility
│   │   └── _pypabuild.py    # Modified pypa/build integration
│   ├── tools/               # Build toolchain files
│   │   ├── cmake/           # CMake toolchain for Emscripten cross-compilation
│   │   └── emscripten.meson.cross  # Meson cross-compilation file
│   ├── tests/               # Unit tests (pytest)
│   │   ├── conftest.py      # Shared fixtures (dummy_xbuildenv, mock_emscripten, etc.)
│   │   ├── recipe/          # Recipe subsystem tests
│   │   ├── _test_recipes/   # Test recipe fixtures (meta.yaml + source packages)
│   │   ├── _test_xbuildenv/ # Test xbuildenv archive fixtures
│   │   └── utils/           # Test utilities (mock shell scripts)
│   ├── build_env.py         # Build environment initialization and management
│   ├── common.py            # Shared utilities (MUST NOT import other pyodide_build modules except logger)
│   ├── config.py            # ConfigManager / CrossBuildEnvConfigManager
│   ├── constants.py         # Reusable constants (e.g., BASE_IGNORED_REQUIREMENTS)
│   ├── create_package_index.py # Generate pyodide-lock.json package index
│   ├── io.py                # YAML/JSON I/O helpers
│   ├── logger.py            # Rich-based logging (custom _Logger with stdout/stderr/success levels)
│   ├── pypabuild.py         # pypa/build integration for Wasm cross-compilation
│   ├── pywasmcross.py       # Compiler wrapper for cross-compiling C/C++/Fortran to Wasm
│   ├── spec.py              # Shared type definitions (_ExportTypes, _BuildSpecExports)
│   ├── uv_helper.py         # UV package manager integration
│   ├── views.py             # Display/formatting for CLI output (MetadataView)
│   ├── xbuildenv.py         # CrossBuildEnvManager — install/manage xbuildenvs
│   └── xbuildenv_releases.py # Cross-build environment release metadata
├── integration_tests/       # Integration tests (not run by default)
│   ├── Makefile             # `make test-recipe`, `make test-src`, etc.
│   ├── recipes/             # Curated test recipes (numpy, orjson, zlib, etc.)
│   ├── scripts/             # Shell scripts for venv integration tests
│   └── src/                 # Source build integration test scripts
├── pyproject.toml           # Project configuration (hatchling + hatch-vcs)
├── .pre-commit-config.yaml  # Pre-commit hooks (ruff, mypy, codespell, shellcheck)
├── CHANGELOG.md             # Keep a Changelog format, semver
```

---

## Development Setup

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in editable mode with test and resolve dependencies
pip install -e ".[test,resolve]"

# Run unit tests (excludes integration tests)
pytest pyodide_build -m "not integration"

# Run integration tests (requires xbuildenv + emsdk)
# Add [integration] to commit message to trigger in CI
pytest pyodide_build -m integration

# Run recipe integration tests
cd integration_tests && make test-recipe
```

## Testing

### Test Framework

- HTTP mocking via `pytest-httpserver`

### Test Organization

- Unit tests live in `pyodide_build/tests/` alongside the code
- Test files follow `test_*.py` naming
- Recipe-specific tests are in `pyodide_build/tests/recipe/`
- Integration test assets are in `integration_tests/`
- Test fixtures (recipes, xbuildenv archives) are in `_test_recipes/` and `_test_xbuildenv/`

### Key Test Fixtures (in `conftest.py`)

- `reset_env_vars` — Restores environment variables after each test
- `reset_cache` — Clears all `@cache`/`@lru_cache` decorated function caches
- `dummy_xbuildenv_url` — HTTP server serving a minimal test xbuildenv archive
- `dummy_xbuildenv` — Installs a minimal xbuildenv in tmp_path (required for most CLI tests)
- `mock_emscripten` — Creates fake `emcc`/`llvm-readobj` binaries on PATH
- `fake_xbuildenv_releases_compatible` / `fake_xbuildenv_releases_incompatible` — Fake release metadata

### Running Tests

```bash
# Unit tests only (fast, no external deps)
pytest pyodide_build -m "not integration"

# Integration tests (requires installed xbuildenv + emsdk)
pytest pyodide_build -m integration

# Specific test file
pytest pyodide_build/tests/test_cli.py

# Recipe integration tests
cd integration_tests && make test-recipe
cd integration_tests && make test-src
```

### Integration Test Trigger

Integration tests do NOT run on every PR. They run when:
- Commit message contains `[integration]`
- Push to `main` branch
- PR has the `integration` label

---

## CLI Architecture

### Framework: Click

- CLI commands use `click` (migrated from `typer` in v0.32.0, PR #287)
- Entry points are registered in `pyproject.toml` under `[project.entry-points."pyodide.cli"]`
- The actual CLI is dispatched through `pyodide-cli` package (separate package)
- CLI testing uses `click.testing.CliRunner`

### CLI Pattern

```python
import click

@click.command()  # or @click.group(invoke_without_command=True)
@click.argument("name")
@click.option("--flag", "-f", default=..., help="...")
def main(name: str, flag: str) -> None:
    """Docstring becomes the help text.

    \b
    Arguments:
        NAME: description of argument
    """
    # implementation
```

### Adding a New CLI Command

1. Create `pyodide_build/cli/<command>.py` with a click command or group
2. Register the entry point in `pyproject.toml` under `[project.entry-points."pyodide.cli"]`
3. Add tests in `pyodide_build/tests/test_cli_<command>.py`
4. Use `click.testing.CliRunner` for testing

---

## Key Patterns and Conventions

### Pydantic Models for Specs

- Recipe specs (`meta.yaml`) are validated using Pydantic v2 models in `pyodide_build/recipe/spec.py`
- Models use `ConfigDict(extra="forbid")` to catch typos in YAML keys
- Field aliases map YAML keys to Python names (e.g., `Field(alias="top-level")`)
- Custom validators via `@pydantic.model_validator(mode="after")`

### Configuration System

- `ConfigManager` loads config from: defaults → Makefile.envs → pyproject.toml `[tool.pyodide.build]` → env vars
- `CrossBuildEnvConfigManager` extends `ConfigManager` with cross-build env vars from Makefile.envs
- Config variables are mapped between Python keys and env var names via `BUILD_KEY_TO_VAR` / `BUILD_VAR_TO_KEY`
- Exposed CLI configs are in `PYODIDE_CLI_CONFIGS` dict
- Use `$(VAR)` syntax for environment variable substitution in config values

### Logging

- Use `from pyodide_build.logger import logger` — custom Rich-based logger
- Available levels: `logger.debug()`, `logger.info()`, `logger.stdout()`, `logger.stderr()`, `logger.warning()`, `logger.error()`, `logger.success()`
- **Do NOT use f-strings in log calls** — use `%s` format (enforced by `G004` ruff rule)
  - ✅ `logger.info("Building %s", package_name)`
  - ❌ `logger.info(f"Building {package_name}")`

### Subprocess Execution

- Use `common.run_command()` for subprocess calls — it handles logging, error messages, and non-zero exit codes
- Do not call `subprocess.run()` directly in new code

### Import Rules

- `common.py` MUST NOT import other `pyodide_build` modules except `logger` (to avoid circular imports)
- Always use absolute imports: `from pyodide_build.xxx import yyy`
- Relative imports are banned project-wide (`ban-relative-imports = "all"` in ruff config)

### Path Handling

- Use `pathlib.Path` throughout, not `os.path`
- Platform awareness: `IS_WIN = sys.platform == "win32"` from `common.py`
- The xbuildenv path resolution checks: `PYODIDE_XBUILDENV_PATH` env → `pyproject.toml` config → `platformdirs` cache dir → cwd

### Cross-build Environment (xbuildenv)

- `CrossBuildEnvManager` in `xbuildenv.py` manages xbuildenv lifecycle (install, uninstall, use, version)
- Xbuildenv archives are downloaded from GitHub releases metadata
- Build flags come from `Makefile.envs` (parsed by `make` on Unix, internal parser on Windows)
- Emscripten SDK is installed separately via `pyodide xbuildenv install-emscripten`

---

## Recipe System (meta.yaml)

### Recipe Format

Recipes live in `packages/<name>/meta.yaml` (in pyodide main repo) or `integration_tests/recipes/<name>/meta.yaml` (in this repo). Structure:

```yaml
package:
  name: <package-name>
  version: <version>
  tag: [<optional-tags>]
  top-level: [<import-names>]

source:
  url: <sdist-url>      # or path: <local-path>
  sha256: <checksum>     # required if url is set
  patches: [<patch-files>]

build:
  cflags: |
    <extra-cflags>
  ldflags: |
    <extra-ldflags>
  backend-flags: |
    <pip/build-backend config>
  post: |
    <post-build-shell-script>
  cross-build-env: true  # install into xbuildenv
  cross-build-files:
    - <files-to-include>

requirements:
  run:
    - <dependency>
  constraint:
    - <pip-constraint>

about:
  home: <url>
  PyPI: <url>
  summary: <description>
  license: <spdx-id>
```

---

## CI/CD

### GitHub Actions Workflows

**`main.yml` (CI):**
- Unit tests: Python 3.12, Ubuntu + macOS
- Integration tests: triggered by `[integration]` commit message, `integration` PR label, or push to `main`
- Integration test matrix: pip/uv installers, recipe/src tests, stable/minimum Pyodide versions
- Venv tests: Ubuntu, macOS, Windows
- Coverage: combined from unit + integration, uploaded to Codecov

**`release.yml` (CD):**
- Builds sdist/wheel via `pypa/build`
- Publishes to PyPI on GitHub release events (trusted publishing)
- Weekly scheduled builds (Monday 3am UTC)

## Build System

- **Build backend:** hatchling with `hatch-vcs` for version inference from git tags
- **Version:** Dynamic, derived from git tags (no hardcoded version in source)
- Tests are excluded from sdist (`/pyodide_build/tests` in `[tool.hatch.build.targets.sdist].exclude`)

---

## Common Pitfalls and Gotchas

1. **Circular imports in `common.py`**: This module must only import `logger` from `pyodide_build`. Adding other imports will cause circular import errors.

2. **Cache invalidation in tests**: Many functions use `@functools.cache`. Tests must use the `reset_cache` fixture or manually call `.cache_clear()` to avoid stale state between tests.

3. **Environment variable side effects**: Tests that modify `os.environ` must use the `reset_env_vars` fixture to restore state. Many build functions read env vars directly.

4. **Makefile.envs parsing**: On Unix, `make` parses `Makefile.envs`. On Windows, a fallback Python parser (`_parse_makefile_envs`) is used. These may behave differently for complex expressions.

5. **Integration tests need full setup**: Integration tests require an installed xbuildenv and Emscripten SDK. Unit tests mock these via `dummy_xbuildenv` and `mock_emscripten` fixtures.

6. **`pyodide` directory in repo root**: This is a submodule/copy of Pyodide runtime templates and tests, NOT the main Pyodide repository. Do not confuse with the `pyodide_build` package.

7. **`emsdk/` directory**: Created at runtime when installing Emscripten. Gitignored. Do not commit.

8. **Platform sensitivity**: The venv system and path handling must work on Linux, macOS, and Windows. Use `IS_WIN` checks and `pathlib.Path` for cross-platform compatibility.

9. **Logging format**: Always use `%s`-style formatting in logger calls, never f-strings (enforced by `G004` lint rule).

10. **Vendor code is frozen**: Files in `pyodide_build/vendor/` are copied from upstream projects. Do not modify directly — update from upstream source instead.
