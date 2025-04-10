import shutil
import zipfile
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

import pyodide_build
from pyodide_build import build_env, cli, common
from pyodide_build.cli import (
    build,
    build_recipes,
    config,
    create_zipfile,
    py_compile,
    skeleton,
)
from pyodide_build.config import PYODIDE_CLI_CONFIGS

runner = CliRunner()

RECIPE_DIR = Path(__file__).parent / "recipe" / "_test_recipes"


def assert_runner_succeeded(result):
    __tracebackhide__ = True
    print(result.stdout)
    if result.exception:
        import traceback

        traceback.print_exception(result.exception)
    assert result.exit_code == 0


def test_skeleton_pypi(tmp_path):
    test_pkg = "pytest-pyodide"
    old_version = "0.21.0"
    new_version = "0.22.0"

    result = runner.invoke(
        skeleton.app,
        [
            "pypi",
            test_pkg,
            "--recipe-dir",
            str(tmp_path),
            "--version",
            old_version,
        ],
    )
    assert_runner_succeeded(result)
    assert "pytest-pyodide/meta.yaml" in result.stdout

    result = runner.invoke(
        skeleton.app,
        [
            "pypi",
            test_pkg,
            "--recipe-dir",
            str(tmp_path),
            "--version",
            new_version,
            "--update",
        ],
    )
    assert_runner_succeeded(result)
    assert f"Updated {test_pkg} from {old_version} to {new_version}" in result.stdout

    result = runner.invoke(
        skeleton.app, ["pypi", test_pkg, "--recipe-dir", str(tmp_path)]
    )
    assert result.exit_code != 0
    assert "already exists" in str(result.stdout)
    assert isinstance(result.exception, SystemExit)


def test_build_recipe_plain(tmp_path, dummy_xbuildenv, mock_emscripten):
    output_dir = tmp_path / "dist"

    pkgs = {
        "pkg_test_tag_always": {},
        "pkg_test_graph1": {"pkg_test_graph2"},
        "pkg_test_graph3": {},
    }

    pkgs_to_build = pkgs.keys() | {p for v in pkgs.values() for p in v} | {"pydecimal"}

    for build_dir in RECIPE_DIR.rglob("build"):
        shutil.rmtree(build_dir)

    app = typer.Typer()
    app.command()(build_recipes.build_recipes)
    for recipe in RECIPE_DIR.glob("**/meta.yaml"):
        recipe.touch()

    result = runner.invoke(
        app,
        [
            *pkgs.keys(),
            "--recipe-dir",
            str(RECIPE_DIR),
            "--install",
            "--install-dir",
            str(output_dir),
        ],
    )
    assert_runner_succeeded(result)

    for pkg in pkgs_to_build:
        assert f"built {pkg} in" in result.stdout

    built_wheels = set(output_dir.glob("*.whl"))
    assert len(built_wheels) == len(pkgs_to_build)


def test_build_recipe_no_deps_plain(tmp_path, dummy_xbuildenv, mock_emscripten):
    for build_dir in RECIPE_DIR.rglob("build"):
        shutil.rmtree(build_dir)

    app = typer.Typer()
    app.command()(build_recipes.build_recipes_no_deps)

    pkgs_to_build = ["pkg_test_graph1", "pkg_test_graph3"]
    for recipe in RECIPE_DIR.glob("**/meta.yaml"):
        recipe.touch()
    result = runner.invoke(
        app,
        [
            *pkgs_to_build,
            "--recipe-dir",
            str(RECIPE_DIR),
        ],
    )
    assert_runner_succeeded(result)

    for pkg in pkgs_to_build:
        assert f"Succeeded building package {pkg}" in result.stdout

    for pkg in pkgs_to_build:
        dist_dir = RECIPE_DIR / pkg / "dist"
        assert len(list(dist_dir.glob("*.whl"))) == 1


def test_build_recipe_no_deps_force_rebuild(tmp_path, dummy_xbuildenv, mock_emscripten):
    for build_dir in RECIPE_DIR.rglob("build"):
        shutil.rmtree(build_dir)

    app = typer.Typer()
    app.command()(build_recipes.build_recipes_no_deps)

    pkg = "pkg_test_graph1"
    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            str(RECIPE_DIR),
        ],
    )
    assert_runner_succeeded(result)

    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            str(RECIPE_DIR),
        ],
    )

    assert_runner_succeeded(result)
    assert f"Succeeded building package {pkg}" in result.stdout

    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            str(RECIPE_DIR),
            "--force-rebuild",
        ],
    )

    assert result.exit_code == 0
    # assert "Creating virtualenv isolated environment" in result.stdout
    assert f"Succeeded building package {pkg}" in result.stdout


def test_build_recipe_no_deps_continue(tmp_path, dummy_xbuildenv, mock_emscripten):
    for build_dir in RECIPE_DIR.rglob("build"):
        shutil.rmtree(build_dir)
    for recipe in RECIPE_DIR.glob("**/meta.yaml"):
        recipe.touch()

    app = typer.Typer()
    app.command()(build_recipes.build_recipes_no_deps)

    pkg = "pkg_test_graph1"
    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            str(RECIPE_DIR),
        ],
    )

    assert_runner_succeeded(result)
    assert f"Succeeded building package {pkg}" in result.stdout

    pyproject_toml = next((RECIPE_DIR / pkg / "build").rglob("pyproject.toml"))

    # Modify some metadata and check it is applied when rebuilt with --continue flag
    with open(pyproject_toml, encoding="utf-8") as f:
        pyproject_data = f.read()

    pyproject_data = pyproject_data.replace(
        "authors = []", 'authors = [{"name" = "Samuel Jackson"}]'
    )
    pyproject_toml.write_text(pyproject_data)

    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            str(RECIPE_DIR),
            "--continue",
        ],
    )

    assert_runner_succeeded(result)
    assert f"Succeeded building package {pkg}" in result.stdout
    wheel = next((RECIPE_DIR / pkg / "dist").rglob("*.whl"))

    metadata = tmp_path / "METADATA"
    common.extract_wheel_metadata_file(wheel, metadata)
    assert metadata.read_text().endswith("Samuel Jackson\n")


def test_config_list(dummy_xbuildenv):
    result = runner.invoke(
        config.app,
        [
            "list",
        ],
    )

    envs = result.stdout.splitlines()
    keys = [env.split("=")[0] for env in envs]

    for cfg_name in PYODIDE_CLI_CONFIGS:
        assert cfg_name in keys


@pytest.mark.parametrize("cfg_name,env_var", PYODIDE_CLI_CONFIGS.items())
def test_config_get(cfg_name, env_var, dummy_xbuildenv):
    result = runner.invoke(
        config.app,
        [
            "get",
            cfg_name,
        ],
    )

    assert result.stdout.strip() == build_env.get_build_flag(env_var)


def test_create_zipfile(temp_python_lib, temp_python_lib2, tmp_path):
    from zipfile import ZipFile

    output = tmp_path / "python.zip"

    app = typer.Typer()
    app.command()(create_zipfile.main)

    result = runner.invoke(
        app,
        [
            str(temp_python_lib),
            str(temp_python_lib2),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Zip file created" in result.stdout
    assert output.exists()

    with ZipFile(output) as zf:
        assert "module1.py" in zf.namelist()
        assert "module2.py" in zf.namelist()
        assert "module3.py" in zf.namelist()
        assert "module4.py" in zf.namelist()


def test_create_zipfile_compile(temp_python_lib, temp_python_lib2, tmp_path):
    from zipfile import ZipFile

    output = tmp_path / "python.zip"

    app = typer.Typer()
    app.command()(create_zipfile.main)

    result = runner.invoke(
        app,
        [
            str(temp_python_lib),
            str(temp_python_lib2),
            "--output",
            str(output),
            "--pycompile",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Zip file created" in result.stdout
    assert output.exists()

    with ZipFile(output) as zf:
        assert "module1.pyc" in zf.namelist()
        assert "module2.pyc" in zf.namelist()
        assert "module3.pyc" in zf.namelist()
        assert "module4.pyc" in zf.namelist()


@pytest.mark.parametrize("target", ["dir", "file"])
@pytest.mark.parametrize("compression_level", [0, 6])
def test_py_compile(tmp_path, target, compression_level):
    wheel_path = tmp_path / "python.zip"
    with zipfile.ZipFile(wheel_path, "w", compresslevel=3) as zf:
        zf.writestr("a1.py", "def f():\n    pass")

    if target == "dir":
        target_path = tmp_path
    elif target == "file":
        target_path = wheel_path

    py_compile.main(
        path=target_path,
        silent=False,
        keep=False,
        compression_level=compression_level,
        exclude="",
    )
    with zipfile.ZipFile(tmp_path / "python.zip", "r") as fh:
        if compression_level > 0:
            assert fh.filelist[0].compress_type == zipfile.ZIP_DEFLATED
        else:
            assert fh.filelist[0].compress_type == zipfile.ZIP_STORED


def test_build1(tmp_path, monkeypatch, dummy_xbuildenv, mock_emscripten):
    from pyodide_build import pypabuild

    def mocked_build(
        srcdir: Path,
        outdir: Path,
        env: Any,
        backend_flags: Any,
        isolation=True,
        skip_dependency_check=False,
    ) -> str:
        results["srcdir"] = srcdir
        results["outdir"] = outdir
        results["backend_flags"] = backend_flags
        dummy_wheel = outdir / "package-1.0.0-py3-none-any.whl"
        return str(dummy_wheel)

    from contextlib import nullcontext

    monkeypatch.setattr(common, "modify_wheel", lambda whl: nullcontext())
    monkeypatch.setattr(
        common, "retag_wheel", lambda wheel_path, platform: Path(wheel_path)
    )
    monkeypatch.setattr(build_env, "check_emscripten_version", lambda: None)
    monkeypatch.setattr(build_env, "replace_so_abi_tags", lambda whl: None)

    monkeypatch.setattr(pypabuild, "build", mocked_build)

    results: dict[str, Any] = {}
    srcdir = tmp_path / "in"
    outdir = tmp_path / "out"
    srcdir.mkdir()
    app = typer.Typer()
    app.command(**build.main.typer_kwargs)(build.main)  # type:ignore[attr-defined]
    result = runner.invoke(app, [str(srcdir), "--outdir", str(outdir), "x", "y", "z"])

    assert result.exit_code == 0, result.stdout
    assert results["srcdir"] == srcdir
    assert results["outdir"] == outdir
    assert results["backend_flags"] == {"x": "", "y": "", "z": ""}


def test_build2_replace_so_abi_tags(
    tmp_path, monkeypatch, dummy_xbuildenv, mock_emscripten
):
    """
    We intentionally include an "so" (actually an empty file) with Linux slug in
    the name into the wheel generated from the package in
    replace_so_abi_tags_test_package. Test that `pyodide build` renames it to
    have the Emscripten slug. In order to ensure that this works on non-linux
    machines too, we monkey patch config vars to look like a linux machine.
    """
    import sysconfig

    config_vars = sysconfig.get_config_vars()
    config_vars["EXT_SUFFIX"] = ".cpython-311-x86_64-linux-gnu.so"
    config_vars["SOABI"] = "cpython-311-x86_64-linux-gnu"

    def my_get_config_vars(*args):
        return config_vars

    monkeypatch.setattr(sysconfig, "get_config_vars", my_get_config_vars)

    srcdir = Path(__file__).parent / "replace_so_abi_tags_test_package"
    outdir = tmp_path / "out"
    app = typer.Typer()
    app.command(**build.main.typer_kwargs)(build.main)  # type:ignore[attr-defined]
    runner.invoke(app, [str(srcdir), "--outdir", str(outdir)])
    wheel_file = next(outdir.glob("*.whl"))
    print(zipfile.ZipFile(wheel_file).namelist())
    so_file = next(
        x for x in zipfile.ZipFile(wheel_file).namelist() if x.endswith(".so")
    )
    assert so_file.endswith(".cpython-311-wasm32-emscripten.so")


def test_build_exports(monkeypatch, dummy_xbuildenv):
    def download_url_shim(url, tmppath):
        (tmppath / "build").mkdir()
        return "blah"

    def unpack_archive_shim(*args):
        pass

    exports_ = None

    def run_shim(
        builddir,
        output_directory,
        exports,
        backend_flags,
        isolation=True,
        skip_dependency_check=False,
    ):
        nonlocal exports_
        exports_ = exports

    monkeypatch.setattr(cli.build, "check_emscripten_version", lambda: None)
    monkeypatch.setattr(cli.build, "download_url", download_url_shim)
    monkeypatch.setattr(shutil, "unpack_archive", unpack_archive_shim)
    monkeypatch.setattr(pyodide_build.out_of_tree.build, "run", run_shim)

    app = typer.Typer()
    app.command()(build.main)

    def run(*args):
        nonlocal exports_
        exports_ = None
        result = runner.invoke(
            app,
            [".", *args],
        )
        print("output", result.output)
        return result

    run()
    assert exports_ == "requested"
    r = run("--exports", "pyinit")
    assert r.exit_code == 0
    assert exports_ == "pyinit"
    r = run("--exports", "a,")
    assert r.exit_code == 0
    assert exports_ == ["a"]
    monkeypatch.setenv("PYODIDE_BUILD_EXPORTS", "whole_archive")
    r = run()
    assert r.exit_code == 0
    assert exports_ == "whole_archive"
    r = run("--exports", "a,")
    assert r.exit_code == 0
    assert exports_ == ["a"]
    r = run("--exports", "a,b,c")
    assert r.exit_code == 0
    assert exports_ == ["a", "b", "c"]
    r = run("--exports", "x")
    assert r.exit_code == 1
    assert (
        r.output.strip().replace("\n", " ").replace("  ", " ")
        == 'Expected exports to be one of "pyinit", "requested", "whole_archive", or a comma separated list of symbols to export. Got "x".'
    )


def test_build_config_settings(monkeypatch, dummy_xbuildenv):
    app = typer.Typer()

    app.command(
        context_settings={
            "ignore_unknown_options": True,
            "allow_extra_args": True,
        }
    )(build.main)

    config_settings_passed = None

    def run(
        srcdir,
        outdir,
        exports,
        config_settings,
        isolation=True,
        skip_dependency_check=False,
    ):
        nonlocal config_settings_passed
        config_settings_passed = config_settings

    monkeypatch.setattr(cli.build, "check_emscripten_version", lambda: None)
    monkeypatch.setattr(pyodide_build.out_of_tree.build, "run", run)

    # Accept `-C`
    result = runner.invoke(
        app,
        [".", "-C--key1", "-C--key2=value2", "-C=value3", "-Ckey4=value4"],
    )

    assert result.exit_code == 0, result.stdout
    assert config_settings_passed == {
        "--key1": "",
        "--key2": "value2",
        "": "value3",
        "key4": "value4",
    }

    result = runner.invoke(
        app,
        [
            ".",
            "--config-setting",
            "--key1",
            "--config-setting=--key2=--value2",
            "--config-setting=key3",
            "--config-setting",
            "--key4=--value4",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert config_settings_passed == {
        "--key1": "",
        "--key2": "--value2",
        "key3": "",
        "--key4": "--value4",
    }

    # For backwards compatibility, extra flags are interpreted as config settings
    result = runner.invoke(
        app,
        [
            ".",
            "-C--key1=value1",
            "--config-setting=--key2=value2",
            "--key3",
            "--key4=--value4",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert config_settings_passed == {
        "--key1": "value1",
        "--key2": "value2",
        "--key3": "",
        "--key4": "--value4",
    }


def test_build_cpython_module(tmp_path, dummy_xbuildenv, mock_emscripten):
    for build_dir in RECIPE_DIR.rglob("build"):
        shutil.rmtree(build_dir)

    app = typer.Typer()
    app.command()(build_recipes.build_recipes_no_deps)

    pkg = "pydecimal"
    for recipe in RECIPE_DIR.glob("**/meta.yaml"):
        recipe.touch()
    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            str(RECIPE_DIR),
        ],
    )
    assert_runner_succeeded(result)

    assert f"Succeeded building package {pkg}" in result.stdout

    dist_dir = RECIPE_DIR / pkg / "dist"
    results = list(dist_dir.glob("*.whl"))
    assert len(results) == 1
    result = results[0]
    assert result.name == "pydecimal-1.0.0-cp312-cp312-pyodide_2024_0_wasm32.whl"


def test_wheel_download_version_mismatch(tmp_path, dummy_xbuildenv, mock_emscripten):
    for build_dir in RECIPE_DIR.rglob("build"):
        shutil.rmtree(build_dir)

    app = typer.Typer()
    app.command()(build_recipes.build_recipes_no_deps)

    pkg = "xarray"
    for recipe in RECIPE_DIR.glob("**/meta.yaml"):
        recipe.touch()
    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            str(RECIPE_DIR),
        ],
    )
    assert result.exit_code == 1
    assert (
        result.exception.args[0]
        == "Version mismatch in xarray: version in meta.yaml is '2025.01.2' but version from wheel name is '2025.1.2'"
    )


def test_wheel_build_version_mismatch(tmp_path, dummy_xbuildenv, mock_emscripten):
    for build_dir in RECIPE_DIR.rglob("build"):
        shutil.rmtree(build_dir)

    app = typer.Typer()
    app.command()(build_recipes.build_recipes_no_deps)

    pkg = "pkg_test_version_mismatch"
    for recipe in RECIPE_DIR.glob("**/meta.yaml"):
        recipe.touch()
    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            str(RECIPE_DIR),
        ],
    )
    assert result.exit_code == 1
    assert (
        result.exception.args[0]
        == "Version mismatch in pkg_test_version_mismatch: version in meta.yaml is '1.0.0' but version from wheel name is '1.0.1'"
    )


def test_build_constraint(tmp_path, dummy_xbuildenv, mock_emscripten, capsys):
    for build_dir in RECIPE_DIR.rglob("build"):
        shutil.rmtree(build_dir)

    app = typer.Typer()
    app.command()(build_recipes.build_recipes_no_deps)

    pkg = "pkg_test_constraint"
    for recipe in RECIPE_DIR.glob("**/meta.yaml"):
        recipe.touch()
    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            str(RECIPE_DIR),
        ],
    )
    assert_runner_succeeded(result)

    assert f"Succeeded building package {pkg}" in result.stdout
    build_dir = RECIPE_DIR / pkg / "build"
    assert (build_dir / "setuptools.version").read_text() == "74.1.3"
    assert (build_dir / "pytest.version").read_text() == "7.0.0"


@pytest.mark.parametrize(
    "isolation_flag",
    [
        None,
        "--no-isolation",
    ],
)
def test_build_isolation_flags(
    tmp_path, monkeypatch, dummy_xbuildenv, mock_emscripten, isolation_flag
):
    """Test that build works with different isolation flags."""
    from pyodide_build import pypabuild

    build_calls = []

    def mocked_build(
        srcdir,
        outdir,
        env,
        config_settings,
        isolation=True,
        skip_dependency_check=False,
    ):
        build_calls.append(
            {
                "srcdir": srcdir,
                "isolation": isolation,
                "skip_dependency_check": skip_dependency_check,
            }
        )
        dummy_wheel = outdir / "package-1.0.0-py3-none-any.whl"
        return str(dummy_wheel)

    monkeypatch.setattr(pypabuild, "build", mocked_build)
    monkeypatch.setattr(build_env, "check_emscripten_version", lambda: None)
    monkeypatch.setattr(build_env, "replace_so_abi_tags", lambda whl: None)
    monkeypatch.setattr(
        common, "retag_wheel", lambda wheel_path, platform: Path(wheel_path)
    )

    from contextlib import nullcontext

    monkeypatch.setattr(common, "modify_wheel", lambda whl: nullcontext())

    app = typer.Typer()
    app.command(**build.main.typer_kwargs)(build.main)  # type:ignore[attr-defined]

    srcdir = tmp_path / "in"
    outdir = tmp_path / "out"
    srcdir.mkdir()

    args = [str(srcdir), "--outdir", str(outdir)]
    if isolation_flag:
        args.append(isolation_flag)

    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.stdout
    assert len(build_calls) == 1

    # Check that isolation was properly passed
    expected_isolation = isolation_flag is None
    assert build_calls[0]["isolation"] == expected_isolation


@pytest.mark.parametrize(
    "skip_check_flag",
    [
        None,  # Default: with dependency check
        "--skip-dependency-check",
        "-x",
    ],
)
def test_build_skip_dependency_check(
    tmp_path, monkeypatch, dummy_xbuildenv, mock_emscripten, skip_check_flag
):
    """Test that build works with different skip dependency check flags."""
    from pyodide_build import pypabuild

    build_calls = []

    def mocked_build(
        srcdir,
        outdir,
        env,
        config_settings,
        isolation=True,
        skip_dependency_check=False,
    ):
        build_calls.append(
            {
                "srcdir": srcdir,
                "isolation": isolation,
                "skip_dependency_check": skip_dependency_check,
            }
        )
        dummy_wheel = outdir / "package-1.0.0-py3-none-any.whl"
        return str(dummy_wheel)

    monkeypatch.setattr(pypabuild, "build", mocked_build)
    monkeypatch.setattr(build_env, "check_emscripten_version", lambda: None)
    monkeypatch.setattr(build_env, "replace_so_abi_tags", lambda whl: None)
    monkeypatch.setattr(
        common, "retag_wheel", lambda wheel_path, platform: Path(wheel_path)
    )

    from contextlib import nullcontext

    monkeypatch.setattr(common, "modify_wheel", lambda whl: nullcontext())

    app = typer.Typer()
    app.command(**build.main.typer_kwargs)(build.main)  # type:ignore[attr-defined]

    srcdir = tmp_path / "in"
    outdir = tmp_path / "out"
    srcdir.mkdir()

    args = [str(srcdir), "--outdir", str(outdir)]
    if skip_check_flag:
        args.append(skip_check_flag)

    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.stdout
    assert len(build_calls) == 1

    # Check that skip_dependency_check was properly passed
    expected_skip = skip_check_flag is not None
    assert build_calls[0]["skip_dependency_check"] == expected_skip


@pytest.mark.parametrize(
    "isolation,skip_check",
    [
        (True, False),  # default: with isolation, without skipping dependency checking
        (False, False),
        (True, True),
        (False, True),
    ],
)
def test_build_combined_flags(
    tmp_path, monkeypatch, dummy_xbuildenv, mock_emscripten, isolation, skip_check
):
    """Test combinations of isolation and skip dependency check flags."""
    from pyodide_build import pypabuild

    build_calls = []

    def mocked_build(
        srcdir,
        outdir,
        env,
        config_settings,
        isolation=True,
        skip_dependency_check=False,
    ):
        build_calls.append(
            {
                "srcdir": srcdir,
                "isolation": isolation,
                "skip_dependency_check": skip_dependency_check,
            }
        )
        dummy_wheel = outdir / "package-1.0.0-py3-none-any.whl"
        return str(dummy_wheel)

    monkeypatch.setattr(pypabuild, "build", mocked_build)
    monkeypatch.setattr(build_env, "check_emscripten_version", lambda: None)
    monkeypatch.setattr(build_env, "replace_so_abi_tags", lambda whl: None)
    monkeypatch.setattr(
        common, "retag_wheel", lambda wheel_path, platform: Path(wheel_path)
    )

    from contextlib import nullcontext

    monkeypatch.setattr(common, "modify_wheel", lambda whl: nullcontext())

    app = typer.Typer()
    app.command(**build.main.typer_kwargs)(build.main)  # type:ignore[attr-defined]

    srcdir = tmp_path / "in"
    outdir = tmp_path / "out"
    srcdir.mkdir()

    args = [str(srcdir), "--outdir", str(outdir)]
    if not isolation:
        args.append("--no-isolation")
    if skip_check:
        args.append("--skip-dependency-check")

    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.stdout
    assert len(build_calls) == 1
    assert build_calls[0]["isolation"] == isolation
    assert build_calls[0]["skip_dependency_check"] == skip_check
