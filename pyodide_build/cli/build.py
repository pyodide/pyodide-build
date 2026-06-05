import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast, get_args

import click
from build import ConfigSettingsType

from pyodide_build.build_env import (
    ensure_emscripten,
    init_environment,
)
from pyodide_build.common import default_xbuildenv_path
from pyodide_build.logger import logger
from pyodide_build.out_of_tree import build as _build
from pyodide_build.pypabuild import parse_backend_flags
from pyodide_build.spec import _BuildSpecExports, _ExportTypes


@dataclass
class BuildArgs:
    exports: str
    config_settings: ConfigSettingsType
    isolation: bool
    skip_dependency_check: bool


def _convert_exports(exports: str) -> _BuildSpecExports:
    if "," in exports:
        return [x.strip() for x in exports.split(",") if x.strip()]
    possible_exports = get_args(_ExportTypes)
    if exports in possible_exports:
        return cast(_ExportTypes, exports)
    logger.stderr(
        f"Expected exports to be one of "
        '"pyinit", "requested", "whole_archive", '
        "or a comma separated list of symbols to export. "
        f'Got "{exports}".'
    )
    sys.exit(1)


def _build_from_source(
    source_path: Path,
    output_directory: Path,
    args: BuildArgs,
) -> Path:
    return _build.run(
        source_path,
        output_directory,
        _convert_exports(args.exports),
        args.config_settings,
        isolation=args.isolation,
        skip_dependency_check=args.skip_dependency_check,
    )


def _resolve_source_dir(source_location: str) -> Path:
    if not source_location:
        return Path.cwd()

    if "://" in source_location:
        logger.stderr(
            f"Building from a URL is no longer supported. "
            f"Got '{source_location}'. Pass a local source directory instead, "
            "or download a pre-built wheel from PyPI."
        )
        sys.exit(1)

    source_path = Path(source_location)
    if not source_path.is_dir():
        logger.stderr(
            f"'{source_location}' is not a directory. Building from a PyPI "
            "requirement specifier is no longer supported. Pass a local source "
            "directory instead, or download a pre-built wheel from PyPI."
        )
        sys.exit(1)

    return source_path.resolve()


DEFAULT_PATH = default_xbuildenv_path()


@click.command(
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "help_option_names": ["-h", "--help"],
    },
)
@click.argument("source_location", default="", required=False)
@click.option(
    "--outdir",
    "-o",
    "output_directory",
    default="",
    help="which directory should the output be placed into?",
)
@click.option(
    "--exports",
    default="requested",
    envvar="PYODIDE_BUILD_EXPORTS",
    show_envvar=True,
    help=(
        "Which symbols to export when linking .so files. "
        "Choices: 'pyinit' (only PyInit_<module>), "
        "'requested' (default, symbols requested by the build system), "
        "'whole_archive' (all symbols from all archives), "
        "or a comma-separated list of symbol names."
    ),
)
@click.option(
    "--no-isolation",
    "-n",
    is_flag=True,
    default=False,
    help=(
        "Disable building the project in an isolated virtual environment. "
        "Build dependencies must be installed separately when this option is used"
    ),
)
@click.option(
    "--skip-dependency-check",
    "-x",
    is_flag=True,
    default=False,
    help=(
        "Do not check that the build dependencies are installed. This option "
        "is only useful when used with --no-isolation."
    ),
)
@click.option(
    "--config-setting",
    "-C",
    "config_setting",
    multiple=True,
    metavar="KEY[=VALUE]",
    help=(
        "Settings to pass to the backend. "
        "Works same as the --config-setting option of pypa/build."
    ),
)
@click.option(
    "--xbuildenv-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_PATH,
    envvar="PYODIDE_XBUILDENV_PATH",
    show_envvar=True,
    help="Path to the cross-build environment directory.",
)
@click.option(
    "--skip-emscripten-install",
    is_flag=True,
    default=False,
    envvar="PYODIDE_SKIP_EMSCRIPTEN_INSTALL",
    show_envvar=True,
    help="Skip automatic installation of Emscripten if not found.",
)
@click.pass_context
def main(
    ctx: click.Context,
    source_location: str,
    output_directory: str,
    exports: str,
    no_isolation: bool,
    skip_dependency_check: bool,
    config_setting: tuple[str, ...],
    xbuildenv_path: Path,
    skip_emscripten_install: bool,
) -> None:
    """Use pypa/build to build a Python package from source.

    \b
    Arguments:
        SOURCE_LOCATION: Path to a local source folder to build. If this is
            blank, it will build the current directory.
    """
    init_environment(xbuildenv_path=xbuildenv_path)
    try:
        ensure_emscripten(skip_install=skip_emscripten_install)
    except RuntimeError as e:
        print(e.args[0], file=sys.stderr)
        sys.exit(1)

    outpath = Path(output_directory or "./dist").resolve()
    outpath.mkdir(exist_ok=True)

    config_settings = parse_backend_flags(list(config_setting) + ctx.args)
    build_args = BuildArgs(
        exports=exports,
        config_settings=config_settings,
        isolation=not no_isolation,
        skip_dependency_check=skip_dependency_check,
    )

    source_dir = _resolve_source_dir(source_location)
    _build_from_source(source_dir, outpath, build_args)
