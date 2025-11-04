from pathlib import Path

from typer.testing import CliRunner

from pyodide_build.cli.clean import app

runner = CliRunner()


def _write_meta(recipe_dir: Path, pkg: str) -> Path:
    pkg_root = recipe_dir / pkg
    pkg_root.mkdir(parents=True, exist_ok=True)
    meta = f"package:\n  name: {pkg}\n  version: '1.0.0'\nsource:\n  path: .\n"
    (pkg_root / "meta.yaml").write_text(meta, encoding="utf-8")
    return pkg_root


def _make_pkg_with_artifacts(
    recipe_dir: Path, pkg: str, install_dir: Path | None = None
) -> Path:
    pkg_root = _write_meta(recipe_dir, pkg)
    build_dir = pkg_root / "build"
    dist_dir = pkg_root / "dist"
    (pkg_root / "build.log").write_text("log", encoding="utf-8")
    build_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / f"{pkg}-1.0.0-any.whl").write_text("wheel", encoding="utf-8")
    if install_dir is not None:
        install_dir.mkdir(parents=True, exist_ok=True)
        (install_dir / "dummy.whl").write_text("wheel", encoding="utf-8")
    return pkg_root


def test_clean_recipes_cli_removes_artifacts(tmp_path):
    recipe_dir = tmp_path / "recipes"
    install_dir = tmp_path / "dist"
    pkg_root = _make_pkg_with_artifacts(recipe_dir, "pkg_a", install_dir=install_dir)

    result = runner.invoke(
        app,
        [
            "recipes",
            "--recipe-dir",
            str(recipe_dir),
            "--install-dir",
            str(install_dir),
            "--include-dist",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not (pkg_root / "build").exists()
    assert not (pkg_root / "build.log").exists()
    assert not (pkg_root / "dist").exists()
    assert not install_dir.exists()


def test_clean_recipes_cli_targets_subset(tmp_path):
    recipe_dir = tmp_path / "recipes"
    install_dir = tmp_path / "dist"
    pkg_a = _make_pkg_with_artifacts(recipe_dir, "pkg_a", install_dir=install_dir)
    pkg_b = _make_pkg_with_artifacts(recipe_dir, "pkg_b", install_dir=install_dir)

    result = runner.invoke(
        app,
        [
            "recipes",
            "--recipe-dir",
            str(recipe_dir),
            "--install-dir",
            str(install_dir),
            "pkg_a",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not (pkg_a / "build").exists()
    assert not (pkg_a / "build.log").exists()
    assert (pkg_a / "dist").exists()

    assert (pkg_b / "build").exists()
    assert (pkg_b / "build.log").exists()
    assert (pkg_b / "dist").exists()
