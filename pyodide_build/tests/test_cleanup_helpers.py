from pathlib import Path
import shutil

from pyodide_build.recipe.cleanup import (
    perform_recipe_cleanup,
    resolve_targets,
)


RECIPE_DIR = Path(__file__).parent / "recipe" / "_test_recipes"


def _make_pkg_with_artifacts(pkg: str, install_dir: Path | None = None) -> tuple[Path, Path, Path]:
    pkg_root = RECIPE_DIR / pkg
    build_dir = RECIPE_DIR / pkg / "build"
    dist_dir = RECIPE_DIR / pkg / "dist"
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


def test_perform_cleanup_preserves_dist_by_default(tmp_path: Path):
    for pkg in ("pkg_test_graph1", "pkg_test_graph3"):
        _make_pkg_with_artifacts(pkg)

    removed = perform_recipe_cleanup(
        recipe_dir=RECIPE_DIR,
        build_dir=None,
        install_dir=None,
        targets=["pkg_test_graph1", "pkg_test_graph3"],
        include_dist=False,
    )
    assert removed >= 4

    for pkg in ("pkg_test_graph1", "pkg_test_graph3"):
        pkg_root = RECIPE_DIR / pkg
        assert not (pkg_root / "build").exists()
        assert (pkg_root / "dist").exists()
        assert not (pkg_root / "build.log").exists()


def test_perform_cleanup_include_dist_removes_dist(tmp_path: Path):
    install_dir = tmp_path / "dist"
    pkg = "pkg_test_graph1"
    pkg_root, build_dir, dist_dir = _make_pkg_with_artifacts(pkg, install_dir=install_dir)

    removed = perform_recipe_cleanup(
        recipe_dir=RECIPE_DIR,
        build_dir=None,
        install_dir=install_dir,
        targets=[pkg],
        include_dist=True,
    )
    assert removed >= 4

    assert not build_dir.exists()
    assert not dist_dir.exists()
    assert not (pkg_root / "build.log").exists()
    assert not install_dir.exists()


def test_resolve_targets_star_selects_all():
    all_targets = set(resolve_targets(RECIPE_DIR, ["*"]))
    assert "pkg_test_graph1" in all_targets
    assert "pkg_test_graph3" in all_targets


