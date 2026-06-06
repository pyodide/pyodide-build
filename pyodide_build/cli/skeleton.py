# Create or update a package recipe skeleton,
# inspired from `conda skeleton` command.

import sys
from pathlib import Path
from typing import Literal

import click

from pyodide_build import build_env
from pyodide_build.logger import logger
from pyodide_build.recipe import skeleton


@click.group(invoke_without_command=True)
@click.pass_context
def app(ctx: click.Context) -> None:
    """Add a new package build recipe or update an existing recipe."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def get_recipe_dir(recipe_dir: str | None) -> Path:
    if recipe_dir:
        return Path(recipe_dir)
    cwd = Path.cwd()
    root = build_env.search_pyodide_root(curdir=cwd)

    if not root:
        root = cwd

    return root / "packages"


@app.command("enable")
@click.argument("names", nargs=-1, required=True)
@click.option(
    "--recipe-dir",
    default=None,
    help=(
        "The directory containing the recipe of packages. "
        "If not specified, the default is ``<cwd>/packages``."
    ),
)
def enable(names: tuple[str, ...], recipe_dir: str | None) -> None:
    """Enable packages.

    \b
    Arguments:
        NAMES: Package names to enable.
    """
    recipe_dir_ = get_recipe_dir(recipe_dir)
    status = 0
    for name in names:
        try:
            skeleton.enable_package(
                recipe_dir_,
                name,
            )
        except skeleton.MkpkgFailedException as e:
            status = -1
            logger.error("%s update failed: %s", name, e)
        except Exception:
            print(name)
            raise
    sys.exit(status)


@app.command("disable")
@click.argument("names", nargs=-1, required=True)
@click.option(
    "--message",
    "-m",
    default="",
    help="Comment to explain why it was disabled.",
)
@click.option(
    "--recipe-dir",
    default=None,
    help=(
        "The directory containing the recipe of packages. "
        "If not specified, the default is ``<cwd>/packages``."
    ),
)
def disable(names: tuple[str, ...], message: str, recipe_dir: str | None) -> int:
    """Disable packages.

    \b
    Arguments:
        NAMES: Package names to disable.
    """
    recipe_dir_ = get_recipe_dir(recipe_dir)
    status = 0
    for name in names:
        try:
            skeleton.disable_package(recipe_dir_, name, message)
        except skeleton.MkpkgFailedException as e:
            status = -1
            logger.error("%s update failed: %s", name, e)
        except Exception:
            print(name)
            raise
    sys.exit(status)


@app.command("pin")
@click.argument("names", nargs=-1, required=True)
@click.option(
    "--message",
    "-m",
    default="",
    help="Comment to explain why it was pinned.",
)
@click.option(
    "--recipe-dir",
    default=None,
    help=(
        "The directory containing the recipe of packages. "
        "If not specified, the default is ``<cwd>/packages``."
    ),
)
def pin(names: tuple[str, ...], message: str, recipe_dir: str | None) -> int:
    """Pin packages.

    \b
    Arguments:
        NAMES: Package names to pin.
    """
    recipe_dir_ = get_recipe_dir(recipe_dir)
    status = 0
    for name in names:
        try:
            skeleton.pin_package(recipe_dir_, name, message)
        except skeleton.MkpkgFailedException as e:
            status = -1
            logger.error("%s update failed: %s", name, e)
        except Exception:
            print(name)
            raise
    sys.exit(status)


@app.command("pypi")
@click.argument("name")
@click.option(
    "--update",
    "-u",
    is_flag=True,
    default=False,
    help="Update an existing recipe instead of creating a new one.",
)
@click.option(
    "--update-patched",
    is_flag=True,
    default=False,
    help="Force update the package even if it contains patches.",
)
@click.option(
    "--update-pinned",
    is_flag=True,
    default=False,
    help="Force update the package even if is pinned.",
)
@click.option(
    "--version",
    default=None,
    help="The version of the package, if not specified, latest version will be used.",
)
@click.option(
    "--source-format",
    default=None,
    type=click.Choice(["wheel", "sdist"]),
    help=(
        "Which source format is preferred. Options are wheel or sdist. "
        "If not specified, then either a wheel or an sdist will be used."
    ),
)
@click.option(
    "--recipe-dir",
    default=None,
    help=(
        "The directory containing the recipe of packages. "
        "If not specified, the default is ``<cwd>/packages``."
    ),
)
@click.option(
    "--maintainer",
    "-m",
    default=None,
    help="The github username to use as the maintainer.",
)
@click.option(
    "--gh-maintainer",
    "--ghm",
    is_flag=True,
    default=False,
    help="Set the maintainer from 'gh auth status'. Requires gh cli.",
)
def new_recipe_pypi(
    name: str,
    update: bool,
    update_patched: bool,
    update_pinned: bool,
    version: str | None,
    source_format: Literal["wheel", "sdist"] | None,
    recipe_dir: str | None,
    maintainer: str | None,
    gh_maintainer: bool,
) -> None:
    """Create a new package recipe from PyPI or update an existing recipe.

    \b
    Arguments:
        NAME: Package name on PyPI.
    """
    # Determine the recipe directory. If it is specified by the user, we use that;
    # otherwise, we assume that the recipe directory is the ``packages`` directory
    # in the root of the Pyodide tree, without the need to initialize the
    # cross-build environment.
    #
    # It is unlikely that a user will run this command outside of the Pyodide
    # tree, so we do not need to initialize the environment at this stage.
    recipe_dir_ = get_recipe_dir(recipe_dir)
    action = "update" if (update or update_patched or update_pinned) else "create"

    try:
        if update or update_patched or update_pinned:
            if maintainer or gh_maintainer:
                raise skeleton.MkpkgFailedException(
                    "--maintainer and --gh-maintainer are only currently supported when creating a new recipe."
                )
            skeleton.update_package(
                recipe_dir_,
                name,
                version=version,
                source_fmt=source_format,
                update_patched=update_patched,
                update_pinned=update_pinned,
            )
        else:
            if maintainer and gh_maintainer:
                raise skeleton.MkpkgFailedException(
                    "At most one of --maintainer and --gh-maintainer can use used."
                )
            if gh_maintainer:
                maintainer = skeleton.lookup_gh_username()
            skeleton.make_package(
                recipe_dir_,
                name,
                version,
                source_fmt=source_format,
                maintainer=maintainer,
            )

    except skeleton.MkpkgFailedException as e:
        logger.error("Failed to %s %s: %s", action, name, e)
        sys.exit(1)
    except skeleton.MkpkgSkipped as e:
        logger.warning("%s %s skipped: %s", name, action, e)
    except Exception:
        print(name)
        raise
