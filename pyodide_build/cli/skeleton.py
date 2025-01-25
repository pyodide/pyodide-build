# Create or update a package recipe skeleton,
# inspired from `conda skeleton` command.

import sys
from pathlib import Path

import typer

from pyodide_build import build_env
from pyodide_build.logger import logger
from pyodide_build.recipe import skeleton

app = typer.Typer()


@app.callback(no_args_is_help=True)
def callback() -> None:
    """Add a new package build recipe or update an existing recipe"""
    return


def get_recipe_dir(recipe_dir: str | None) -> Path:
    if recipe_dir:
        return Path(recipe_dir)
    cwd = Path.cwd()
    root = build_env.search_pyodide_root(curdir=cwd)

    if not root:
        root = cwd

    return root / "packages"


@app.command("enable")
def enable(
    names: list[str],
    recipe_dir: str | None = typer.Option(
        None,
        help="The directory containing the recipe of packages."
        "If not specified, the default is ``<cwd>/packages``.",
    ),
):
    recipe_dir_ = get_recipe_dir(recipe_dir)
    status = 0
    for name in names:
        try:
            skeleton.enable_package(
                recipe_dir_,
                name,
            )
            status = -1
        except skeleton.MkpkgFailedException as e:
            logger.error("%s update failed: %s", name, e)
        except Exception:
            print(name)
            raise
    sys.exit(status)


@app.command("disable")
def disable(
    names: list[str],
    message: str = typer.Option(
        "", "--message", "-m", help="Comment to explain why it was disabled"
    ),
    recipe_dir: str | None = typer.Option(
        None,
        help="The directory containing the recipe of packages."
        "If not specified, the default is ``<cwd>/packages``.",
    ),
) -> int:
    recipe_dir_ = get_recipe_dir(recipe_dir)
    status = 0
    for name in names:
        try:
            skeleton.disable_package(recipe_dir_, name, message)
            status = -1
        except skeleton.MkpkgFailedException as e:
            logger.error("%s update failed: %s", name, e)
        except Exception:
            print(name)
            raise
    sys.exit(status)


@app.command("pypi")
def new_recipe_pypi(
    name: str,
    update: bool = typer.Option(
        False,
        "--update",
        "-u",
        help="Update an existing recipe instead of creating a new one",
    ),
    update_patched: bool = typer.Option(
        False,
        "--update-patched",
        help="Force update the package even if it contains patches.",
    ),
    version: str = typer.Option(
        None,
        help="The version of the package, if not specified, latest version will be used.",
    ),
    source_format: str = typer.Option(
        None,
        help="Which source format is preferred. Options are wheel or sdist. "
        "If not specified, then either a wheel or an sdist will be used. ",
    ),
    recipe_dir: str | None = typer.Option(
        None,
        help="The directory containing the recipe of packages."
        "If not specified, the default is ``<cwd>/packages``.",
    ),
) -> None:
    """
    Create a new package recipe from PyPI or update an existing recipe.
    """

    # Determine the recipe directory. If it is specified by the user, we use that;
    # otherwise, we assume that the recipe directory is the ``packages`` directory
    # in the root of the Pyodide tree, without the need to initialize the
    # cross-build environment.
    #
    # It is unlikely that a user will run this command outside of the Pyodide
    # tree, so we do not need to initialize the environment at this stage.

    recipe_dir_ = get_recipe_dir(recipe_dir)

    if update or update_patched:
        try:
            skeleton.update_package(
                recipe_dir_,
                name,
                version,
                source_fmt=source_format,  # type: ignore[arg-type]
                update_patched=update_patched,
            )
        except skeleton.MkpkgFailedException as e:
            logger.error("%s update failed: %s", name, e)
            sys.exit(1)
        except skeleton.MkpkgSkipped as e:
            logger.warning("%s update skipped: %s", name, e)
        except Exception:
            print(name)
            raise
    else:
        skeleton.make_package(recipe_dir_, name, version, source_fmt=source_format)  # type: ignore[arg-type]
