from collections.abc import Iterable
from pathlib import Path

from pyodide_build.build_env import BuildArgs
from pyodide_build.recipe import loader
from pyodide_build.recipe.builder import RecipeBuilder


def resolve_targets(
    recipe_dir: Path,
    names_or_tags: Iterable[str] | None,
) -> list[str]:
    """
    Resolve package names from names/tags using the recipe loader.

    If names_or_tags is None, selects all packages ("*").
    By default, packages with the "always" tag are not implicitly included.
    """
    if names_or_tags is None:
        names_or_tags = ["*"]

    recipes = loader.load_recipes(
        recipe_dir,
        names_or_tags,
    )
    return list(recipes.keys())


def clean_recipes(
    recipe_dir: Path,
    targets: Iterable[str] | None,
    *,
    build_dir: Path | None = None,
    include_dist: bool = False,
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
        recipe_dir,
        targets,
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
