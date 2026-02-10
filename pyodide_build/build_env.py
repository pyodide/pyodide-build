# This file contains functions for managing the Pyodide build environment.

import dataclasses
import functools
import os
import re
import subprocess
import sys
from collections.abc import Iterator, Sequence
from contextlib import nullcontext, redirect_stdout
from io import StringIO
from pathlib import Path

from packaging.tags import Tag, compatible_tags, cpython_tags

from pyodide_build import __version__
from pyodide_build.common import default_xbuildenv_path, search_pyproject_toml, to_bool

RUST_BUILD_PRELUDE = """
rustup default ${RUST_TOOLCHAIN}
"""


@dataclasses.dataclass(eq=False, order=False, kw_only=True)
class BuildArgs:
    """
    Common arguments for building a package.
    """

    pkgname: str = ""
    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""
    target_install_dir: str = ""  # The path to the target Python installation
    host_install_dir: str = ""  # Directory for installing built host packages.
    builddir: str = ""  # The path to run pypa/build


def init_environment(
    *, quiet: bool = False, xbuildenv_path: Path | None = None
) -> None:
    """
    Initialize Pyodide build environment.
    This function needs to be called before any other Pyodide build functions.

    Parameters
    ----------
    quiet
        If True, do not print any messages
    xbuildenv_path
        Path to the cross-build environment directory. If None, the default
        location will be used.
    """

    # Already initialized
    if "PYODIDE_ROOT" in os.environ:
        return

    root = search_pyodide_root(Path.cwd())
    if not root:  # Not in Pyodide tree
        root = _init_xbuild_env(quiet=quiet, xbuildenv_path=xbuildenv_path)

    os.environ["PYODIDE_ROOT"] = str(root)


def _init_xbuild_env(
    *, quiet: bool = False, xbuildenv_path: Path | None = None
) -> Path:
    """
    Initialize the build environment for out-of-tree builds.

    Parameters
    ----------
    quiet
        If True, do not print any messages
    xbuildenv_path
        Path to the cross-build environment directory. If None, the default location will be used.

    Returns
    -------
        The path to the Pyodide root directory inside the xbuild environment
    """
    from pyodide_build.xbuildenv import CrossBuildEnvManager  # avoid circular import

    xbuildenv_path = xbuildenv_path or default_xbuildenv_path()
    context = redirect_stdout(StringIO()) if quiet else nullcontext()
    with context:
        manager = CrossBuildEnvManager(xbuildenv_path)
        matches, _ = manager.version_marker_matches()
        if not matches:
            manager.install()
        matches, errmsg = manager.version_marker_matches()
        if not matches:
            raise ValueError(errmsg)

        return manager.pyodide_root


@functools.cache
def get_pyodide_root() -> Path:
    init_environment()
    return Path(os.environ["PYODIDE_ROOT"])


def search_pyodide_root(curdir: str | Path, *, max_depth: int = 10) -> Path | None:
    """
    Recursively search for the root of the Pyodide repository,
    by looking for the pyproject.toml file in the parent directories
    which contains the [tool._pyodide] section.
    """
    pyproject_path, pyproject_file = search_pyproject_toml(curdir, max_depth)

    if pyproject_path is None or pyproject_file is None:
        return None

    if "tool" in pyproject_file and "_pyodide" in pyproject_file["tool"]:
        return pyproject_path.parent

    return None


def in_xbuildenv() -> bool:
    pyodide_root = get_pyodide_root()
    return pyodide_root.name == "pyodide-root"


def _load_config_manager():
    """Lazily load ConfigManager so that we can avoid circular imports."""
    from pyodide_build.config import ConfigManager, CrossBuildEnvConfigManager

    return ConfigManager, CrossBuildEnvConfigManager


@functools.cache
def get_build_environment_vars(pyodide_root: Path) -> dict[str, str]:
    """
    Get common environment variables for the in-tree and out-of-tree build.
    """
    _, CrossBuildEnvConfigManager = _load_config_manager()

    config_manager = CrossBuildEnvConfigManager(pyodide_root)
    env = config_manager.to_env()

    env.update(
        {
            # This environment variable is used for packages to detect if they are built
            # for pyodide during build time
            "PYODIDE": "1",
            # This is the legacy environment variable used for the aforementioned purpose
            "PYODIDE_PACKAGE_ABI": "1",
            "PYTHONPATH": env["HOSTSITEPACKAGES"],
        }
    )

    return env


@functools.cache
def get_host_build_environment_vars() -> dict[str, str]:
    ConfigManager, _ = _load_config_manager()
    manager = ConfigManager()
    return manager.to_env()


def get_build_flag(name: str) -> str:
    """
    Get a value of a build flag.
    """
    pyodide_root = get_pyodide_root()
    build_vars = get_build_environment_vars(pyodide_root)
    if name not in build_vars:
        raise ValueError(f"Unknown build flag: {name}")

    return build_vars[name]


def get_host_build_flag(name: str) -> str:
    """
    Get a value of a build flag without accessing the cross-build environment.
    """
    build_vars = get_host_build_environment_vars()
    if name not in build_vars:
        raise ValueError(f"Unknown build flag: {name}")

    return build_vars[name]


def get_pyversion_major() -> str:
    return get_build_flag("PYMAJOR")


def get_pyversion_minor() -> str:
    return get_build_flag("PYMINOR")


def get_pyversion_major_minor() -> str:
    return f"{get_pyversion_major()}.{get_pyversion_minor()}"


def get_pyversion() -> str:
    return f"python{get_pyversion_major_minor()}"


def get_hostsitepackages() -> str:
    return get_build_flag("HOSTSITEPACKAGES")


@functools.cache
def get_unisolated_packages() -> list[str]:
    # TODO: Remove this function (and use remote package index)
    # https://github.com/pyodide/pyodide-build/issues/43
    PYODIDE_ROOT = get_pyodide_root()

    unisolated_file = PYODIDE_ROOT / "unisolated.txt"
    if unisolated_file.exists():
        # in xbuild env, read from file
        unisolated_packages = unisolated_file.read_text().splitlines()
    else:
        from pyodide_build.recipe.loader import load_all_recipes

        unisolated_packages = []
        recipe_dir = PYODIDE_ROOT / "packages"
        recipes = load_all_recipes(recipe_dir)
        for name, config in recipes.items():
            if config.build.cross_build_env:
                unisolated_packages.append(name)

    return unisolated_packages


def platform() -> str:
    emscripten_version = get_build_flag("PYODIDE_EMSCRIPTEN_VERSION")
    version = emscripten_version.replace(".", "_")
    return f"emscripten_{version}_wasm32"


def wheel_platform() -> str:
    abi_version = get_build_flag("PYODIDE_ABI_VERSION")
    return f"pyodide_{abi_version}_wasm32"


def pyodide_tags_() -> Iterator[Tag]:
    """
    Returns the sequence of tag triples for the Pyodide interpreter.

    The sequence is ordered in decreasing specificity.
    """
    PYMAJOR = get_pyversion_major()
    PYMINOR = get_pyversion_minor()
    PLATFORMS = [platform(), wheel_platform()]
    python_version = (int(PYMAJOR), int(PYMINOR))
    yield from cpython_tags(platforms=PLATFORMS, python_version=python_version)
    yield from compatible_tags(platforms=PLATFORMS, python_version=python_version)
    # Following line can be removed once packaging 22.0 is released and we update to it.
    yield Tag(interpreter=f"cp{PYMAJOR}{PYMINOR}", abi="none", platform="any")


@functools.cache
def pyodide_tags() -> Sequence[Tag]:
    return list(pyodide_tags_())


def replace_so_abi_tags(wheel_dir: Path) -> None:
    """Replace native abi tag with emscripten abi tag in .so file names"""
    import sysconfig

    build_soabi = sysconfig.get_config_var("SOABI")
    assert build_soabi
    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    assert ext_suffix
    build_triplet = "-".join(build_soabi.split("-")[2:])
    host_triplet = get_build_flag("PLATFORM_TRIPLET")
    for file in wheel_dir.glob(f"**/*{ext_suffix}"):
        file.rename(file.with_name(file.name.replace(build_triplet, host_triplet)))


def emscripten_version() -> str:
    return get_build_flag("PYODIDE_EMSCRIPTEN_VERSION")


def get_emscripten_version_info() -> str:
    """Extracted for testing purposes."""
    return subprocess.run(
        ["emcc", "-v"], capture_output=True, encoding="utf8", check=True
    ).stderr


# Env variables that are set by emsdk_env.sh
EMSDK_ENV_VARS = {
    "PATH",
    "EMSDK",
    "EMSDK_NODE",
    "EMSDK_PYTHON",
    "SSL_CERT_FILE",
}


def activate_emscripten_env(emsdk_dir: Path) -> dict[str, str]:
    """
    Source emsdk_env.sh and return the resulting environment variables.

    Parameters
    ----------
    emsdk_dir
        Path to the emsdk directory containing emsdk_env.sh

    Returns
    -------
    dict[str, str]
        Dictionary of environment variables set by emsdk_env.sh
    """
    emsdk_env_script = emsdk_dir / "emsdk_env.sh"
    if not emsdk_env_script.exists():
        raise FileNotFoundError(f"emsdk_env.sh not found at {emsdk_env_script}")

    # Source emsdk_env.sh and capture the resulting environment
    result = subprocess.run(
        ["bash", "-c", f"source {emsdk_env_script} > /dev/null 2>&1 && env"],
        capture_output=True,
        encoding="utf8",
        check=True,
    )

    # Parse the environment variables from output
    env_vars: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            if key in EMSDK_ENV_VARS:
                env_vars[key] = value

    return env_vars


def ensure_emscripten(skip_install: bool = False) -> None:
    """
    Ensure Emscripten is available and correctly versioned.

    If emcc is not found and auto-install is not skipped, this function will
    automatically install Emscripten using CrossBuildEnvManager and activate it.

    Parameters
    ----------
    skip_install
        If True, skip auto-installation when emcc is not found.
        Also controlled by PYODIDE_SKIP_EMSCRIPTEN_INSTALL env var.

    Raises
    ------
    RuntimeError
        If emcc is not found and auto-install is skipped, or if version mismatch.
    """
    from pyodide_build.logger import logger
    from pyodide_build.xbuildenv import CrossBuildEnvManager  # avoid circular import

    # Check if auto-install should be skipped
    env_skip = os.environ.get("PYODIDE_SKIP_EMSCRIPTEN_INSTALL", "")
    should_skip_install = skip_install or to_bool(env_skip)

    skip = get_build_flag("SKIP_EMSCRIPTEN_VERSION_CHECK")
    if to_bool(skip):
        return

    needed_version = emscripten_version()

    try:
        version_info = get_emscripten_version_info()
    except FileNotFoundError:
        if should_skip_install:
            raise RuntimeError(
                f"No Emscripten compiler found. Need Emscripten version {needed_version}"
            ) from None

        # Get the xbuildenv path from the already-initialized pyodide root
        # pyodide_root is at {xbuild_root}/xbuildenv/pyodide-root
        # so xbuild_root is pyodide_root.parent.parent
        pyodide_root = get_pyodide_root()
        xbuild_root = pyodide_root.parent.parent
        emsdk_dir = xbuild_root / "emsdk"
        emsdk_env_script = emsdk_dir / "emsdk_env.sh"

        if emsdk_env_script.exists():
            logger.info("Emscripten found but not activated, activating...")
        else:
            logger.info("Emscripten not found, installing...")
            manager = CrossBuildEnvManager(xbuild_root.parent)
            emsdk_dir = manager.install_emscripten(needed_version)

        env_vars = activate_emscripten_env(emsdk_dir)
        os.environ.update(env_vars)

        try:
            version_info = get_emscripten_version_info()
        except FileNotFoundError:
            raise RuntimeError(
                f"Emscripten activation failed. emcc not found after setup. "
                f"Need Emscripten version {needed_version}"
            ) from None

    # Parse and check version
    installed_version = None
    try:
        for x in reversed(version_info.partition("\n")[0].split(" ")):
            # (X.Y.Z) or (X.Y.Z)-git
            match = re.match(r"(\d+\.\d+\.\d+)(-\w+)?", x)
            if match:
                installed_version = match.group(1)
                break
    except Exception:
        raise RuntimeError("Failed to determine Emscripten version.") from None

    if installed_version is None:
        raise RuntimeError("Failed to determine Emscripten version.")

    if installed_version != needed_version:
        raise RuntimeError(
            f"Incorrect Emscripten version {installed_version}. Need Emscripten version {needed_version}"
        )


def local_versions() -> dict[str, str]:
    """
    Returns the versions of the local Python interpreter and the pyodide-build.
    This information is used for checking compatibility with the cross-build environment.
    """
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "pyodide-build": __version__,
        # "emscripten": "TODO"
    }


def _create_constraints_file() -> str:
    # PIP_BUILD_CONSTRAINT takes precedence; fall back to PIP_CONSTRAINT for backward compatibility
    try:
        constraints = get_build_flag("PIP_BUILD_CONSTRAINT")
    except ValueError:
        try:
            constraints = get_build_flag("PIP_CONSTRAINT")
        except ValueError:
            return ""

    if not constraints:
        return ""

    if len(constraints.split(maxsplit=1)) > 1:
        raise ValueError(
            "PIP_BUILD_CONSTRAINT/PIP_CONSTRAINT contains spaces so pip will misinterpret it. Make sure the path to pyodide has no spaces.\n"
            "See https://github.com/pypa/pip/issues/13283"
        )

    constraints_file = Path(constraints)
    if not constraints_file.is_file():
        constraints_file.parent.mkdir(parents=True, exist_ok=True)
        constraints_file.write_text("")
    return constraints
