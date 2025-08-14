from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pyodide_build.logger import logger
from pyodide_build.recipe import loader


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


def remove_package_build(recipe_dir: Path, build_dir_base: Path, package: str) -> bool:
    """
    Remove the per-package build directory if it exists.

    Returns True if anything was removed.
    """
    pkg_build = build_dir_base / package / "build"
    if pkg_build.exists():
        logger.info("Removing %s", str(pkg_build))
        import shutil

        shutil.rmtree(pkg_build, ignore_errors=True)
        return True
    return False


def remove_package_log(recipe_dir: Path, package: str) -> bool:
    """Remove the per-package build log file if it exists."""
    pkg_log = recipe_dir / package / "build.log"
    if pkg_log.is_file():
        try:
            pkg_log.unlink()
            return True
        except Exception:
            return False
    return False


def remove_package_dist(recipe_dir: Path, package: str) -> bool:
    """Remove the per-package dist directory if it exists."""
    pkg_dist = recipe_dir / package / "dist"
    if pkg_dist.exists():
        logger.info("Removing %s", str(pkg_dist))
        import shutil

        shutil.rmtree(pkg_dist, ignore_errors=True)
        return True
    return False


def remove_install_dist(install_dir: Path) -> bool:
    """Remove the global install dist directory if it exists."""
    if install_dir and install_dir.exists():
        logger.info("Removing %s", str(install_dir))
        import shutil

        shutil.rmtree(install_dir, ignore_errors=True)
        return True
    return False


def perform_recipe_cleanup(
    *,
    recipe_dir: Path,
    build_dir: Path | None,
    install_dir: Path | None,
    targets: Iterable[str] | None,
    include_dist: bool = False,
    include_always_tag: bool = False,
) -> int:
    """
    Clean recipe build artifacts and optionally dist directories.

    Returns the number of items removed.
    """
    if not recipe_dir.is_dir():
        raise FileNotFoundError(f"Recipe directory {recipe_dir} not found")

    build_base = build_dir or recipe_dir
    removed_count = 0

    selected = resolve_targets(
        recipe_dir, targets, include_always_tag=include_always_tag
    )

    for pkg in selected:
        if remove_package_build(recipe_dir, build_base, pkg):
            removed_count += 1
        if remove_package_log(recipe_dir, pkg):
            removed_count += 1
        if include_dist and remove_package_dist(recipe_dir, pkg):
            removed_count += 1

    if include_dist and install_dir is not None:
        if remove_install_dist(install_dir):
            removed_count += 1

    return removed_count
