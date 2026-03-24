# pyodide-build Documentation Plan

> Status: Draft
> Last updated: 2026-03-24

## Background

pyodide-build has virtually no user-facing documentation. The `docs/` directory contains an empty Sphinx skeleton, and the README is 12 lines. Relevant content currently lives on pyodide.org (scattered across the Pyodide project docs) — this will be migrated here, and pyodide.org will link to these docs instead.

This plan proposes a comprehensive documentation structure for pyodide-build as the **canonical source** for all package building documentation, following the [Diataxis framework](https://diataxis.fr/) (tutorials, how-to guides, reference, explanation).

### Target Audience

**Primary**: Python package maintainers who want their package to work in Pyodide/WebAssembly.
**Secondary**: Pyodide ecosystem contributors who author recipes.

pyodide-build docs are the **canonical home** for everything related to building, testing, and publishing Python packages for Pyodide. pyodide.org will link here for build-related content.

### Guiding Principles

1. **This is the canonical source** — All package building docs live here. Existing content on pyodide.org (building packages, out-of-tree builds, meta.yaml spec, CLI reference) will be migrated here, and pyodide.org will link to these docs instead.
2. **Lead with the happy path** — Quickstart should be 4 commands with a working result.
3. **Explain the "why" before the "how"** — Concepts page before CLI reference.
4. **Real-world examples** — Use NumPy, pandas, matplotlib configs as proof points, not hypothetical examples.
5. **Progressive disclosure** — 80% of users need Getting Started + CI guide + Publishing. The rest serves progressively smaller audiences.

---

## Document Structure

### Part I — Getting Started

#### 1. Overview (`index.md`)

The landing page. Sets expectations and orients the reader.

- What is pyodide-build? (one paragraph: "the `python -m build` for WebAssembly")
- Who is this for? (Python package maintainers, not Pyodide end-users)
- Ecosystem map diagram: pyodide-build -> pyodide-cli -> Emscripten -> Pyodide runtime
- Quick links to the three main workflows: Build -> Test -> Ship

#### 2. Installation (`getting-started/installation.md`)

- `pip install pyodide-build` (also: `pipx install`, `uv tool install`, `uvx`)
- Version requirements: Python >= 3.12, Node.js (for venv testing)
- Verify installation: `pyodide --version`
- Optional extras: `pip install pyodide-build[resolve]` for dependency resolution

#### 3. Concepts (`getting-started/concepts.md`)

Explain the mental model before showing commands. This addresses a major user pain point — people don't understand what xbuildenv is or why they need Emscripten.

- **Why cross-compilation?** Python packages with C extensions must be compiled for the target platform. Pyodide's target is Emscripten/WebAssembly.
- **The cross-build environment (xbuildenv)**: pre-built CPython headers, sysconfig data, and package stubs. Analogous to a sysroot in cross-compilation.
- **Emscripten SDK**: the compiler toolchain that turns C/C++ into WebAssembly. Managed automatically by pyodide-build.
- **Platform tags**: `pyemscripten_2025_0_wasm32` — what each part means, ABI versioning, the PEP 783 specification.
- **Side-by-side comparison**: `python -m build` vs `pyodide build` — what's the same, what's different.

#### 4. Quick Start (`getting-started/quickstart.md`)

The "5-minute" path. Build a package with a C extension for Pyodide.

- Callout: **Pure-Python packages don't need pyodide-build.** A pure-Python wheel built with `python -m build` (or any standard build frontend) is already compatible with Pyodide — no special tooling required. pyodide-build is for packages that contain C, C++, Rust, or Fortran extensions.

```
pip install pyodide-build
pyodide xbuildenv install
pyodide build .
ls dist/   # -> your_package-1.0-cp313-cp313-pyemscripten_2025_0_wasm32.whl
```

- Step 1: Install pyodide-build
- Step 2: Install the cross-build environment (one sentence explanation, link to Concepts)
- Step 3: Build — show the three source modes:
  - From current directory (like `python -m build`)
  - From PyPI (`pyodide build numpy==2.0`)
  - From URL (`pyodide build https://...tar.gz`)
- Step 4: Inspect the output wheel — what the platform tag means
- Callout box: "From `python -m build` to `pyodide build`" migration comparison

#### 5. Testing with `pyodide venv` (`getting-started/testing.md`)

Immediately after building, show how to verify the wheel works.

```
pyodide venv .venv-pyodide
source .venv-pyodide/bin/activate
pip install dist/your_package-*.whl
python -c "import your_package; print('works!')"
```

- What `pyodide venv` does differently from `python -m venv` (Node.js + Pyodide runtime as interpreter)
- Installing your wheel — pip inside the venv only accepts Wasm-compatible wheels
- Running tests: `python -m pytest` inside the venv runs on Pyodide/Node.js
- "What's weird about this venv": pip runs on host Python, but `python` invokes Pyodide/Node.js
- Note: requires Node.js
- Windows notes (`Scripts\activate` path, known quirks)

---

### Part II — Tutorials (learning-oriented, end-to-end walkthroughs)

Each tutorial walks through a complete scenario from start to finish.

#### 6. Tutorial: Package with C Extension (`tutorials/c-extension.md`)

- Setuptools/distutils package with a `.c` file
- What happens under the hood: pywasmcross intercepts `gcc` calls and redirects to `emcc`
- Export modes explained in context: `pyinit` (default) vs `requested` vs `whole_archive`
- Debugging a build failure (practical example with a real error)

#### 7. Tutorial: CMake/Meson Package (`tutorials/cmake-meson.md`)

- How to pass the cross-compilation files:
  - `pyodide config get meson_cross_file`
  - `pyodide config get cmake_toolchain_file`
- The `-C setup-args=--cross-file=...` pattern
- `--no-isolation` mode for complex build environments
- pybind11, nanobind, and Cython examples
- scikit-build-core integration

#### 8. Tutorial: Rust Package (PyO3/Maturin) (`tutorials/rust.md`)

- Rust toolchain auto-setup (`wasm32-unknown-emscripten` target)
- Key environment variables: `CARGO_BUILD_TARGET`, `RUSTFLAGS`, `PYO3_CROSS_*`
- `pyodide config get rust_toolchain` and `rustflags`
- Example: building a simple PyO3 extension

#### 9. Tutorial: Building with Dependencies (`tutorials/dependencies.md`)

- Installing the resolve extra: `pip install pyodide-build[resolve]`
- `pyodide build --build-dependencies` — auto-resolves and builds the dependency tree
- Skipping built-in packages (`--skip-built-in-packages`) and specific deps (`--skip-dependency <name>`)
- Building from a requirements file: `-r requirements.txt`
- Exporting resolved dependencies: `--output-lockfile`
- Practical example: building a package that needs numpy + scipy at runtime

---

### Part III — How-to Guides (task-oriented, for working developers)

Each guide solves a specific task. Assumes the reader has basic familiarity from Parts I-II.

#### 10. CI with cibuildwheel (`how-to/cibuildwheel.md`)

This is likely the **highest-value section** after the quickstart — many users encounter pyodide-build through cibuildwheel.

- Why cibuildwheel: build for Linux, macOS, Windows, **and** Pyodide in one CI config
- Pyodide support history: added in cibuildwheel v2.19.0, current at v3.4.0
- Platform identifiers: `cp312-pyodide_wasm32`, `cp313-pyodide_wasm32`
- Minimal `pyproject.toml` configuration:
  ```toml
  [tool.cibuildwheel]
  build = ["cp312-*", "cp313-*"]

  [tool.cibuildwheel.pyodide]
  test-command = "python -m pytest {project}/tests -x"
  test-requires = ["pytest"]
  ```
- Complete GitHub Actions workflow (copy-paste-ready, Pyodide as separate job)
- Key constraints:
  - Must explicitly set `CIBW_PLATFORM=pyodide` — auto-detection won't select it
  - `pip` frontend NOT supported — only `build` or `build[uv]`
  - Linux/macOS only — cannot build on Windows runners
  - Tests must use `python -m pytest`, not bare `pytest`
  - No default wheel repair — most projects set `repair-wheel-command = ""`
- Real-world config examples from: NumPy, pandas, matplotlib, Rust+Pyodide projects
- Link to cibuildwheel's Pyodide platform docs

#### 11. CI without cibuildwheel (`how-to/ci-direct.md`)

For projects that don't use cibuildwheel or want more control.

- Direct GitHub Actions workflow using `pyodide build` commands
- Matrix builds across Pyodide versions
- Caching the xbuildenv for faster CI runs
- Testing step with `pyodide venv`

#### 12. Publishing Wasm Wheels (`how-to/publishing.md`)

- Publishing to PyPI: standard `twine upload` / trusted publishing works — Wasm wheels are regular wheels
- Platform tag format: `pyemscripten_YYYY_P_wasm32` (per PEP 783; older versions used `pyodide_YYYY_P_wasm32`)
- How Pyodide users consume your wheel: `micropip.install("your-package")` in the browser, or `pip install` inside a `pyodide venv`
- Complete CI example: build with cibuildwheel -> publish with trusted publishing
- Admonition (single note): PEP 783 formalizes the Emscripten platform tags — link to the PEP for details on the platform specification

#### 13. Migrating from Native Builds (`how-to/migrate.md`)

Addresses a major user pain point: "I already build native wheels, what do I change?"

- Side-by-side comparison: `python -m build` workflow vs `pyodide build` workflow
- Common issues when adapting:
  - `pthreads` (not supported in Wasm)
  - SIMD intrinsics / inline assembly
  - Filesystem assumptions (limited in Wasm)
  - Networking code (no sockets in Wasm)
  - 64-bit integer assumptions
- Conditional compilation: detecting Pyodide at build time:
  - C/C++: `#ifdef __EMSCRIPTEN__`
  - Python: `os.environ.get("PYODIDE")` (build-time), `sys.platform == "emscripten"` (runtime)

#### 14. Managing Cross-Build Environments (`how-to/xbuildenv.md`)

- Install: `pyodide xbuildenv install [version]`
- List installed: `pyodide xbuildenv versions`
- Switch active: `pyodide xbuildenv use <version>`
- Uninstall: `pyodide xbuildenv uninstall [version]`
- Search available: `pyodide xbuildenv search [--all] [--json]`
- Path resolution order: `PYODIDE_XBUILDENV_PATH` env var -> pyproject.toml -> platform cache dir -> cwd
- Pinning a version in pyproject.toml (`xbuildenv_path` or `default_cross_build_env_url`)
- Emscripten SDK management: `pyodide xbuildenv install-emscripten`
- Lazy cross-build package installation (packages installed on first use, not eagerly)

#### 15. Customizing Compiler Flags (`how-to/compiler-flags.md`)

For power users who need to tweak the build.

- Default flags and what they do:
  - `-Oz` (optimize for size), `SIDE_MODULE=1` (Emscripten side module)
- Overriding via `pyproject.toml` `[tool.pyodide.build]`:
  ```toml
  [tool.pyodide.build]
  cflags = "$(CFLAGS_BASE) -I$(PYTHONINCLUDE) -O2"
  ```
- Overriding via environment variables: `CFLAGS`, `CXXFLAGS`, `LDFLAGS` (appended to defaults)
- What pywasmcross silently filters out:
  - `-pthread` (threading disabled)
  - macOS-specific flags (`-bundle`, `-undefined dynamic_lookup`)
  - x86 SIMD flags (`-mpopcnt`, `-mno-sse2`, etc.)
  - Fortran-specific flags
- Fortran handling: `gfortran` calls are converted via f2c translation
- CMake toolchain file and Meson cross-file integration

#### 16. Debugging Build Failures (`how-to/debugging.md`)

Systematic troubleshooting guide organized by failure phase.

- **Phase 1: Environment errors**
  - "No Emscripten compiler found" -> install xbuildenv
  - "Version X is not compatible" -> Python/pyodide-build version mismatch
  - "local Python version does not match" -> Python changed after xbuildenv install
- **Phase 2: Compilation errors**
  - Missing headers -> check include paths
  - Incompatible C/C++ code -> pthread, SIMD, inline assembly
  - Function pointer cast errors -> Wasm strict typing
- **Phase 3: Link errors**
  - Missing symbols -> check export mode (`pyinit` vs `requested` vs `whole_archive`)
  - Duplicate symbols -> wasm-ld doesn't allow duplicate `-l` flags (pywasmcross deduplicates)
- **Phase 4: Build system errors**
  - CMake/Meson configuration failures -> cross-file not passed
  - scikit-build-core issues -> `CMAKE_EXECUTABLE` env var
- **Phase 5: Runtime errors**
  - "Wheel works in browser but fails in venv" -> testing environment differences

---

### Part IV — Recipe System (for Pyodide ecosystem contributors)

Separate audience — most users never need this.

#### 17. Recipe Authoring (`recipes/authoring.md`)

- What is a recipe? A `meta.yaml` file that declares how to build a package for Pyodide's package ecosystem.
- When do you need a recipe vs. just `pyodide build`?
  - Recipe: contributing to the Pyodide built-in packages set
  - `pyodide build`: building your own package for distribution
- Generating a recipe: `pyodide skeleton pypi <name>`
- `meta.yaml` walkthrough with annotated example
- Build types: `package`, `static_library`, `shared_library`, `cpython_module`
- Source handling: URL vs local path, sha256 checksums, patches, extras
- Build customization: `cflags`, `ldflags`, `backend-flags`, `script`, `post`
- Requirements: `run` (runtime), `host` (build-time), `executable` (e.g., rustc), `constraint`
- Cross-build support: `cross-build-env`, `cross-build-files`
- Test imports validation

#### 18. Building Recipes (`recipes/building.md`)

- `pyodide build-recipes` — dependency graph resolution + parallel builds
- `pyodide build-recipes-no-deps` — building individual packages without resolution
- `pyodide clean recipes` — cleaning build artifacts
- Recipe lifecycle management:
  - `pyodide skeleton enable <name>` / `disable <name> -m "reason"`
  - `pyodide skeleton pin <name> -m "reason"`

---

### Part V — Reference (information-oriented, exhaustive)

#### 19. CLI Reference (`reference/cli.md`)

Complete option tables for every command. Consider auto-generating from Click's `--help` output.

Commands to document:
- `pyodide build` — all arguments and options with defaults, env var mappings
- `pyodide venv` — arguments and options
- `pyodide xbuildenv` — all subcommands: `install`, `version`, `versions`, `uninstall`, `use`, `search`, `install-emscripten`
- `pyodide config` — subcommands: `list`, `get`
- `pyodide build-recipes` — all options
- `pyodide build-recipes-no-deps` — all options
- `pyodide skeleton` — subcommands: `pypi`, `enable`, `disable`, `pin`
- `pyodide py-compile` — arguments and options
- `pyodide clean recipes` — arguments and options

#### 20. Configuration Reference (`reference/configuration.md`)

- Configuration precedence: env vars > pyproject.toml > Makefile.envs > defaults
- Complete `[tool.pyodide.build]` key reference table:

  | Key | Env Var | Default | Description |
  |---|---|---|---|
  | `cflags` | `SIDE_MODULE_CFLAGS` | `$(CFLAGS_BASE) -I$(PYTHONINCLUDE) -Oz` | C compiler flags |
  | `cxxflags` | `SIDE_MODULE_CXXFLAGS` | `$(CFLAGS_BASE) -Oz` | C++ compiler flags |
  | `ldflags` | `SIDE_MODULE_LDFLAGS` | `$(LDFLAGS_BASE) -s SIDE_MODULE=1 -Oz` | Linker flags |
  | `rustflags` | `RUSTFLAGS` | `-C link-arg=-sSIDE_MODULE=2 ...` | Rust compiler flags |
  | `rust_toolchain` | `RUST_TOOLCHAIN` | `nightly-2025-02-01` | Rust toolchain version |
  | `meson_cross_file` | `MESON_CROSS_FILE` | `<tools>/emscripten.meson.cross` | Meson cross file |
  | `xbuildenv_path` | `PYODIDE_XBUILDENV_PATH` | platform cache dir | xbuildenv location |
  | `ignored_build_requirements` | `IGNORED_BUILD_REQUIREMENTS` | `patchelf oldest-supported-numpy` | Build deps to ignore |
  | ... | ... | ... | ... |

- Environment variables reference table (all `PYODIDE_*` vars)
- `$(VAR)` substitution syntax in config values

#### 21. meta.yaml Reference (`reference/meta-yaml.md`)

- Complete field reference with types, defaults, validation rules
- All sections: `package`, `source`, `build`, `requirements`, `test`, `about`, `extra`
- Validation error messages and what triggers them
- Migrated from pyodide.org's meta.yaml spec — this becomes the canonical reference

#### 22. Platform Tags & Compatibility (`reference/platform.md`)

- Platform version <-> Python version <-> Emscripten version matrix:

  | Platform Tag | Python | Notes |
  |---|---|---|
  | `pyodide_2024_0_wasm32` | 3.12 | Legacy tag name |
  | `pyemscripten_2025_0_wasm32` | 3.13 | PEP 783 standardized name |
  | `pyemscripten_2026_0_wasm32` | 3.14 | PEP 783 standardized name |

- Wheel naming format explained
- PEP 783 (Emscripten/WebAssembly platform) — the formal specification for these tags
- ABI compatibility rules: wheels are NOT cross-version compatible
- cibuildwheel identifier mapping: `cp312-pyodide_wasm32`, `cp313-pyodide_wasm32`

---

### Part VI — Explanation (understanding-oriented)

#### 23. How pyodide-build Works (`explanation/architecture.md`)

For users who want to understand the internals.

- The build pipeline: source -> pypa/build -> pywasmcross wrapper -> emcc -> .wasm -> wheel
- The compiler wrapper (pywasmcross): intercepts cc/gcc/g++ calls, translates flags, redirects to emcc/em++
- Symlinks created: `cc`, `c++`, `ld`, `ar`, `cmake`, `meson`, `cargo`, `gfortran`, etc.
- Why `SIDE_MODULE` and symbol exports matter
- Flag filtering: what gets removed and why (pthreads, macOS flags, SIMD, etc.)
- Fortran-to-C translation pipeline (f2c)

#### 24. The Pyodide Ecosystem (`explanation/ecosystem.md`)

- Package relationships:
  - `pyodide-cli`: the dispatcher that routes `pyodide <cmd>` to plugins
  - `pyodide-build`: registers all build commands as pyodide-cli plugins
  - `pyodide-lock`: the lockfile format library
  - `auditwheel-emscripten`: wheel repair/inspection for Wasm wheels
  - `micropip`: runtime package installer (browser-side)
- How users consume your wheel: `micropip.install()` in the browser or `pip install` in a pyodide venv
- The relationship between pyodide-build and the main Pyodide project

---

### Appendix

#### 25. Troubleshooting (`troubleshooting.md`)

Organized by error message for searchability.

- "No Emscripten compiler found" -> install xbuildenv or check `PYODIDE_SKIP_EMSCRIPTEN_INSTALL`
- "Version X is not compatible with the current environment" -> Python/pyodide-build version mismatch, use `--force`
- "local Python version does not match" -> Python changed after xbuildenv install, reinstall xbuildenv
- "MissingOptionalDependencyError" -> `pip install pyodide-build[resolve]`
- "Can't find package: <spec>" -> PyPI resolution failure
- "PIP_CONSTRAINT contains spaces" -> move project to a path without spaces
- Build failures with C extensions -> check filtered flags, threading, SIMD
- Wheel is too large -> compression level, `unvendor-tests`, `-Oz` vs `-O2` tradeoff
- Windows-specific issues -> Makefile.envs parsing limitations

#### 26. FAQ (`faq.md`)

- "Which packages work with Pyodide?" — Pure Python = always. C extensions = usually. Threading/multiprocessing = no. Filesystem-heavy = maybe. Networking = no.
- "What's the difference between `pyodide build` and `pyodide build-recipes`?" — Out-of-tree single package build vs in-tree recipe system with dependency resolution.
- "Can I use maturin/meson-python/scikit-build-core?" — Yes, with cross-file configuration.
- "Do I need the full Pyodide repo?" — No, pyodide-build is standalone.
- "What Node.js version do I need?" — v22+ recommended (for pyodide venv).
- "Should I use `pyodide build` directly or cibuildwheel?" — cibuildwheel if you already build native wheels and want one CI config. `pyodide build` directly if you only target Pyodide or want more control.
- "Can I publish Wasm wheels to PyPI?" — Yes. Upload with `twine` or trusted publishing like any other wheel.

#### 27. Changelog

Link to `CHANGELOG.md`. Highlight breaking changes between versions:
- **Unreleased**: `-Oz` replaces `-O2` default, `vendor_sharedlib` defaults to `true`
- **v0.33.0**: Emscripten auto-install
- **v0.32.0**: typer -> click CLI framework migration
- **v0.31.0**: Windows support for `pyodide venv`
- **v0.30.0**: uv support, xbuildenv moved to cache dir

---

## Reader Journey Map

| Reader Profile | Sections They Need | Time |
|---|---|---|
| "I have 5 minutes, show me it works" | 1, 2, 4, 5 | 10 min |
| "I have a C extension package" | + 6, 7 | + 30 min |
| "I want CI for my project" | + 10 or 11 | + 15 min |
| "I want to publish" | + 12 | + 10 min |
| "My build is failing" | 16, 25 | lookup |
| "I need custom compiler flags" | 15, 20 | lookup |
| "I want to contribute a Pyodide recipe" | 17, 18, 21 | 30 min |
| "I want to understand the internals" | 23, 24 | 30 min |

**80% of users** need only: **Getting Started (1-5) + CI guide (10) + Publishing (12)**.

## Implementation Notes

- The `docs/` directory already has Sphinx + myst-parser configured (`.readthedocs.yaml`, `conf.py`). Write in Markdown (`.md`), not reStructuredText.
- Consider auto-generating the CLI Reference (Section 20) from Click's `--help` output to stay in sync.
- Real-world examples (NumPy, pandas, matplotlib cibuildwheel configs) should be kept up-to-date or link to the source repos directly.
- PEP 783 is assumed accepted throughout the docs. A single admonition in the Publishing guide (Section 13) links to the PEP for the formal platform specification. No scattered caveats elsewhere.
- **Migration from pyodide.org**: The following pyodide.org pages should be migrated here and replaced with redirects/links:
  - `development/building-packages.html` → Sections 4, 6, 10
  - `development/building-packages-from-source.html` → Sections 6, 7, 16
  - `development/meta-yaml.html` → Section 21
  - `usage/api/pyodide-cli.html` (build-related commands) → Section 19
