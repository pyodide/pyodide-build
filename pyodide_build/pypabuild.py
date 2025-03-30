import json
import os
import shutil
import subprocess as sp
import sys
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence


# A helper function from pypa/build/__main__.py since
# it's not in the vendorized code we have
# TODO: we should move this to a new file. it's out of place
# between the other imports ;-)
def _format_dep_chain(dep_chain: Sequence[str]) -> str:
    return " -> ".join(dep.partition(";")[0].strip() for dep in dep_chain)


from contextlib import contextmanager
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, cast

from build import BuildBackendException, ConfigSettingsType
from build.env import DefaultIsolatedEnv
from packaging.requirements import Requirement

from pyodide_build import _f2c_fixes, common, pywasmcross, uv_helper
from pyodide_build.build_env import (
    get_build_flag,
    get_hostsitepackages,
    get_pyversion,
    get_unisolated_packages,
    platform,
)
from pyodide_build.spec import _BuildSpecExports
from pyodide_build.vendor._pypabuild import (
    _STYLES,
    _DefaultIsolatedEnv,
    _error,
    _handle_build_error,
    _ProjectBuilder,
)

AVOIDED_REQUIREMENTS = [
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
    "cmake": "CMAKE_EXECUTABLE",  # For scikit-build to find cmake (https://github.com/scikit-build/scikit-build-core/pull/603)
}


def _gen_runner(
    cross_build_env: Mapping[str, str],
    isolated_build_env: _DefaultIsolatedEnv = None,
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
        if isolated_build_env:
            env["BUILD_ENV_SCRIPTS_DIR"] = isolated_build_env.scripts_dir
        else:
            # For non-isolated builds, set a fallback path or use the current Python path
            import sysconfig

            scripts_dir = sysconfig.get_path("scripts")
            env["BUILD_ENV_SCRIPTS_DIR"] = scripts_dir

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
    host_site_packages = Path(get_hostsitepackages())
    for name in get_unisolated_packages():
        for path in chain(
            host_site_packages.glob(f"{name}*"), host_site_packages.glob(f"_{name}*")
        ):
            (env_site_packages / path.name).unlink(missing_ok=True)
            (env_site_packages / path.name).symlink_to(path)


def remove_avoided_requirements(
    requires: set[str], avoided_requirements: set[str] | list[str]
) -> set[str]:
    for reqstr in list(requires):
        req = Requirement(reqstr)
        for avoid_name in set(avoided_requirements):
            if avoid_name in req.name.lower():
                requires.remove(reqstr)
    return requires


def install_reqs(
    build_env: Mapping[str, str], env: DefaultIsolatedEnv, reqs: set[str]
) -> None:
    # propagate PIP config from build_env to current environment
    with common.replace_env(
        os.environ | {k: v for k, v in build_env.items() if k.startswith("PIP")}
    ):
        env.install(
            remove_avoided_requirements(
                reqs,
                get_unisolated_packages() + AVOIDED_REQUIREMENTS,
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
    # _DefaultIsolatedEnv.__exit__ = lambda self, *args: print("Skipping removing isolated env in", self.path)
    installer = "uv" if uv_helper.should_use_uv() else "pip"
    with _DefaultIsolatedEnv(installer=installer) as env:
        env = cast(_DefaultIsolatedEnv, env)
        builder = _ProjectBuilder.from_isolated_env(
            env,
            srcdir,
            runner=_gen_runner(build_env, env),
        )

        # first install the build dependencies
        symlink_unisolated_packages(env)
        install_reqs(build_env, env, builder.build_system_requires)
        build_reqs: set[str] | None = None
        try:
            build_reqs = builder.get_requires_for_build(
                distribution,
            )
        except BuildBackendException:
            pass

        if not build_reqs:
            # get_requires_for_build in native env failed. Maybe trying to
            # execute get_requires_for_build in the cross build environment will
            # work?

            # This case is used in pygame-ce. In native env, the setup.py picks
            # up native SDL2 config, then fails. In the cross env, it correctly
            # picks up Emscripten SDL2 config.
            # TODO: Add test coverage.
            with common.replace_env(build_env):
                build_reqs = builder.get_requires_for_build(
                    distribution,
                    config_settings,
                )

        install_reqs(build_env, env, build_reqs)

        with common.replace_env(build_env):
            return builder.build(
                distribution,
                outdir,
                config_settings,
            )


# TODO: move to common.py
def _format_missing_dependencies(missing) -> str:
    return "".join(
        "\n\t" + dep
        for deps in missing
        for dep in (deps[0], _format_dep_chain(deps[1:]))
        if dep
    )


def _build_in_current_env(
    build_env: Mapping[str, str],
    srcdir: Path,
    outdir: str,
    distribution: Literal["sdist", "wheel"],
    config_settings: ConfigSettingsType,
    skip_dependency_check: bool = False,
) -> str:
    with common.replace_env(build_env):
        builder = _ProjectBuilder(srcdir, runner=_gen_runner(build_env))

        if not skip_dependency_check:
            missing = builder.check_dependencies(distribution, config_settings or {})
            if missing:
                dependencies = _format_missing_dependencies(missing)
                _error(f"Missing dependencies: {dependencies}")

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
def _create_symlink_dir(
    env: dict[str, str], build_dir: Path | None, no_isolation: bool = False
):
    if build_dir:
        # If we're running under build-recipes, leave the symlinks in
        # the build directory. This helps with reproducing.
        symlink_dir = build_dir / "pywasmcross_symlinks"
        shutil.rmtree(symlink_dir, ignore_errors=True)
        symlink_dir.mkdir()
        yield symlink_dir
        return

    # TODO: FIXME: compiler wrappers are still ending up in a temporary
    # directory, which breaks persistent builds. This is not ideal, but
    # it is better than nothing so this is non-blocking for now. It has
    # to be investigated further.

    if no_isolation:
        # For non-isolated builds, create a persistent directory in the current working directory
        # or in a well-known location like ~/.pyodide/compiler_wrappers
        symlink_dir = Path.cwd() / ".pyodide_compiler_wrappers"
        symlink_dir.mkdir(exist_ok=True)
        yield symlink_dir
    else:
        # Running from "pyodide build". Put symlinks in a temporary directory.
        # TODO: Add a debug option to save the symlinks.
        with TemporaryDirectory() as symlink_dir_str:
            yield Path(symlink_dir_str)


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
    build_dir: Path | None = None,
    no_isolation: bool = False,
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
    args["exports"] = exports
    env = env.copy()

    with _create_symlink_dir(env, build_dir, no_isolation) as symlink_dir:
        env.update(make_command_wrapper_symlinks(symlink_dir))
        sysconfig_dir = Path(get_build_flag("TARGETINSTALLDIR")) / "sysconfigdata"
        args["PYTHONPATH"] = sys.path + [str(symlink_dir), str(sysconfig_dir)]
        args["orig__name__"] = __name__
        args["pythoninclude"] = get_build_flag("PYTHONINCLUDE")
        args["PATH"] = env["PATH"]
        args["abi"] = get_build_flag("PYODIDE_ABI_VERSION")

        pywasmcross_env = json.dumps(args)
        # Store into environment variable and to disk. In most cases we will
        # load from the environment variable but if some other tool filters
        # environment variables we will load from disk instead.
        env["PYWASMCROSS_ARGS"] = pywasmcross_env
        (symlink_dir / "pywasmcross_env.json").write_text(pywasmcross_env)

        env["_PYTHON_HOST_PLATFORM"] = platform()
        env["_PYTHON_SYSCONFIGDATA_NAME"] = get_build_flag("SYSCONFIG_NAME")
        env["PYTHONPATH"] = str(sysconfig_dir)
        env["COMPILER_WRAPPER_DIR"] = str(symlink_dir)

        yield env


def build(
    srcdir: Path,
    outdir: Path,
    build_env: Mapping[str, str],
    config_settings: ConfigSettingsType,
    isolation: bool = True,
    skip_dependency_check: bool = False,
) -> str:
    try:
        with _handle_build_error():
            if isolation:
                built = _build_in_isolated_env(
                    build_env, srcdir, str(outdir), "wheel", config_settings
                )
            else:
                built = _build_in_current_env(
                    build_env,
                    srcdir,
                    str(outdir),
                    "wheel",
                    config_settings,
                    skip_dependency_check,
                )
            print("{bold}{green}Successfully built {}{reset}".format(built, **_STYLES))
            return built
    except Exception as e:  # pragma: no cover
        tb = traceback.format_exc().strip("\n")
        print("\n{dim}{}{reset}\n".format(tb, **_STYLES))
        _error(str(e))
        sys.exit(1)
