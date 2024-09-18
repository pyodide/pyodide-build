import json
import os
import shutil
from pathlib import Path

import pytest
from pyodide_lock import PyodideLockSpec
from typer.testing import CliRunner

from pyodide_build.cli import (
    xbuildenv,
)
from pyodide_build.common import chdir
from pyodide_build.xbuildenv_releases import CROSS_BUILD_ENV_METADATA_URL_ENV_VAR


def mock_pyodide_lock() -> PyodideLockSpec:
    return PyodideLockSpec(
        info={
            "version": "0.22.1",
            "arch": "wasm32",
            "platform": "emscripten_xxx",
            "python": "3.11",
        },
        packages={},
    )


def is_valid_json(json_str) -> bool:
    try:
        json.loads(json_str)
    except json.JSONDecodeError:
        return False
    return True


@pytest.fixture()
def mock_xbuildenv_url(tmp_path_factory, httpserver):
    """
    Create a temporary xbuildenv archive
    """
    base = tmp_path_factory.mktemp("base")

    path = Path(base)

    xbuildenv = path / "xbuildenv"
    xbuildenv.mkdir()

    pyodide_root = xbuildenv / "pyodide-root"
    site_packages_extra = xbuildenv / "site-packages-extras"
    requirements_txt = xbuildenv / "requirements.txt"

    pyodide_root.mkdir()
    site_packages_extra.mkdir()
    requirements_txt.touch()

    (pyodide_root / "Makefile.envs").write_text(
        """
export HOSTSITEPACKAGES=$(PYODIDE_ROOT)/packages/.artifacts/lib/python$(PYMAJOR).$(PYMINOR)/site-packages

.output_vars:
	set
"""  # noqa: W191
    )
    (pyodide_root / "dist").mkdir()
    mock_pyodide_lock().to_json(pyodide_root / "dist" / "pyodide-lock.json")

    with chdir(base):
        archive_name = shutil.make_archive("xbuildenv", "tar")

    content = Path(base / archive_name).read_bytes()
    httpserver.expect_request("/xbuildenv-mock.tar").respond_with_data(content)
    yield httpserver.url_for("/xbuildenv-mock.tar")


runner = CliRunner()


def test_xbuildenv_install(tmp_path, mock_xbuildenv_url):
    envpath = Path(tmp_path) / ".xbuildenv"

    result = runner.invoke(
        xbuildenv.app,
        [
            "install",
            "--path",
            str(envpath),
            "--url",
            mock_xbuildenv_url,
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Downloading Pyodide cross-build environment" in result.stdout, result.stdout
    assert "Installing Pyodide cross-build environment" in result.stdout, result.stdout
    assert (envpath / "xbuildenv").is_symlink()
    assert (envpath / "xbuildenv").resolve().exists()

    concrete_path = (envpath / "xbuildenv").resolve()
    assert (concrete_path / ".installed").exists()


def test_xbuildenv_install_version(tmp_path, fake_xbuildenv_releases_compatible):
    envpath = Path(tmp_path) / ".xbuildenv"

    os.environ.pop(CROSS_BUILD_ENV_METADATA_URL_ENV_VAR, None)
    os.environ[CROSS_BUILD_ENV_METADATA_URL_ENV_VAR] = str(
        fake_xbuildenv_releases_compatible
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "install",
            "0.1.0",
            "--path",
            str(envpath),
        ],
    )

    os.environ.pop(CROSS_BUILD_ENV_METADATA_URL_ENV_VAR, None)

    assert result.exit_code == 0, result.stdout
    assert "Downloading Pyodide cross-build environment" in result.stdout, result.stdout
    assert "Installing Pyodide cross-build environment" in result.stdout, result.stdout
    assert (envpath / "xbuildenv").is_symlink()
    assert (envpath / "xbuildenv").resolve().exists()
    assert (envpath / "0.1.0").exists()

    concrete_path = (envpath / "xbuildenv").resolve()
    assert (concrete_path / ".installed").exists()


def test_xbuildenv_install_force_install(
    tmp_path, fake_xbuildenv_releases_incompatible
):
    envpath = Path(tmp_path) / ".xbuildenv"

    os.environ.pop(CROSS_BUILD_ENV_METADATA_URL_ENV_VAR, None)
    os.environ[CROSS_BUILD_ENV_METADATA_URL_ENV_VAR] = str(
        fake_xbuildenv_releases_incompatible
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "install",
            "0.1.0",
            "--path",
            str(envpath),
        ],
    )

    # should fail if no force option is given
    assert result.exit_code != 0, result.stdout

    result = runner.invoke(
        xbuildenv.app,
        [
            "install",
            "0.1.0",
            "--path",
            str(envpath),
            "--force",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Downloading Pyodide cross-build environment" in result.stdout, result.stdout
    assert "Installing Pyodide cross-build environment" in result.stdout, result.stdout
    assert (envpath / "xbuildenv").is_symlink()
    assert (envpath / "xbuildenv").resolve().exists()
    assert (envpath / "0.1.0").exists()

    concrete_path = (envpath / "xbuildenv").resolve()
    assert (concrete_path / ".installed").exists()

    os.environ.pop(CROSS_BUILD_ENV_METADATA_URL_ENV_VAR, None)


def test_xbuildenv_version(tmp_path):
    envpath = Path(tmp_path) / ".xbuildenv"

    (envpath / "0.25.0").mkdir(exist_ok=True, parents=True)
    (envpath / "0.25.1").mkdir(exist_ok=True, parents=True)
    (envpath / "0.26.0").mkdir(exist_ok=True, parents=True)
    (envpath / "xbuildenv").symlink_to(envpath / "0.26.0")

    result = runner.invoke(
        xbuildenv.app,
        [
            "version",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "0.26.0" in result.stdout, result.stdout


def test_xbuildenv_versions(tmp_path):
    envpath = Path(tmp_path) / ".xbuildenv"

    (envpath / "0.25.0").mkdir(exist_ok=True, parents=True)
    (envpath / "0.25.1").mkdir(exist_ok=True, parents=True)
    (envpath / "0.26.0").mkdir(exist_ok=True, parents=True)
    (envpath / "xbuildenv").symlink_to(envpath / "0.26.0")

    result = runner.invoke(
        xbuildenv.app,
        [
            "versions",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "  0.25.0" in result.stdout, result.stdout
    assert "  0.25.1" in result.stdout, result.stdout
    assert "* 0.26.0" in result.stdout, result.stdout


def test_xbuildenv_use(tmp_path):
    envpath = Path(tmp_path) / ".xbuildenv"

    (envpath / "0.25.0").mkdir(exist_ok=True, parents=True)
    (envpath / "0.25.1").mkdir(exist_ok=True, parents=True)
    (envpath / "0.26.0").mkdir(exist_ok=True, parents=True)
    (envpath / "xbuildenv").symlink_to(envpath / "0.26.0")

    result = runner.invoke(
        xbuildenv.app,
        [
            "use",
            "0.25.0",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert (
        "Pyodide cross-build environment 0.25.0 is now in use" in result.stdout
    ), result.stdout


def test_xbuildenv_uninstall(tmp_path):
    envpath = Path(tmp_path) / ".xbuildenv"

    (envpath / "0.25.0").mkdir(exist_ok=True, parents=True)
    (envpath / "0.25.1").mkdir(exist_ok=True, parents=True)
    (envpath / "0.26.0").mkdir(exist_ok=True, parents=True)
    (envpath / "xbuildenv").symlink_to(envpath / "0.26.0")

    result = runner.invoke(
        xbuildenv.app,
        [
            "uninstall",
            "0.25.0",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert (
        "Pyodide cross-build environment 0.25.0 uninstalled" in result.stdout
    ), result.stdout

    result = runner.invoke(
        xbuildenv.app,
        [
            "uninstall",
            "0.26.0",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert (
        "Pyodide cross-build environment 0.26.0 uninstalled" in result.stdout
    ), result.stdout

    result = runner.invoke(
        xbuildenv.app,
        [
            "uninstall",
            "0.26.1",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code != 0, result.stdout
    assert isinstance(result.exception, ValueError), result.exception


def test_xbuildenv_search(
    tmp_path, fake_xbuildenv_releases_compatible, fake_xbuildenv_releases_incompatible
):
    result = runner.invoke(
        xbuildenv.app,
        [
            "search",
            "--metadata",
            str(fake_xbuildenv_releases_compatible),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "0.1.0" in result.stdout, result.stdout

    result = runner.invoke(
        xbuildenv.app,
        [
            "search",
            "--metadata",
            str(fake_xbuildenv_releases_incompatible),
        ],
    )

    assert result.exit_code != 0, result.stdout
    assert (
        "No compatible cross-build environment found for your system" in result.stdout
    )
    assert "0.1.0" not in result.stdout, result.stdout

    result = runner.invoke(
        xbuildenv.app,
        [
            "search",
            "--metadata",
            str(fake_xbuildenv_releases_incompatible),
            "--all",
        ],
    )

    assert result.exit_code == 0, result.stdout

    lines = result.stdout.splitlines()
    header = lines[1].strip().split("│")[1:-1]
    assert [col.strip() for col in header] == [
        "Version",
        "Python",
        "Emscripten",
        "pyodide-build",
        "Compatible",
    ]

    row1 = lines[3].strip().split("│")[1:-1]
    assert [col.strip() for col in row1] == ["0.1.0", "4.5.6", "1.39.8", "-", "No"]


def test_xbuildenv_search_json(tmp_path, fake_xbuildenv_releases_compatible):
    result = runner.invoke(
        xbuildenv.app,
        [
            "search",
            "--metadata",
            str(fake_xbuildenv_releases_compatible),
            "--json",
            "--all",
        ],
    )

    # Sanity check
    assert result.exit_code == 0, result.stdout
    assert is_valid_json(result.stdout), "Output is not valid JSON"

    output = json.loads(result.stdout)

    # First, check overall structure of JSON response
    assert isinstance(output, dict), "Output should be a dictionary"
    assert "environments" in output, "Output should have an 'environments' key"
    assert isinstance(output["environments"], list), "'environments' should be a list"

    # Now, we'll check types in each environment entry
    for environment in output["environments"]:
        assert isinstance(environment, dict), "Each environment should be a dictionary"
        assert set(environment.keys()) == {
            "version",
            "python",
            "emscripten",
            "pyodide_build",
            "compatible",
        }, f"Environment {environment} has unexpected keys: {environment.keys()}"

        assert isinstance(environment["version"], str), "version should be a string"
        assert isinstance(environment["python"], str), "python should be a string"
        assert isinstance(
            environment["emscripten"], str
        ), "emscripten should be a string"
        assert isinstance(
            environment["compatible"], bool
        ), "compatible should be either True or False"

        assert isinstance(
            environment["pyodide_build"], dict
        ), "pyodide_build should be a dictionary"
        assert set(environment["pyodide_build"].keys()) == {
            "min",
            "max",
        }, f"pyodide_build has unexpected keys: {environment['pyodide_build'].keys()}"
        assert isinstance(
            environment["pyodide_build"]["min"], (str, type(None))
        ), "pyodide_build-min should be a string or None"
        assert isinstance(
            environment["pyodide_build"]["max"], (str, type(None))
        ), "pyodide_build-max should be a string or None"

    assert any(
        env["compatible"] for env in output["environments"]
    ), "There should be at least one compatible environment"
