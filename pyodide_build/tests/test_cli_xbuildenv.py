import json
import os
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner
from pyodide_lock import PyodideLockSpec

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

    assert result.exit_code == 0, result.output
    assert "Downloading Pyodide cross-build environment" in result.output, result.output
    assert "Installing Pyodide cross-build environment" in result.output, result.output
    assert str(envpath.resolve()) in result.output, result.output
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

    assert result.exit_code == 0, result.output
    assert "Pyodide cross-build environment installed at" in result.output, (
        result.output
    )
    assert str(envpath.resolve()) in result.output, result.output
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
    assert result.exit_code != 0, result.output

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

    assert result.exit_code == 0, result.output
    assert "Pyodide cross-build environment installed at" in result.output, (
        result.output
    )
    assert str(envpath.resolve()) in result.output, result.output
    assert (envpath / "xbuildenv").is_symlink()
    assert (envpath / "xbuildenv").resolve().exists()
    assert (envpath / "0.1.0").exists()

    concrete_path = (envpath / "xbuildenv").resolve()
    assert (concrete_path / ".installed").exists()

    os.environ.pop(CROSS_BUILD_ENV_METADATA_URL_ENV_VAR, None)


def test_xbuildenv_install_nightly(tmp_path, mock_xbuildenv_url, monkeypatch):
    """Installing with --nightly uses the nightly metadata URL, not stable."""
    from pyodide_build import build_env

    envpath = Path(tmp_path) / ".xbuildenv"
    local = build_env.local_versions()

    nightly_data = {
        "releases": {
            "20260520": {
                "version": "20260520",
                "url": mock_xbuildenv_url,
                "sha256": None,
                "python_version": f"{local['python']}.0",
                "emscripten_version": "5.0.3",
                "published_at": "2026-05-20T04:40:12Z",
                "min_pyodide_build_version": None,
                "max_pyodide_build_version": None,
            }
        }
    }
    metadata_path = tmp_path / "nightly.json"
    metadata_path.write_text(json.dumps(nightly_data))

    monkeypatch.setattr(
        "pyodide_build.cli.xbuildenv.NIGHTLY_CROSS_BUILD_ENV_METADATA_URL",
        str(metadata_path),
    )

    result = runner.invoke(
        xbuildenv.app,
        ["install", "20260520", "--path", str(envpath), "--nightly"],
    )

    assert result.exit_code == 0, result.output
    assert "Pyodide cross-build environment installed at" in result.output
    assert str(envpath.resolve()) in result.output
    assert (envpath / "xbuildenv").is_symlink()
    assert (envpath / "20260520").exists()


def test_xbuildenv_install_debug(tmp_path, mock_xbuildenv_url, monkeypatch):
    """Installing with --debug uses the nightly-debug metadata URL, not stable."""
    from pyodide_build import build_env

    envpath = Path(tmp_path) / ".xbuildenv"
    local = build_env.local_versions()

    debug_data = {
        "releases": {
            "20260520": {
                "version": "20260520",
                "url": mock_xbuildenv_url,
                "sha256": None,
                "python_version": f"{local['python']}.0",
                "emscripten_version": "5.0.3",
                "published_at": "2026-05-20T04:40:12Z",
                "min_pyodide_build_version": None,
                "max_pyodide_build_version": None,
            }
        }
    }
    metadata_path = tmp_path / "nightly-debug.json"
    metadata_path.write_text(json.dumps(debug_data))

    monkeypatch.setattr(
        "pyodide_build.cli.xbuildenv.NIGHTLY_DEBUG_CROSS_BUILD_ENV_METADATA_URL",
        str(metadata_path),
    )

    result = runner.invoke(
        xbuildenv.app,
        ["install", "20260520", "--path", str(envpath), "--debug"],
    )

    assert result.exit_code == 0, result.output
    assert "Pyodide cross-build environment installed at" in result.output
    assert str(envpath.resolve()) in result.output
    assert (envpath / "xbuildenv").is_symlink()
    assert (envpath / "20260520").exists()


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

    assert result.exit_code == 0, result.output
    assert "0.26.0" in result.output, result.output


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

    assert result.exit_code == 0, result.output
    assert "  0.25.0" in result.output, result.output
    assert "  0.25.1" in result.output, result.output
    assert "* 0.26.0" in result.output, result.output


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

    assert result.exit_code == 0, result.output
    assert "Pyodide cross-build environment 0.25.0 is now in use" in result.output, (
        result.output
    )


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

    assert result.exit_code == 0, result.output
    assert "Pyodide cross-build environment 0.25.0 uninstalled" in result.output, (
        result.output
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "uninstall",
            "0.26.0",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Pyodide cross-build environment 0.26.0 uninstalled" in result.output, (
        result.output
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "uninstall",
            "0.26.1",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code != 0, result.output
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

    assert result.exit_code == 0, result.output
    assert "0.1.0" in result.output, result.output

    result = runner.invoke(
        xbuildenv.app,
        [
            "search",
            "--metadata",
            str(fake_xbuildenv_releases_incompatible),
        ],
    )

    assert result.exit_code != 0, result.output
    assert (
        "No compatible cross-build environment found for your system" in result.output
    )
    assert "0.1.0" not in result.output, result.output

    result = runner.invoke(
        xbuildenv.app,
        [
            "search",
            "--metadata",
            str(fake_xbuildenv_releases_incompatible),
            "--all",
        ],
    )

    assert result.exit_code == 0, result.output

    lines = result.output.splitlines()
    header = lines[1].strip().split("│")[1:-1]
    assert [col.strip() for col in header] == [
        "Version",
        "Python",
        "Emscripten",
        "pyodide-build",
        "Published",
        "Compatible",
    ]

    row1 = lines[3].strip().split("│")[1:-1]
    assert [col.strip() for col in row1] == ["0.1.0", "4.5.6", "1.39.8", "-", "", "No"]


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
    assert result.exit_code == 0, result.output
    assert is_valid_json(result.output), "Output is not valid JSON"

    output = json.loads(result.output)

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
            "published_at",
            "compatible",
        }, f"Environment {environment} has unexpected keys: {environment.keys()}"

        assert isinstance(environment["version"], str), "version should be a string"
        assert isinstance(environment["python"], str), "python should be a string"
        assert isinstance(environment["emscripten"], str), (
            "emscripten should be a string"
        )
        assert isinstance(environment["compatible"], bool), (
            "compatible should be either True or False"
        )

        assert isinstance(environment["pyodide_build"], dict), (
            "pyodide_build should be a dictionary"
        )
        assert set(environment["pyodide_build"].keys()) == {
            "min",
            "max",
        }, f"pyodide_build has unexpected keys: {environment['pyodide_build'].keys()}"
        assert isinstance(environment["pyodide_build"]["min"], (str, type(None))), (
            "pyodide_build-min should be a string or None"
        )
        assert isinstance(environment["pyodide_build"]["max"], (str, type(None))), (
            "pyodide_build-max should be a string or None"
        )

    assert any(env["compatible"] for env in output["environments"]), (
        "There should be at least one compatible environment"
    )


@pytest.fixture
def fake_nightly_release_metadata(tmp_path):
    """Fake nightly release metadata (non-debug), two entries: one compatible, one not."""
    from pyodide_build import build_env

    local = build_env.local_versions()
    data = {
        "releases": {
            "20260520": {
                "version": "20260520",
                "url": "https://example.com/20260520/xbuildenv.tar.bz2",
                "sha256": "abc123",
                "python_version": f"{local['python']}.0",
                "emscripten_version": "5.0.3",
                "published_at": "2026-05-20T04:40:12Z",
                "min_pyodide_build_version": "0.26.0",
                "max_pyodide_build_version": None,
            },
            "20250101": {
                "version": "20250101",
                "url": "https://example.com/20250101/xbuildenv.tar.bz2",
                "sha256": "def456",
                "python_version": "3.12.0",
                "emscripten_version": "3.1.58",
                "published_at": "2025-01-01T02:53:30Z",
                "min_pyodide_build_version": "0.26.0",
                "max_pyodide_build_version": None,
            },
        }
    }
    path = tmp_path / "nightly-release.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def fake_nightly_debug_metadata(tmp_path):
    """Fake nightly debug metadata — only entries that have a debug build."""
    from pyodide_build import build_env

    local = build_env.local_versions()
    data = {
        "releases": {
            "20260520": {
                "version": "20260520",
                "url": "https://example.com/20260520/xbuildenv-debug.tar.bz2",
                "sha256": "debug_abc123",
                "python_version": f"{local['python']}.0",
                "emscripten_version": "5.0.3",
                "published_at": "2026-05-20T04:40:12Z",
                "min_pyodide_build_version": "0.26.0",
                "max_pyodide_build_version": None,
            },
        }
    }
    path = tmp_path / "nightly-debug.json"
    path.write_text(json.dumps(data))
    return path


def test_xbuildenv_search_nightly(
    tmp_path,
    fake_xbuildenv_releases_compatible,
    fake_nightly_release_metadata,
    monkeypatch,
):
    monkeypatch.setattr(
        "pyodide_build.cli.xbuildenv.NIGHTLY_CROSS_BUILD_ENV_METADATA_URL",
        str(fake_nightly_release_metadata),
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "search",
            "--metadata",
            str(fake_xbuildenv_releases_compatible),
            "--nightly",
            "--all",
        ],
    )

    assert result.exit_code == 0, result.output

    lines = result.output.splitlines()
    header = lines[1].strip().split("│")[1:-1]
    assert [col.strip() for col in header] == [
        "Version",
        "Python",
        "Emscripten",
        "pyodide-build",
        "Published",
        "Compatible",
        "Source",
    ]

    # Only nightly entries should be present. Stable versions are not mixed in.
    assert "0.1.0" not in result.output
    assert "0.2.0" not in result.output
    assert "20260520" in result.output
    assert "20250101" in result.output
    assert "stable" not in result.output
    assert "nightly" in result.output


def test_xbuildenv_search_debug(
    tmp_path,
    fake_xbuildenv_releases_compatible,
    fake_nightly_debug_metadata,
    monkeypatch,
):
    monkeypatch.setattr(
        "pyodide_build.cli.xbuildenv.NIGHTLY_DEBUG_CROSS_BUILD_ENV_METADATA_URL",
        str(fake_nightly_debug_metadata),
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "search",
            "--metadata",
            str(fake_xbuildenv_releases_compatible),
            "--debug",
            "--all",
        ],
    )

    assert result.exit_code == 0, result.output

    # Only nightly-debug entries should be present. Stable and nightly-release versions
    # are not mixed in. 20250101 is absent because it has no debug build (not in the
    # debug metadata file).
    assert "stable" not in result.output
    assert "nightly-debug" in result.output
    assert "20260520" in result.output
    assert "20250101" not in result.output


def test_xbuildenv_search_nightly_json(
    tmp_path,
    fake_xbuildenv_releases_compatible,
    fake_nightly_release_metadata,
    fake_nightly_debug_metadata,
    monkeypatch,
):
    monkeypatch.setattr(
        "pyodide_build.cli.xbuildenv.NIGHTLY_CROSS_BUILD_ENV_METADATA_URL",
        str(fake_nightly_release_metadata),
    )
    monkeypatch.setattr(
        "pyodide_build.cli.xbuildenv.NIGHTLY_DEBUG_CROSS_BUILD_ENV_METADATA_URL",
        str(fake_nightly_debug_metadata),
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "search",
            "--metadata",
            str(fake_xbuildenv_releases_compatible),
            "--nightly",
            "--debug",
            "--all",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert is_valid_json(result.output)

    output = json.loads(result.output)
    sources = {env["source"] for env in output["environments"]}
    assert sources == {"nightly", "nightly-debug"}

    for env in output["environments"]:
        assert "debug_url" not in env
        assert "debug_sha256" not in env
