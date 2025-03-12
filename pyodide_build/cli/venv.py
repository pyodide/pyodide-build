from pathlib import Path

import typer

from pyodide_build.build_env import init_environment
from pyodide_build.out_of_tree import venv


# TODO: disabled options that can be later supported have been commented out, fix them
# --copies/--always-copy and symlink_app_data
def main(
    dest: Path = typer.Argument(
        ...,
        help="directory to create virtualenv at",
    ),
    clear: bool = typer.Option(
        False,
        "--clear/--no-clear",
        help="Remove the destination directory if it exists",
    ),
    no_vcs_ignore: bool = typer.Option(
        False,
        "--no-vcs-ignore",
        help="Don't create VCS ignore directive in the destination directory",
    ),
    symlinks: bool = typer.Option(
        True,
        "--symlinks",
        help="Try to use symlinks rather than copies, when symlinks are not the default for the platform",
    ),
    # copies: bool = typer.Option(
    #     False, "--copies", "--always-copy", help="Use copies rather than symlinks, even when symlinks are the default"
    # ),
    no_download: bool = typer.Option(
        False,
        "--no-download",
        "--never-download",
        help="Disable download of the latest pip/setuptools/wheel from PyPI",
    ),
    download: bool = typer.Option(
        False,
        "--download/--no-download",
        help="Enable download of the latest pip/setuptools/wheel from PyPI",
    ),
    extra_search_dir: list[str] = typer.Option(
        None,
        "--extra-search-dir",
        help="A path containing wheels to extend the internal wheel list",
    ),
    pip: str = typer.Option(
        "bundle",
        "--pip",
        help="Version of pip to install as seed: embed, bundle, or exact version.",
    ),
    setuptools: str | None = typer.Option(
        None,
        "--setuptools",
        help="Version of setuptools to install as seed: embed, bundle, none or exact version",
    ),
    no_setuptools: bool = typer.Option(
        False, "--no-setuptools", help="Do not install setuptools"
    ),
    no_wheel: bool = typer.Option(True, "--no-wheel", help="Do not install wheel"),
    no_periodic_update: bool = typer.Option(
        False,
        "--no-periodic-update",
        help="Disable the periodic update of the embedded wheels",
    ),
    # symlink_app_data: bool = typer.Option(
    #     False, "--symlink-app-data/--no-symlink-app-data", help="Symlink the python packages from the app-data folder"
    # ),
) -> None:
    """
    Create a Pyodide virtual environment.
    Additionally, this interface supports a subset of the arguments that `virtualenv` supports, with some minor differences for Pyodide compatibility.
    Please note that passing extra options is experimental and may be subject to change.
    """
    init_environment()

    venv_args = []

    # if copies:
    #     venv_args.append("--copies")
    # if symlink_app_data:
    #     venv_args.append("--symlink-app-data")

    if clear:
        venv_args.append("--clear")
    if no_vcs_ignore:
        venv_args.append("--no-vcs-ignore")
    if no_download:
        venv_args.append("--no-download")
    if download:
        venv_args.append("--download")
    if extra_search_dir:
        for search_dir in extra_search_dir:
            venv_args.extend(["--extra-search-dir", search_dir])
    if pip:
        venv_args.extend(["--pip", pip])
    if symlinks:
        venv_args.append("--symlinks")
    if setuptools is not None:
        venv_args.extend(["--setuptools", setuptools])
    if no_wheel:
        venv_args.append("--no-wheel")
    if no_setuptools:
        venv_args.append("--no-setuptools")

    if no_periodic_update:
        venv_args.append("--no-periodic-update")

    venv.create_pyodide_venv(dest, venv_args)
