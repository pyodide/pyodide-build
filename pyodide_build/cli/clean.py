from pathlib import Path

import typer

from pyodide_build.logger import logger
from pyodide_build.recipe import cleanup
from pyodide_build import build_env

app = typer.Typer(help="Clean build artifacts.")


@app.callback(no_args_is_help=True)
def callback() -> None:
    return


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
def clean_recipes(
    targets: list[str] = typer.Argument(
        None,
        help="Packages or tags (tag:<name>) to clean. Defaults to all packages.",
    ),
    recipe_dir: str | None = typer.Option(
        None,
        help="Directory containing package recipes. Defaults to <pyodide root>/packages.",
    ),
    build_dir: str | None = typer.Option(
        None,
        envvar="PYODIDE_RECIPE_BUILD_DIR",
        help="Directory where package build artifacts are stored. Defaults to recipe directory.",
    ),
) -> None:
    """
    Remove build artifacts for recipe packages.
    """
    recipe_path, build_path = _resolve_paths(
        recipe_dir,
        build_dir,
    )

    logger.info("Cleaning recipes in %s", recipe_path)

    cleanup.clean_recipes(
        recipe_path,
        targets or None,
        build_dir=build_path,
        include_dist=False,
        include_always_tag=False,
    )
