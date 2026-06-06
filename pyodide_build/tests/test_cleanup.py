import shutil
from pathlib import Path

from pyodide_build.recipe.cleanup import (
    clean_recipes,
    resolve_targets,
)


def _write_meta(recipe_dir: Path, pkg: str) -> Path:
    pkg_root = recipe_dir / pkg
    pkg_root.mkdir(parents=True, exist_ok=True)
    meta = f"package:\n  name: {pkg}\n  version: '1.0.0'\nsource:\n  path: .\n"
    (pkg_root / "meta.yaml").write_text(meta, encoding="utf-8")
    return pkg_root


def _make_pkg_with_artifacts(
    recipe_dir: Path, pkg: str, install_dir: Path | None = None
) -> tuple[Path, Path, Path]:
    pkg_root = _write_meta(recipe_dir, pkg)
    build_dir = pkg_root / "build"
    dist_dir = pkg_root / "dist"
    shutil.rmtree(build_dir, ignore_errors=True)
    shutil.rmtree(dist_dir, ignore_errors=True)
    (pkg_root / "build.log").write_text("log", encoding="utf-8")
    build_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / f"{pkg}-1.0.0-any.whl").write_text("wheel", encoding="utf-8")
    if install_dir is not None:
        install_dir.mkdir(parents=True, exist_ok=True)
        (install_dir / "dummy.whl").write_text("wheel", encoding="utf-8")
    return pkg_root, build_dir, dist_dir


def test_clean_preserves_dist_by_default(tmp_path: Path):
    recipe_dir = tmp_path / "recipes"
    for pkg in ("pkg_a", "pkg_b"):
        _make_pkg_with_artifacts(recipe_dir, pkg)

    clean_recipes(
        recipe_dir,
        ["pkg_a", "pkg_b"],
        build_dir=None,
        include_dist=False,
    )

    for pkg in ("pkg_a", "pkg_b"):
        pkg_root = recipe_dir / pkg
        assert not (pkg_root / "build").exists()
        assert (pkg_root / "dist").exists()
        assert not (pkg_root / "build.log").exists()


def test_clean_include_dist_removes_dist(tmp_path: Path):
    recipe_dir = tmp_path / "recipes"
    pkg = "pkg_a"
    pkg_root, build_dir, dist_dir = _make_pkg_with_artifacts(recipe_dir, pkg)

    clean_recipes(
        recipe_dir,
        [pkg],
        build_dir=None,
        include_dist=True,
    )

    assert not build_dir.exists()
    assert not dist_dir.exists()
    assert not (pkg_root / "build.log").exists()


def test_clean_removes_from_custom_build_dir(tmp_path: Path):
    recipe_dir = tmp_path / "recipes"
    custom_build_dir = tmp_path / "custom_build"

    for pkg in ("pkg_a", "pkg_b"):
        _write_meta(recipe_dir, pkg)

    for pkg in ("pkg_a", "pkg_b"):
        pkg_build = custom_build_dir / pkg / "build"
        pkg_build.mkdir(parents=True, exist_ok=True)
        (pkg_build / "artifact.txt").write_text("build artifact", encoding="utf-8")

    assert (custom_build_dir / "pkg_a" / "build" / "artifact.txt").exists()
    assert (custom_build_dir / "pkg_b" / "build" / "artifact.txt").exists()

    clean_recipes(
        recipe_dir,
        ["pkg_a", "pkg_b"],
        build_dir=custom_build_dir,
        include_dist=False,
    )

    assert not (custom_build_dir / "pkg_a" / "build").exists()
    assert not (custom_build_dir / "pkg_b" / "build").exists()
    assert custom_build_dir.exists()


def test_resolve_targets_star_selects_all(tmp_path: Path):
    recipe_dir = tmp_path / "recipes"
    _write_meta(recipe_dir, "pkg_a")
    _write_meta(recipe_dir, "pkg_b")
    all_targets = set(resolve_targets(recipe_dir, ["*"]))
    assert "pkg_a" in all_targets
    assert "pkg_b" in all_targets
