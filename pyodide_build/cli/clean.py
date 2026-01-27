from pathlib import Path

import click

from pyodide_build import build_env
from pyodide_build.logger import logger
from pyodide_build.recipe import cleanup


@click.group(invoke_without_command=True)
@click.pass_context
def app(ctx: click.Context) -> None:
    """Clean build artifacts."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _resolve_paths(
    recipe_dir: str | None,
    build_dir: str | None,
) -> tuple[Path, Path | None]:
    cwd = Path.cwd()
    root = build_env.search_pyodide_root(cwd) or cwd
    resolved_recipe = (
        Path(recipe_dir).expanduser().resolve() if recipe_dir else (root / "packages")
    )
    resolved_build = Path(build_dir).expanduser().resolve() if build_dir else None
    return resolved_recipe, resolved_build


@app.command("recipes")
@click.argument("targets", nargs=-1, required=False)
@click.option(
    "--recipe-dir",
    default=None,
    help="Directory containing package recipes. Defaults to <pyodide root>/packages.",
)
@click.option(
    "--build-dir",
    default=None,
    envvar="PYODIDE_RECIPE_BUILD_DIR",
    show_envvar=True,
    help="Directory where package build artifacts are stored. Defaults to recipe directory.",
)
def clean_recipes(
    targets: tuple[str, ...],
    recipe_dir: str | None,
    build_dir: str | None,
) -> None:
    """Remove build artifacts for recipe packages.

    \b
    Arguments:
        TARGETS: Packages or tags (tag:<name>) to clean. Defaults to all packages.
    """
    recipe_path, build_path = _resolve_paths(
        recipe_dir,
        build_dir,
    )

    logger.info("Cleaning recipes in %s", recipe_path)

    cleanup.clean_recipes(
        recipe_path,
        list(targets) if targets else None,
        build_dir=build_path,
        include_dist=False,
    )
