import shutil
from collections.abc import Iterable
from pathlib import Path

from pyodide_build.build_env import BuildArgs
from pyodide_build.logger import logger
from pyodide_build.recipe import loader
from pyodide_build.recipe.builder import RecipeBuilder


def resolve_targets(
    recipe_dir: Path,
    names_or_tags: Iterable[str] | None,
    *,
    include_always_tag: bool = False,
) -> list[str]:
    """
    Resolve package names from names/tags using the recipe loader.

    If names_or_tags is None, selects all packages ("*").
    By default, packages with the "always" tag are not implicitly included.
    """
    if names_or_tags is None:
        names_or_tags = ["*"]

    recipes = loader.load_recipes(
        recipe_dir, names_or_tags, load_always_tag=include_always_tag
    )
    return list(recipes.keys())


def _remove_path(path: Path) -> None:
    """
    Remove a file or directory if it exists. Best-effort, ignore errors.
    """
    try:
        if path.is_dir():
            if path.exists():
                logger.info("Removing %s", str(path))
                shutil.rmtree(path, ignore_errors=True)
        elif path.is_file():
            logger.info("Removing %s", str(path))
            path.unlink(missing_ok=True)
        else:
            # Path does not exist; nothing to do
            logger.debug("Path does not exist: %s", str(path))
            return
    except Exception as exc:
        # Best-effort cleanup; ignore failures
        logger.debug("Failed to remove %s: %s", str(path), exc, exc_info=True)
        return


def clean_recipes(
    recipe_dir: Path,
    targets: Iterable[str] | None,
    *,
    build_dir: Path | None = None,
    include_dist: bool = False,
    include_always_tag: bool = False,
) -> None:
    """
    Clean recipe build artifacts and optionally dist directories.

    Parameters
    ----------
    recipe_dir : Path
        Directory containing package recipes.
    targets : Iterable[str] | None
        Package names or tags to clean. If None, cleans all packages.
    build_dir : Path | None
        Top-level directory where package build directories are created.
        Each package's build artifacts are expected at <build_dir>/<package>/build/.
        If None, defaults to <recipe_dir>/<package>/build/ for each package.
    include_dist : bool
        If True, also remove the dist directory.
    """
    if not recipe_dir.is_dir():
        raise FileNotFoundError(f"Recipe directory {recipe_dir} not found")

    selected = resolve_targets(
        recipe_dir, targets, include_always_tag=include_always_tag
    )

    for pkg in selected:
        # When build_dir is specified, construct the package-specific path
        # to match the structure used in build_recipes_no_deps_impl. The
        # idea is that if set we delete build directories per package, and
        # not the entire build_dir.
        package_build_dir = build_dir / pkg / "build" if build_dir else None
        builder = RecipeBuilder(
            recipe_dir / pkg,
            BuildArgs(),
            build_dir=package_build_dir,
        )
        builder.clean(include_dist=include_dist)
