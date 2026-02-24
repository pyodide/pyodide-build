from pathlib import Path

import click

from pyodide_build.build_env import init_environment
from pyodide_build.out_of_tree import venv


# TODO: disabled options that can be later supported have been commented out, fix them
# --copies/--always-copy and symlink_app_data
@click.command()
@click.argument("dest", type=click.Path(path_type=Path))
@click.option(
    "--clear/--no-clear",
    default=False,
    help="Remove the destination directory if it exists.",
)
@click.option(
    "--no-vcs-ignore",
    is_flag=True,
    default=False,
    help="Don't create VCS ignore directive in the destination directory.",
)
@click.option(
    "--no-download",
    "--never-download",
    is_flag=True,
    default=False,
    help="Disable download of the latest pip/setuptools from PyPI.",
)
@click.option(
    "--download/--no-download",
    "download",
    default=False,
    help="Enable download of the latest pip/setuptools from PyPI.",
)
@click.option(
    "--extra-search-dir",
    multiple=True,
    help="A path containing wheels to extend the internal wheel list.",
)
@click.option(
    "--pip",
    default="bundle",
    show_default=True,
    help="Version of pip to install as seed: embed, bundle, or exact version.",
)
@click.option(
    "--setuptools",
    default=None,
    help="Version of setuptools to install as seed: embed, bundle, none or exact version.",
)
@click.option(
    "--no-setuptools",
    is_flag=True,
    default=False,
    help="Do not install setuptools.",
)
@click.option(
    "--no-periodic-update",
    is_flag=True,
    default=False,
    help="Disable the periodic update of the embedded wheels.",
)
def main(
    dest: Path,
    clear: bool,
    no_vcs_ignore: bool,
    no_download: bool,
    download: bool,
    extra_search_dir: tuple[str, ...],
    pip: str,
    setuptools: str | None,
    no_setuptools: bool,
    no_periodic_update: bool,
) -> None:
    """Create a Pyodide virtual environment.

    Additionally, this interface supports a subset of the arguments that
    `virtualenv` supports, with some minor differences for Pyodide compatibility.
    Please note that passing extra options is experimental and may be subject to change.

    \b
    Arguments:
        DEST: directory to create virtualenv at
    """
    init_environment()

    venv_args = []

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
    if setuptools is not None:
        venv_args.extend(["--setuptools", setuptools])
    if no_setuptools:
        venv_args.append("--no-setuptools")

    if no_periodic_update:
        venv_args.append("--no-periodic-update")

    venv.create_pyodide_venv(dest, venv_args)
