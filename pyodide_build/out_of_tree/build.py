import os
from pathlib import Path
from textwrap import dedent

from build import ConfigSettingsType

from pyodide_build import build_env, common, pypabuild
from pyodide_build.build_env import get_pyodide_root, wheel_platform
from pyodide_build.spec import _BuildSpecExports


def _create_ignore_files(directory: Path) -> None:
    directory.joinpath(".gitignore").write_text(
        dedent("""\
        # Created by pyodide-build
        *
    """),
        encoding="utf-8",
    )

    directory.joinpath(".hgignore").write_text(
        dedent("""\
        # Created by pyodide-build
        syntax: glob
        **/*
    """),
        encoding="utf-8",
    )


def _prepare_build_dir(build_dir: Path) -> None:
    # create a persistent build dir in the source dir
    build_dir.mkdir(exist_ok=True)
    # don't track the build dir in version control,
    # helps if building in a git/mercurial repo
    _create_ignore_files(build_dir)


def run(
    srcdir: Path,
    outdir: Path,
    exports: _BuildSpecExports,
    config_settings: ConfigSettingsType,
    isolation: bool = True,
    skip_dependency_check: bool = False,
) -> Path:
    outdir = outdir.resolve()
    cflags = build_env.get_build_flag("SIDE_MODULE_CFLAGS")
    cflags += f" {os.environ.get('CFLAGS', '')}"
    cxxflags = build_env.get_build_flag("SIDE_MODULE_CXXFLAGS")
    cxxflags += f" {os.environ.get('CXXFLAGS', '')}"
    ldflags = build_env.get_build_flag("SIDE_MODULE_LDFLAGS")
    ldflags += f" {os.environ.get('LDFLAGS', '')}"
    target_install_dir = os.environ.get(
        "TARGETINSTALLDIR", build_env.get_build_flag("TARGETINSTALLDIR")
    )
    build_env._create_constraints_file()
    env = os.environ.copy()
    env.update(build_env.get_build_environment_vars(get_pyodide_root()))

    build_dir = srcdir / ".pyodide_build"
    _prepare_build_dir(build_dir)

    build_env_ctx = pypabuild.get_build_env(
        env=env,
        pkgname="",
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir=target_install_dir,
        exports=exports,
        build_dir=build_dir,
    )

    with build_env_ctx as env:
        built_wheel = pypabuild.build(
            srcdir,
            outdir,
            env,
            config_settings,
            isolation=isolation,
            skip_dependency_check=skip_dependency_check,
        )

    wheel_path = Path(built_wheel)
    if "emscripten" in wheel_path.name:
        # Retag platformed wheels to pyodide
        wheel_path = common.retag_wheel(wheel_path, wheel_platform())
    with common.modify_wheel(wheel_path) as wheel_dir:
        build_env.replace_so_abi_tags(wheel_dir)

    return wheel_path
