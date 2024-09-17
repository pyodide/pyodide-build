from pathlib import Path

import typer

from pyodide_build.build_env import init_environment
from pyodide_build.out_of_tree import venv


def main(
    dest: Path = typer.Argument(
        ...,
        help="directory to create virtualenv at",
    ),
) -> None:
    """Create a Pyodide virtual environment"""
    init_environment()
    venv.create_pyodide_venv(dest)
