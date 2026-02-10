import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast, get_args
from urllib.parse import urlparse

import click
import requests
from build import ConfigSettingsType

from pyodide_build.build_env import (
    ensure_emscripten,
    get_pyodide_root,
    init_environment,
)
from pyodide_build.common import default_xbuildenv_path
from pyodide_build.logger import logger
from pyodide_build.out_of_tree import build as _build
from pyodide_build.out_of_tree.pypi import (
    MissingOptionalDependencyError,
    build_dependencies_for_wheel,
    build_wheels_from_pypi_requirements,
    fetch_pypi_package,
)
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


def _download_url(url: str, output_directory: Path) -> str:
    with requests.get(url, stream=True) as response:
        urlpath = Path(urlparse(response.url).path)
        if urlpath.suffix == ".gz":
            urlpath = urlpath.with_suffix("")
        file_name = urlpath.name
        with open(output_directory / file_name, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        return file_name


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


def _build_from_url(
    package_url: str,
    output_directory: Path,
    args: BuildArgs,
) -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        filename = _download_url(package_url, tmppath)
        if Path(filename).suffix == ".whl":
            shutil.move(tmppath / filename, output_directory / filename)
            return output_directory / filename

        builddir = tmppath / "build"
        shutil.unpack_archive(tmppath / filename, builddir)
        files = list(builddir.iterdir())
        if len(files) == 1 and files[0].is_dir():
            builddir = files[0]
        return _build_from_source(builddir, output_directory, args)


def _build_from_pypi(
    package: str,
    output_directory: Path,
    args: BuildArgs,
) -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        srcdir = Path(tmpdir)

        try:
            package_path = fetch_pypi_package(package, srcdir)
        except MissingOptionalDependencyError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

        if not package_path.is_dir():
            dest_file = output_directory / package_path.name
            shutil.copyfile(str(package_path), dest_file)
            print(f"Successfully fetched: {package_path.name}")
            return dest_file

        return _build_from_source(srcdir, output_directory, args)


def _parse_requirements_file(requirements_txt: str) -> list[str]:
    if not Path(requirements_txt).exists():
        raise RuntimeError(f"Couldn't find requirements text file {requirements_txt}")

    reqs = []
    with open(requirements_txt) as f:
        raw_reqs = [x.strip() for x in f.readlines()]

    for line in raw_reqs:
        comment_pos = line.find("#")
        if comment_pos != -1:
            line = line[:comment_pos].strip()
        if not line:
            continue
        if line[0] == "-":
            raise RuntimeError(
                f"pyodide build only supports name-based PEP508 requirements. [{line}] will not work."
            )
        if "@" in line:
            raise RuntimeError(
                f"pyodide build does not support URL based requirements. [{line}] will not work"
            )
        reqs.append(line)

    return reqs


def _build_from_requirements(
    requirements_txt: str,
    output_directory: Path,
    args: BuildArgs,
    build_dependencies: bool,
    skip_dependency_list: list[str],
    output_lockfile: str,
) -> None:
    reqs = _parse_requirements_file(requirements_txt)
    try:
        build_wheels_from_pypi_requirements(
            reqs,
            output_directory,
            build_dependencies,
            skip_dependency_list,
            _convert_exports(args.exports),
            args.config_settings,
            isolation=args.isolation,
            skip_dependency_check=args.skip_dependency_check,
            output_lockfile=output_lockfile,
        )
    except MissingOptionalDependencyError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except BaseException as e:
        import traceback

        print("Failed building multiple wheels:", traceback.format_exc())
        raise e


def _build_wheel_dependencies(
    wheel: Path,
    extras: list[str],
    args: BuildArgs,
    skip_dependency_list: list[str],
    output_lockfile: str,
    compression_level: int,
) -> None:
    try:
        build_dependencies_for_wheel(
            wheel,
            extras,
            skip_dependency_list,
            _convert_exports(args.exports),
            args.config_settings,
            isolation=args.isolation,
            skip_dependency_check=args.skip_dependency_check,
            output_lockfile=output_lockfile,
            compression_level=compression_level,
        )
    except MissingOptionalDependencyError as e:
        print(str(e), file=sys.stderr)
        wheel.unlink()
        sys.exit(1)
    except BaseException as e:
        import traceback

        print("Failed building dependencies for wheel:", traceback.format_exc())
        wheel.unlink()
        raise e


def _detect_source_type(source_location: str) -> str:
    if not source_location:
        return "cwd"
    if "://" in source_location:
        return "url"
    if Path(source_location).is_dir():
        return "directory"
    if "/" not in source_location:
        return "pypi"
    raise RuntimeError(f"Couldn't determine source type for {source_location}")


def _extract_extras(source_location: str) -> tuple[str, list[str]]:
    extras = re.findall(r"\[(\w+)\]", source_location)
    if extras:
        source_location = source_location[: source_location.find("[")]
    return source_location, extras


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
    "--requirements",
    "-r",
    "requirements_txt",
    default="",
    help="Build a list of package requirements from a requirements.txt file",
)
@click.option(
    "--exports",
    default="requested",
    envvar="PYODIDE_BUILD_EXPORTS",
    show_envvar=True,
    help="Which symbols should be exported when linking .so files?",
)
@click.option(
    "--build-dependencies/--no-build-dependencies",
    default=False,
    help="Fetch dependencies from pypi and build them too.",
)
@click.option(
    "--output-lockfile",
    default="",
    help="Output list of resolved dependencies to a file in requirements.txt format",
)
@click.option(
    "--skip-dependency",
    multiple=True,
    help=(
        "Skip building or resolving a single dependency, or a pyodide-lock.json file. "
        "Use multiple times or provide a comma separated list to skip multiple dependencies."
    ),
)
@click.option(
    "--skip-built-in-packages/--no-skip-built-in-packages",
    default=True,
    help="Don't build dependencies that are built into the pyodide distribution.",
)
@click.option(
    "--compression-level",
    default=6,
    show_default=True,
    help="Compression level to use for the created zip file",
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
    requirements_txt: str,
    exports: str,
    build_dependencies: bool,
    output_lockfile: str,
    skip_dependency: tuple[str, ...],
    skip_built_in_packages: bool,
    compression_level: int,
    no_isolation: bool,
    skip_dependency_check: bool,
    config_setting: tuple[str, ...],
    xbuildenv_path: Path,
    skip_emscripten_install: bool,
) -> None:
    """Use pypa/build to build a Python package from source, pypi or url.

    \b
    Arguments:
        SOURCE_LOCATION: Build source, can be source folder, pypi version specification,
            or url to a source dist archive or wheel file. If this is blank, it
            will build the current directory.
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

    skip_dependency_list = list(skip_dependency)
    if skip_built_in_packages:
        package_lock_json = get_pyodide_root() / "dist" / "pyodide-lock.json"
        skip_dependency_list.append(str(package_lock_json.absolute()))

    if requirements_txt:
        _build_from_requirements(
            requirements_txt,
            outpath,
            build_args,
            build_dependencies,
            skip_dependency_list,
            output_lockfile,
        )
        return

    source_location, extras = _extract_extras(source_location)
    source_type = _detect_source_type(source_location)

    if source_type == "cwd":
        wheel = _build_from_source(Path.cwd(), outpath, build_args)
    elif source_type == "directory":
        wheel = _build_from_source(Path(source_location).resolve(), outpath, build_args)
    elif source_type == "url":
        wheel = _build_from_url(source_location, outpath, build_args)
    elif source_type == "pypi":
        wheel = _build_from_pypi(source_location, outpath, build_args)
    else:
        raise RuntimeError(f"Unknown source type: {source_type}")

    if build_dependencies:
        _build_wheel_dependencies(
            wheel,
            extras,
            build_args,
            skip_dependency_list,
            output_lockfile,
            compression_level,
        )


def pypi(
    package: str,
    output_directory: Path,
    exports: str,
    config_settings: ConfigSettingsType,
    isolation: bool = True,
    skip_dependency_check: bool = False,
) -> Path:
    """Fetch a wheel from pypi, or build from source if none available."""
    args = BuildArgs(
        exports=exports,
        config_settings=config_settings,
        isolation=isolation,
        skip_dependency_check=skip_dependency_check,
    )
    return _build_from_pypi(package, output_directory, args)


def url(
    package_url: str,
    output_directory: Path,
    exports: str,
    config_settings: ConfigSettingsType,
    isolation: bool = True,
    skip_dependency_check: bool = False,
) -> Path:
    """Fetch a wheel or build sdist from url."""
    args = BuildArgs(
        exports=exports,
        config_settings=config_settings,
        isolation=isolation,
        skip_dependency_check=skip_dependency_check,
    )
    return _build_from_url(package_url, output_directory, args)


def source(
    source_location: Path,
    output_directory: Path,
    exports: str,
    config_settings: ConfigSettingsType,
    isolation: bool = True,
    skip_dependency_check: bool = False,
) -> Path:
    """Use pypa/build to build a Python package from source"""
    args = BuildArgs(
        exports=exports,
        config_settings=config_settings,
        isolation=isolation,
        skip_dependency_check=skip_dependency_check,
    )
    return _build_from_source(source_location, output_directory, args)
