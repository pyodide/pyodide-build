import json
import os
import shutil
import subprocess as sp
import sys
import traceback
from collections.abc import Callable, Generator, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, cast

from build import BuildBackendException, ConfigSettingsType
from build.env import DefaultIsolatedEnv
from packaging.requirements import Requirement

from pyodide_build import _f2c_fixes, common, pywasmcross
from pyodide_build.build_env import (
    get_build_flag,
    get_pyversion,
    platform,
)
from pyodide_build.io import _BuildSpecExports
from pyodide_build.vendor._pypabuild import (
    _STYLES,
    _DefaultIsolatedEnv,
    _error,
    _handle_build_error,
    _ProjectBuilder,
)

AVOIDED_REQUIREMENTS = [
    # We don't want to install cmake Python package inside the isolated env as it will shadow
    # the pywasmcross cmake wrapper.
    # TODO: Find a way to make scikit-build use the pywasmcross cmake wrapper.
    "cmake",
    # mesonpy installs patchelf in linux platform but we don't want it.
    "patchelf",
]

# corresponding env variables for symlinks
SYMLINK_ENV_VARS = {
    "cc": "CC",
    "c++": "CXX",
    "ld": "LD",
    "lld": "LLD",
    "ar": "AR",
    "gcc": "GCC",
    "ranlib": "RANLIB",
    "strip": "STRIP",
    "gfortran": "FC",  # https://mesonbuild.com/Reference-tables.html#compiler-and-linker-selection-variables
}

HOST_ARCH = common.get_host_platform().replace("-", "_").replace(".", "_")


def _gen_runner(
    cross_build_env: Mapping[str, str],
    isolated_build_env: _DefaultIsolatedEnv,
) -> Callable[[Sequence[str], str | None, Mapping[str, str] | None], None]:
    """
    This returns a slightly modified version of default subprocess runner that pypa/build uses.
    pypa/build prepends the virtual environment's bin directory to the PATH environment variable.
    This is problematic because it shadows the pywasmcross compiler wrappers for cmake, meson, etc.

    This function prepends the compiler wrapper directory to the PATH again so that our compiler wrappers
    are searched first.

    Parameters
    ----------
    cross_build_env
        The cross build environment for pywasmcross.
    isolated_build_env
        The isolated build environment created by pypa/build.
    """

    def _runner(cmd, cwd=None, extra_environ=None):
        env = os.environ.copy()
        if extra_environ:
            env.update(extra_environ)

        # Some build dependencies like cmake, meson installs binaries to this directory
        # and we should add it to the PATH so that they can be found.
        env["BUILD_ENV_SCRIPTS_DIR"] = isolated_build_env.scripts_dir
        env["PATH"] = f"{cross_build_env['COMPILER_WRAPPER_DIR']}:{env['PATH']}"
        # For debugging: Uncomment the following line to print the build command
        # print("Build backend call:", " ".join(str(x) for x in cmd), file=sys.stderr)
        sp.check_call(cmd, cwd=cwd, env=env)

    return _runner


def symlink_unisolated_packages(env: DefaultIsolatedEnv) -> None:
    pyversion = get_pyversion()
    site_packages_path = f"lib/{pyversion}/site-packages"
    env_site_packages = Path(env.path) / site_packages_path
    sysconfigdata_name = get_build_flag("SYSCONFIG_NAME")
    sysconfigdata_path = (
        Path(get_build_flag("TARGETINSTALLDIR"))
        / f"sysconfigdata/{sysconfigdata_name}.py"
    )

    env_site_packages.mkdir(parents=True, exist_ok=True)
    shutil.copy(sysconfigdata_path, env_site_packages)


def remove_avoided_requirements(
    requires: set[str], avoided_requirements: set[str] | list[str]
) -> set[str]:
    for reqstr in list(requires):
        req = Requirement(reqstr)
        for avoid_name in set(avoided_requirements):
            if avoid_name in req.name.lower():
                requires.remove(reqstr)
    return requires


def install_reqs(env: DefaultIsolatedEnv, reqs: set[str]) -> None:
    env.install(
        remove_avoided_requirements(
            reqs,
            AVOIDED_REQUIREMENTS,
        )
    )


def _build_in_isolated_env(
    build_env: Mapping[str, str],
    srcdir: Path,
    outdir: str,
    distribution: Literal["sdist", "wheel"],
    config_settings: ConfigSettingsType,
) -> str:
    # For debugging: The following line disables removal of the isolated venv.
    # It will be left in the /tmp folder and can be inspected or entered as
    # needed.
    # _DefaultIsolatedEnv.__exit__ = lambda *args: None
    with _DefaultIsolatedEnv() as env:
        env = cast(_DefaultIsolatedEnv, env)
        builder = _ProjectBuilder.from_isolated_env(
            env,
            srcdir,
            runner=_gen_runner(build_env, env),
        )

        # first install the build dependencies
        symlink_unisolated_packages(env)
        index_url_for_cross_build = get_build_flag("BUILD_DEPENDENCY_INDEX_URL")
        installed_build_system_requires = False  # build depdency for in pyproject.toml
        installed_backend_requires = (
            False  # dependencies defined by the backend for a given distribution
        )

        with switch_index_url(index_url_for_cross_build):
            try:
                install_reqs(env, builder.build_system_requires)
                installed_build_system_requires = True
            except Exception:
                print(
                    f"Failed to install build dependencies from {index_url_for_cross_build}, falling back to default index url"
                )

        # Disabled for testing
        # if not installed_build_system_requires:
        #     install_reqs(env, builder.build_system_requires)

        try:
            build_reqs = builder.get_requires_for_build(
                distribution,
            )
        except BuildBackendException:
            pass
        else:
            install_reqs(env, build_reqs)
            installed_backend_requires = True

        with common.replace_env(build_env):
            if not installed_backend_requires:
                build_reqs = builder.get_requires_for_build(
                    distribution,
                    config_settings,
                )
                install_reqs(env, build_reqs)

            return builder.build(
                distribution,
                outdir,
                config_settings,
            )


def parse_backend_flags(backend_flags: str | list[str]) -> ConfigSettingsType:
    config_settings: dict[str, str | list[str]] = {}

    if isinstance(backend_flags, str):
        backend_flags = backend_flags.split()

    for arg in backend_flags:
        setting, _, value = arg.partition("=")
        if setting not in config_settings:
            config_settings[setting] = value
            continue

        cur_value = config_settings[setting]
        if isinstance(cur_value, str):
            config_settings[setting] = [cur_value, value]
        else:
            cur_value.append(value)
    return config_settings


def make_command_wrapper_symlinks(symlink_dir: Path) -> dict[str, str]:
    """
    Create symlinks that make pywasmcross look like a compiler.

    Parameters
    ----------
    symlink_dir
        The directory where the symlinks will be created.

    Returns
    -------
    The dictionary of compiler environment variables that points to the symlinks.
    """

    # For maintainers:
    # - you can set "_f2c_fixes_wrapper" variable in pyproject.toml
    # in order to change the script to use when cross-compiling
    # this is only for maintainers and *should* not be used by others

    pywasmcross_exe = symlink_dir / "pywasmcross.py"
    pywasmcross_origin = pywasmcross.__file__
    shutil.copy2(pywasmcross_origin, pywasmcross_exe)
    pywasmcross_exe.chmod(0o755)

    f2c_fixes_exe = symlink_dir / "_f2c_fixes.py"
    f2c_fixes_origin = get_build_flag("_F2C_FIXES_WRAPPER") or _f2c_fixes.__file__
    shutil.copy2(f2c_fixes_origin, f2c_fixes_exe)

    env = {}
    for symlink in pywasmcross.SYMLINKS:
        symlink_path = symlink_dir / symlink
        if os.path.lexists(symlink_path) and not symlink_path.exists():
            # remove broken symlink so it can be re-created
            symlink_path.unlink()

        symlink_path.symlink_to(pywasmcross_exe)
        if symlink in SYMLINK_ENV_VARS:
            env[SYMLINK_ENV_VARS[symlink]] = str(symlink_path)

    return env


@contextmanager
def switch_index_url(index_url: str) -> Generator[None, None, None]:
    """
    Switch index URL that pip locates the packages.
    This function is expected to be used during the process of
    installing package build dependencies.

    Parameters
    ----------
    index_url: index URL to switch to
    """

    env = {
        "PIP_INDEX_URL": index_url,
    }

    # import build
    # build._ctx.VERBOSITY.set(1)

    # def log(msg, *args, **kwargs):
    #     print(msg, str(kwargs))

    # build._ctx.LOGGER.set(log)

    with common.replace_env(env) as replaced_env:
        yield replaced_env


@contextmanager
def get_build_env(
    env: dict[str, str],
    *,
    pkgname: str,
    cflags: str,
    cxxflags: str,
    ldflags: str,
    target_install_dir: str,
    exports: _BuildSpecExports,
) -> Iterator[dict[str, str]]:
    """
    Returns a dict of environment variables that should be used when building
    a package with pypa/build.
    """

    kwargs = {
        "pkgname": pkgname,
        "cflags": cflags,
        "cxxflags": cxxflags,
        "ldflags": ldflags,
        "target_install_dir": target_install_dir,
    }

    args = common.environment_substitute_args(kwargs, env)
    args["builddir"] = str(Path(".").absolute())
    args["exports"] = exports
    env = env.copy()

    with TemporaryDirectory() as symlink_dir_str:
        symlink_dir = Path(symlink_dir_str)
        env.update(make_command_wrapper_symlinks(symlink_dir))

        sysconfig_dir = Path(get_build_flag("TARGETINSTALLDIR")) / "sysconfigdata"
        host_pythonpath = Path(get_build_flag("PYTHONPATH"))
        args["PYTHONPATH"] = sys.path + [str(symlink_dir), str(sysconfig_dir)]
        args["orig__name__"] = __name__
        args["pythoninclude"] = get_build_flag("PYTHONINCLUDE")
        args["PATH"] = env["PATH"]

        pywasmcross_env = json.dumps(args)
        # Store into environment variable and to disk. In most cases we will
        # load from the environment variable but if some other tool filters
        # environment variables we will load from disk instead.
        env["PYWASMCROSS_ARGS"] = pywasmcross_env
        (symlink_dir / "pywasmcross_env.json").write_text(pywasmcross_env)

        env["_PYTHON_HOST_PLATFORM"] = platform()
        env["_PYTHON_SYSCONFIGDATA_NAME"] = get_build_flag("SYSCONFIG_NAME")
        env["PYTHONPATH"] = str(sysconfig_dir) + ":" + str(host_pythonpath)
        env["COMPILER_WRAPPER_DIR"] = str(symlink_dir)

        yield env


def build(
    srcdir: Path,
    outdir: Path,
    build_env: Mapping[str, str],
    config_settings: ConfigSettingsType,
) -> str:
    try:
        with _handle_build_error():
            built = _build_in_isolated_env(
                build_env, srcdir, str(outdir), "wheel", config_settings
            )
            print("{bold}{green}Successfully built {}{reset}".format(built, **_STYLES))
            return built
    except Exception as e:  # pragma: no cover
        tb = traceback.format_exc().strip("\n")
        print("\n{dim}{}{reset}\n".format(tb, **_STYLES))
        _error(str(e))
        sys.exit(1)
