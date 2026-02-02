import re
import shutil
import sys
import tempfile
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
from pyodide_build.out_of_tree import build
from pyodide_build.out_of_tree.pypi import (
    build_dependencies_for_wheel,
    build_wheels_from_pypi_requirements,
    fetch_pypi_package,
)
from pyodide_build.pypabuild import parse_backend_flags
from pyodide_build.spec import _BuildSpecExports, _ExportTypes


def convert_exports(exports: str) -> _BuildSpecExports:
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


def pypi(
    package: str,
    output_directory: Path,
    exports: str,
    config_settings: ConfigSettingsType,
    isolation: bool = True,
    skip_dependency_check: bool = False,
) -> Path:
    """Fetch a wheel from pypi, or build from source if none available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        srcdir = Path(tmpdir)

        # get package from pypi
        package_path = fetch_pypi_package(package, srcdir)
        if not package_path.is_dir():
            # a pure-python wheel has been downloaded - just copy to dist folder
            dest_file = output_directory / package_path.name
            shutil.copyfile(str(package_path), output_directory / package_path.name)
            print(f"Successfully fetched: {package_path.name}")
            return dest_file

        built_wheel = build.run(
            srcdir,
            output_directory,
            convert_exports(exports),
            config_settings,
            isolation=isolation,
            skip_dependency_check=skip_dependency_check,
        )
        return built_wheel


def download_url(url: str, output_directory: Path) -> str:
    with requests.get(url, stream=True) as response:
        urlpath = Path(urlparse(response.url).path)
        if urlpath.suffix == ".gz":
            urlpath = urlpath.with_suffix("")
        file_name = urlpath.name
        with open(output_directory / file_name, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        return file_name


def url(
    package_url: str,
    output_directory: Path,
    exports: str,
    config_settings: ConfigSettingsType,
    isolation: bool = True,
    skip_dependency_check: bool = False,
) -> Path:
    """Fetch a wheel or build sdist from url."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        filename = download_url(package_url, tmppath)
        if Path(filename).suffix == ".whl":
            shutil.move(tmppath / filename, output_directory / filename)
            return output_directory / filename

        builddir = tmppath / "build"
        shutil.unpack_archive(tmppath / filename, builddir)
        files = list(builddir.iterdir())
        if len(files) == 1 and files[0].is_dir():
            # unzipped into subfolder
            builddir = files[0]
        wheel_path = build.run(
            builddir,
            output_directory,
            convert_exports(exports),
            config_settings,
            isolation=isolation,
            skip_dependency_check=skip_dependency_check,
        )
        return wheel_path


def source(
    source_location: Path,
    output_directory: Path,
    exports: str,
    config_settings: ConfigSettingsType,
    isolation: bool = True,
    skip_dependency_check: bool = False,
) -> Path:
    """Use pypa/build to build a Python package from source"""
    built_wheel = build.run(
        source_location,
        output_directory,
        convert_exports(exports),
        config_settings,
        isolation=isolation,
        skip_dependency_check=skip_dependency_check,
    )
    return built_wheel


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
def main(  # noqa: PLR0915
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

    output_directory = output_directory or "./dist"

    outpath = Path(output_directory).resolve()
    outpath.mkdir(exist_ok=True)
    extras: list[str] = []

    # For backward compatibility, in addition to the `--config-setting` arguments, we also support
    # passing config settings as positional arguments.
    config_settings = parse_backend_flags(list(config_setting) + ctx.args)

    skip_dependency_list = list(skip_dependency)
    if skip_built_in_packages:
        package_lock_json = get_pyodide_root() / "dist" / "pyodide-lock.json"
        skip_dependency_list.append(str(package_lock_json.absolute()))

    if len(requirements_txt) > 0:
        # a requirements.txt - build it (and optionally deps)
        if not Path(requirements_txt).exists():
            raise RuntimeError(
                f"Couldn't find requirements text file {requirements_txt}"
            )
        reqs = []
        with open(requirements_txt) as f:
            raw_reqs = [x.strip() for x in f.readlines()]
        for x in raw_reqs:
            # remove comments
            comment_pos = x.find("#")
            if comment_pos != -1:
                x = x[:comment_pos].strip()
            if len(x) > 0:
                if x[0] == "-":
                    raise RuntimeError(
                        f"pyodide build only supports name-based PEP508 requirements. [{x}] will not work."
                    )
                if x.find("@") != -1:
                    raise RuntimeError(
                        f"pyodide build does not support URL based requirements. [{x}] will not work"
                    )
                reqs.append(x)
        try:
            build_wheels_from_pypi_requirements(
                reqs,
                outpath,
                build_dependencies,
                skip_dependency_list,
                # TODO: should we really use same "exports" value for all of our
                # dependencies? Not sure this makes sense...
                convert_exports(exports),
                config_settings,
                isolation=not no_isolation,
                skip_dependency_check=skip_dependency_check,
                output_lockfile=output_lockfile,
            )
        except BaseException as e:
            import traceback

            print("Failed building multiple wheels:", traceback.format_exc())
            raise e
        return

    source_location_: str | None = source_location
    if source_location_:
        extras = re.findall(r"\[(\w+)\]", source_location_)
        if len(extras) != 0:
            source_location_ = source_location_[0 : source_location_.find("[")]
    if not source_location_:
        # build the current folder
        wheel = source(
            Path.cwd(),
            outpath,
            exports,
            config_settings,
            isolation=not no_isolation,
            skip_dependency_check=skip_dependency_check,
        )
    elif source_location_.find("://") != -1:
        wheel = url(
            source_location_,
            outpath,
            exports,
            config_settings,
            isolation=not no_isolation,
            skip_dependency_check=skip_dependency_check,
        )
    elif Path(source_location_).is_dir():
        # a folder, build it
        wheel = source(
            Path(source_location_).resolve(),
            outpath,
            exports,
            config_settings,
            isolation=not no_isolation,
            skip_dependency_check=skip_dependency_check,
        )
    elif source_location_.find("/") == -1:
        # try fetch or build from pypi
        wheel = pypi(
            source_location_,
            outpath,
            exports,
            config_settings,
            isolation=not no_isolation,
            skip_dependency_check=skip_dependency_check,
        )
    else:
        raise RuntimeError(f"Couldn't determine source type for {source_location_}")

    # now build deps for wheel
    if build_dependencies:
        try:
            build_dependencies_for_wheel(
                wheel,
                extras,
                skip_dependency_list,
                # TODO: should we really use same "exports" value for all of our
                # dependencies? Not sure this makes sense...
                convert_exports(exports),
                config_settings,
                isolation=not no_isolation,
                skip_dependency_check=skip_dependency_check,
                output_lockfile=output_lockfile,
                compression_level=compression_level,
            )
        except BaseException as e:
            import traceback

            print("Failed building dependencies for wheel:", traceback.format_exc())
            wheel.unlink()
            raise e
