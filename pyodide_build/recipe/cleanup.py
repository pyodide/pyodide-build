import shutil
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


def _locate_cleanup_paths_for_package(
    recipe_dir: Path,
    build_dir_base: Path,
    package: str,
    *,
    include_dist: bool = False,
) -> list[Path]:
    """
    Locate filesystem paths to remove for a single package.
    """
    paths: list[Path] = []
    # Per-package build directory
    paths.append(build_dir_base / package / "build")
    # Per-package build log
    paths.append(recipe_dir / package / "build.log")
    # Per-package dist directory (optional)
    if include_dist:
        paths.append(recipe_dir / package / "dist")
    return paths


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
            path.unlink(missing_ok=True)  # type: ignore[call-arg]
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
    install_dir: Path | None = None,
    include_dist: bool = False,
    include_always_tag: bool = False,
) -> None:
    """
    Clean recipe build artifacts and optionally dist directories.
    """
    if not recipe_dir.is_dir():
        raise FileNotFoundError(f"Recipe directory {recipe_dir} not found")

    build_base = build_dir or recipe_dir

    selected = resolve_targets(
        recipe_dir, targets, include_always_tag=include_always_tag
    )

    for pkg in selected:
        for path in _locate_cleanup_paths_for_package(
            recipe_dir, build_base, pkg, include_dist=include_dist
        ):
            _remove_path(path)

    if include_dist and install_dir is not None:
        _remove_path(install_dir)
