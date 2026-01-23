import re
from pathlib import Path

import click

from pyodide_build._py_compile import _py_compile_archive, _py_compile_archive_dir


@click.group(invoke_without_command=True)
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--silent/--no-silent",
    default=False,
    help="Silent mode, do not print anything.",
)
@click.option(
    "--keep/--no-keep",
    default=False,
    help="Keep the original wheel / zip file.",
)
@click.option(
    "--compression-level",
    default=6,
    show_default=True,
    help="Compression level to use for the created zip file.",
)
@click.option(
    "--exclude",
    default="",
    help="List of files to exclude from compilation, works only for directories. Defaults to no files.",
)
@click.pass_context
def main(
    ctx: click.Context,
    path: Path,
    silent: bool,
    keep: bool,
    compression_level: int,
    exclude: str,
) -> None:
    """Compile .py files to .pyc in a wheel, a zip file, or a folder with wheels or zip files.

    If the provided folder contains the `pyodide-lock.json` file, it will be
    rewritten with the updated wheel / zip file paths and sha256 checksums.

    \b
    Arguments:
        PATH: Path to the input wheel or a folder with wheels or zip files.
    """
    if ctx.invoked_subcommand is not None:
        return

    if not path.exists():
        click.echo(f"Error: {path} does not exist")
        raise SystemExit(1)

    # Convert the comma / space separated strings to lists
    excludes = [
        item.strip() for item in re.split(r",|\s", exclude) if item.strip() != ""
    ]

    if path.is_file():
        if path.suffix not in [".whl", ".zip"]:
            click.echo(
                f"Error: only .whl and .zip files are supported, got {path.name}"
            )
            raise SystemExit(1)

        _py_compile_archive(
            path, verbose=not silent, keep=keep, compression_level=compression_level
        )
    elif path.is_dir():
        _py_compile_archive_dir(
            path,
            verbose=not silent,
            keep=keep,
            compression_level=compression_level,
            excludes=excludes,
        )
    else:
        click.echo(f"{path=} is not a file or a directory")
