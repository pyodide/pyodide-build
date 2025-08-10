import shutil
from pathlib import Path

import typer
from typer.testing import CliRunner

from pyodide_build.cli import build_recipes

runner = CliRunner()

RECIPE_DIR = Path(__file__).parent / "recipe" / "_test_recipes"


def _ensure_dirs(pkg: str) -> tuple[Path, Path, Path]:
    pkg_root = RECIPE_DIR / pkg
    build_dir = RECIPE_DIR / pkg / "build"
    dist_dir = RECIPE_DIR / pkg / "dist"
    # clean slate
    shutil.rmtree(build_dir, ignore_errors=True)
    shutil.rmtree(dist_dir, ignore_errors=True)
    (pkg_root / "build.log").write_text("log", encoding="utf-8")
    build_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / f"{pkg}-1.0.0-any.whl").write_text("wheel", encoding="utf-8")
    return pkg_root, build_dir, dist_dir


def test_clean_preserves_dist_by_default():
    # Register only the clean command to avoid initializing other CLI parts
    app = typer.Typer()
    app.command()(build_recipes.clean)

    # Prepare two packages
    for pkg in ("pkg_test_graph1", "pkg_test_graph3"):
        _ensure_dirs(pkg)

    result = runner.invoke(
        app,
        [
            "pkg_test_graph1",
            "pkg_test_graph3",
            "--recipe-dir",
            str(RECIPE_DIR),
        ],
    )
    assert result.exit_code == 0, result.output

    for pkg in ("pkg_test_graph1", "pkg_test_graph3"):
        pkg_root = RECIPE_DIR / pkg
        assert not (pkg_root / "build").exists()
        assert (pkg_root / "dist").exists()
        assert not (pkg_root / "build.log").exists()


def test_clean_include_dist_removes_dist(tmp_path):
    app = typer.Typer()
    app.command()(build_recipes.clean)

    pkg = "pkg_test_graph1"
    pkg_root, build_dir, dist_dir = _ensure_dirs(pkg)

    # Use a custom install dir and create a dummy file there
    install_dir = tmp_path / "dist"
    install_dir.mkdir(parents=True, exist_ok=True)
    (install_dir / "dummy.whl").write_text("wheel", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            str(RECIPE_DIR),
            "--install-dir",
            str(install_dir),
            "--include-dist",
        ],
    )
    assert result.exit_code == 0, result.output

    assert not build_dir.exists()
    assert not dist_dir.exists()
    assert not (pkg_root / "build.log").exists()
    assert not install_dir.exists()
