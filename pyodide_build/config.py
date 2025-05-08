import os
import subprocess
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from types import MappingProxyType

from pyodide_build.common import (
    _environment_substitute_str,
    exit_with_stdio,
    search_pyproject_toml,
)
from pyodide_build.constants import BASE_IGNORED_REQUIREMENTS
from pyodide_build.logger import logger


class ConfigManager:
    """
    Configuration manager for pyodide-build.
    This class works "before" installing the cross build environment.
    So it does not have access to the variables that are retrieved from the cross build environment.

    Most of the times, use CrossBuildEnvConfigManager instead of this class.
    But if you need to access the configuration without installing the cross build environment, use this class.
    """

    def __init__(self):
        self._config = {
            **self._load_default_config(),
            **self._load_cross_build_envs(),
            **self._load_config_file(Path.cwd(), os.environ),
            **self._load_config_from_env(os.environ),
        }

    def _load_default_config(self) -> Mapping[str, str]:
        return deepcopy(DEFAULT_CONFIG)

    def _load_cross_build_envs(self) -> Mapping[str, str]:
        """
        Load environment variables from the cross build environment.
        """

        # This method should be implemented in the subclass.
        return {}

    def _load_config_from_env(self, env: Mapping[str, str]) -> Mapping[str, str]:
        return {
            BUILD_VAR_TO_KEY[key]: env[key] for key in env if key in BUILD_VAR_TO_KEY
        }

    def _load_config_file(
        self, curdir: Path, env: Mapping[str, str]
    ) -> Mapping[str, str]:
        pyproject_path, configs = search_pyproject_toml(curdir)

        if pyproject_path is None or configs is None:
            return {}

        if (
            "tool" in configs
            and "pyodide" in configs["tool"]
            and "build" in configs["tool"]["pyodide"]
        ):
            build_config = {}
            for key, v in configs["tool"]["pyodide"]["build"].items():
                if key not in OVERRIDABLE_BUILD_KEYS:
                    logger.warning(
                        "WARNING: The provided build key %s is either invalid or not overridable, hence ignored.",
                        key,
                    )
                    continue
                build_config[key] = _environment_substitute_str(v, env)

            return build_config
        else:
            return {}

    @property
    def config(self) -> Mapping[str, str]:
        return MappingProxyType(self._config)

    def to_env(self) -> dict[str, str]:
        """
        Export the configuration to environment variables.
        """
        return {BUILD_KEY_TO_VAR[k]: v for k, v in self.config.items()}


class CrossBuildEnvConfigManager(ConfigManager):
    """
    Configuration manager for Package build process.
    This class works "after" installing the cross build environment.

    The configuration manager is responsible for loading configuration from various sources.
    The configuration can be loaded from the following sources (in order of precedence):

        1. Command line arguments (TODO)
        2. Environment variables
        3. Configuration file
        4. Makefile.envs
        5. Default values
    """

    def __init__(self, pyodide_root: Path):
        self.pyodide_root = pyodide_root
        super().__init__()

    def _load_cross_build_envs(self) -> Mapping[str, str]:
        makefile_vars = self._get_make_environment_vars()
        computed_vars = {
            k: _environment_substitute_str(v, env=makefile_vars)
            for k, v in DEFAULT_CONFIG_COMPUTED.items()
        }

        return {
            BUILD_VAR_TO_KEY[k]: v
            for k, v in makefile_vars.items()
            if k in BUILD_VAR_TO_KEY
        } | computed_vars

    def _get_make_environment_vars(self) -> Mapping[str, str]:
        """
        Load environment variables from Makefile.envs
        """
        environment = {}
        result = subprocess.run(
            ["make", "-f", str(self.pyodide_root / "Makefile.envs"), ".output_vars"],
            capture_output=True,
            text=True,
            env={"PYODIDE_ROOT": str(self.pyodide_root)},
            check=False,
        )

        if result.returncode != 0:
            logger.error(
                "ERROR: Failed to load environment variables from Makefile.envs"
            )
            exit_with_stdio(result)

        for line in result.stdout.splitlines():
            equalPos = line.find("=")
            if equalPos != -1:
                varname = line[0:equalPos]

                if varname not in BUILD_VAR_TO_KEY:
                    continue

                value = line[equalPos + 1 :]
                value = value.strip("'").strip()
                environment[varname] = value

        return environment


# Configuration variables and corresponding environment variables.
# TODO: distinguish between variables that are overridable by the user and those that are not.
BUILD_KEY_TO_VAR: dict[str, str] = {
    "pyodide_version": "PYODIDE_VERSION",
    "pyodide_abi_version": "PYODIDE_ABI_VERSION",
    "cargo_build_target": "CARGO_BUILD_TARGET",
    "cargo_target_wasm32_unknown_emscripten_linker": "CARGO_TARGET_WASM32_UNKNOWN_EMSCRIPTEN_LINKER",
    "host_install_dir": "HOSTINSTALLDIR",
    "host_site_packages": "HOSTSITEPACKAGES",
    "numpy_lib": "NUMPY_LIB",
    "pyodide_interpreter": "PYODIDE_INTERPETER",
    "platform_triplet": "PLATFORM_TRIPLET",
    "pip_constraint": "PIP_CONSTRAINT",
    "pymajor": "PYMAJOR",
    "pymicro": "PYMICRO",
    "pyminor": "PYMINOR",
    "pyo3_cross_include_dir": "PYO3_CROSS_INCLUDE_DIR",
    "pyo3_cross_lib_dir": "PYO3_CROSS_LIB_DIR",
    "pyo3_cross_python_version": "PYO3_CROSS_PYTHON_VERSION",
    "pyodide_emscripten_version": "PYODIDE_EMSCRIPTEN_VERSION",
    "pyodide_jobs": "PYODIDE_JOBS",
    "pyodide_root": "PYODIDE_ROOT",
    "python_archive_sha256": "PYTHON_ARCHIVE_SHA256",
    "python_archive_url": "PYTHON_ARCHIVE_URL",
    "pythoninclude": "PYTHONINCLUDE",
    "pyversion": "PYVERSION",
    "cpythoninstall": "CPYTHONINSTALL",
    "rustflags": "RUSTFLAGS",
    "rust_toolchain": "RUST_TOOLCHAIN",
    "rust_emscripten_target_url": "RUST_EMSCRIPTEN_TARGET_URL",
    "cflags": "SIDE_MODULE_CFLAGS",
    "cxxflags": "SIDE_MODULE_CXXFLAGS",
    "ldflags": "SIDE_MODULE_LDFLAGS",
    "stdlib_module_cflags": "STDLIB_MODULE_CFLAGS",
    "sysconfigdata_dir": "SYSCONFIGDATA_DIR",
    "sysconfig_name": "SYSCONFIG_NAME",
    "targetinstalldir": "TARGETINSTALLDIR",
    "cmake_toolchain_file": "CMAKE_TOOLCHAIN_FILE",
    "meson_cross_file": "MESON_CROSS_FILE",
    "cflags_base": "CFLAGS_BASE",
    "cxxflags_base": "CXXFLAGS_BASE",
    "ldflags_base": "LDFLAGS_BASE",
    "home": "HOME",
    "path": "PATH",
    "zip_compression_level": "PYODIDE_ZIP_COMPRESSION_LEVEL",
    "skip_emscripten_version_check": "SKIP_EMSCRIPTEN_VERSION_CHECK",
    "build_dependency_index_url": "BUILD_DEPENDENCY_INDEX_URL",
    "default_cross_build_env_url": "DEFAULT_CROSS_BUILD_ENV_URL",
    "xbuildenv_path": "PYODIDE_XBUILDENV_PATH",
    "ignored_build_requirements": "IGNORED_BUILD_REQUIREMENTS",
    "pyodide_interpreter": "PYODIDE_INTERPRETER",
    # maintainer only
    "_f2c_fixes_wrapper": "_F2C_FIXES_WRAPPER",
}

BUILD_VAR_TO_KEY = {v: k for k, v in BUILD_KEY_TO_VAR.items()}

# Configuration keys that can be overridden by the user.
# TODO: distinguish between variables that are overridable by the user and those that are not.
OVERRIDABLE_BUILD_KEYS = {
    "cflags",
    "cxxflags",
    "ldflags",
    "rust_toolchain",
    "rust_emscripten_target_url",
    "meson_cross_file",
    "skip_emscripten_version_check",
    "build_dependency_index_url",
    "default_cross_build_env_url",
    "xbuildenv_path",
    "ignored_build_requirements",
    # maintainer only
    "_f2c_fixes_wrapper",
}

# Default configuration values.
TOOLS_DIR = Path(__file__).parent / "tools"
DEFAULT_CONFIG: dict[str, str] = {
    # Paths to toolchain configuration files
    "cmake_toolchain_file": str(TOOLS_DIR / "cmake/Modules/Platform/Emscripten.cmake"),
    "meson_cross_file": str(TOOLS_DIR / "emscripten.meson.cross"),
    # Rust-specific configuration
    "rustflags": "-C link-arg=-sSIDE_MODULE=2 -C link-arg=-sWASM_BIGINT -Z link-native-libraries=no",
    "cargo_build_target": "wasm32-unknown-emscripten",
    "cargo_target_wasm32_unknown_emscripten_linker": "emcc",
    "rust_toolchain": "nightly-2025-02-01",
    "rust_emscripten_target_url": "",
    # Other configuration
    "pyodide_jobs": "1",
    "skip_emscripten_version_check": "0",
    "build_dependency_index_url": "https://pypi.anaconda.org/pyodide/simple",
    "default_cross_build_env_url": "",
    "xbuildenv_path": "",
    # A list of PEP508 build-time requirements to be ignored when building a wheel
    "ignored_build_requirements": " ".join(BASE_IGNORED_REQUIREMENTS),
    # maintainer only
    "_f2c_fixes_wrapper": "",
}

# Default configs that are computed from other values (often from Makefile.envs)
# TODO: Remove dependency on Makefile.envs
DEFAULT_CONFIG_COMPUTED: dict[str, str] = {
    # Compiler flags
    "cflags": "$(CFLAGS_BASE) -I$(PYTHONINCLUDE)",
    "cxxflags": "$(CXXFLAGS_BASE)",
    "ldflags": "$(LDFLAGS_BASE) -s SIDE_MODULE=1",
    # Rust-specific configuration
    "pyo3_cross_lib_dir": "$(CPYTHONINSTALL)/sysconfigdata",  # FIXME: pyodide xbuildenv stores sysconfigdata here
    "pyo3_cross_include_dir": "$(PYTHONINCLUDE)",
    "pyo3_cross_python_version": "$(PYMAJOR).$(PYMINOR)",
    # Misc
    "stdlib_module_cflags": "$(CFLAGS_BASE) -I$(PYTHONINCLUDE) -I Include/ -I. -IInclude/internal/",  # TODO: remove this
    # Paths to build dependencies
    "host_install_dir": "$(PYODIDE_ROOT)/packages/.artifacts",
    "host_site_packages": "$(PYODIDE_ROOT)/packages/.artifacts/lib/python$(PYMAJOR).$(PYMINOR)/site-packages",
    "numpy_lib": "$(PYODIDE_ROOT)/packages/.artifacts/lib/python$(PYMAJOR).$(PYMINOR)/site-packages/numpy/",
    "pyodide_interpreter": "$(PYODIDE_ROOT)/dist/python",
}


# A dictionary of config variables that are exposed through pyodide config CLI.
PYODIDE_CLI_CONFIGS = {
    "emscripten_version": "PYODIDE_EMSCRIPTEN_VERSION",
    "python_version": "PYVERSION",
    "rustflags": "RUSTFLAGS",
    "cmake_toolchain_file": "CMAKE_TOOLCHAIN_FILE",
    "rust_toolchain": "RUST_TOOLCHAIN",
    "cflags": "SIDE_MODULE_CFLAGS",
    "cxxflags": "SIDE_MODULE_CXXFLAGS",
    "ldflags": "SIDE_MODULE_LDFLAGS",
    "meson_cross_file": "MESON_CROSS_FILE",
    "xbuildenv_path": "PYODIDE_XBUILDENV_PATH",
    "pyodide_abi_version": "PYODIDE_ABI_VERSION",
    "pyodide_root": "PYODIDE_ROOT",
    "python_include_dir": "PYTHONINCLUDE",
    "ignored_build_requirements": "IGNORED_BUILD_REQUIREMENTS",
    "interpreter": "PYODIDE_INTERPRETER",
}
