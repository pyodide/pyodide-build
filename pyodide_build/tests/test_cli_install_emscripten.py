"""Tests for install-emscripten CLI command"""

import subprocess
from pathlib import Path

from click.testing import CliRunner

from pyodide_build.cli import xbuildenv

runner = CliRunner()


def test_install_emscripten_no_xbuildenv(tmp_path):
    """Test that install-emscripten fails when no xbuildenv exists"""
    envpath = Path(tmp_path) / ".xbuildenv"

    result = runner.invoke(
        xbuildenv.app,
        [
            "install-emscripten",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code != 0, result.output
    assert "Cross-build environment not found" in result.output, result.output


def test_install_emscripten_default_version(tmp_path, monkeypatch):
    """Test installing Emscripten with default version"""
    envpath = Path(tmp_path) / ".xbuildenv"
    envpath.mkdir()

    monkeypatch.setattr(
        "pyodide_build.cli.xbuildenv.get_build_flag",
        lambda name: "3.1.46",
    )

    called = {}

    def fake_install(self, version):
        called["version"] = version
        return self.env_dir / "emsdk"

    monkeypatch.setattr(
        "pyodide_build.xbuildenv.CrossBuildEnvManager.install_emscripten",
        fake_install,
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "install-emscripten",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Installing emsdk..." in result.output, result.output
    assert "Installing emsdk complete." in result.output, result.output
    assert "Use `source" in result.output, result.output
    assert "emsdk_env.sh` to set up the environment." in result.output, result.output
    assert called["version"] == "3.1.46"


def test_install_emscripten_specific_version(tmp_path, monkeypatch):
    """Test installing Emscripten with a specific version"""
    envpath = Path(tmp_path) / ".xbuildenv"
    envpath.mkdir()

    called = {}

    def fake_install(self, version):
        called["version"] = version
        return self.env_dir / "emsdk"

    monkeypatch.setattr(
        "pyodide_build.xbuildenv.CrossBuildEnvManager.install_emscripten",
        fake_install,
    )

    emscripten_version = "3.1.46"
    result = runner.invoke(
        xbuildenv.app,
        [
            "install-emscripten",
            "--version",
            emscripten_version,
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Installing emsdk..." in result.output, result.output
    assert "Installing emsdk complete." in result.output, result.output
    assert called["version"] == emscripten_version


def test_install_emscripten_with_existing_emsdk(tmp_path, monkeypatch):
    """Test installing Emscripten when emsdk already exists (should pull updates)"""
    envpath = Path(tmp_path) / ".xbuildenv"
    envpath.mkdir()

    existing_emsdk = envpath / "emsdk"
    existing_emsdk.mkdir()

    monkeypatch.setattr(
        "pyodide_build.cli.xbuildenv.get_build_flag",
        lambda name: "latest",
    )

    def fake_install(self, version):
        assert version == "latest"
        assert existing_emsdk.exists()
        return existing_emsdk

    monkeypatch.setattr(
        "pyodide_build.xbuildenv.CrossBuildEnvManager.install_emscripten",
        fake_install,
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "install-emscripten",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Installing emsdk..." in result.output, result.output
    assert "Installing emsdk complete." in result.output, result.output
    assert str(existing_emsdk / "emsdk_env.sh") in result.output


def test_install_emscripten_git_failure(tmp_path, monkeypatch):
    """Test handling of git clone failure"""
    envpath = Path(tmp_path) / ".xbuildenv"
    envpath.mkdir()

    monkeypatch.setattr(
        "pyodide_build.xbuildenv.CrossBuildEnvManager.install_emscripten",
        lambda self, version: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, "git clone")
        ),
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "install-emscripten",
            "--path",
            str(envpath),
        ],
    )

    # Should fail due to git clone error
    assert result.exit_code != 0
    assert isinstance(result.exception, subprocess.CalledProcessError)


def test_install_emscripten_emsdk_install_failure(tmp_path, monkeypatch):
    """Test handling of emsdk install command failure"""
    envpath = Path(tmp_path) / ".xbuildenv"
    envpath.mkdir()

    monkeypatch.setattr(
        "pyodide_build.xbuildenv.CrossBuildEnvManager.install_emscripten",
        lambda self, version: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, "./emsdk install")
        ),
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "install-emscripten",
            "--path",
            str(envpath),
        ],
    )

    # Should fail due to emsdk install error
    assert result.exit_code != 0
    assert isinstance(result.exception, subprocess.CalledProcessError)


def test_install_emscripten_output_format(tmp_path, monkeypatch):
    """Test that the output message format is correct"""
    envpath = Path(tmp_path) / ".xbuildenv"
    envpath.mkdir()

    monkeypatch.setattr(
        "pyodide_build.cli.xbuildenv.get_build_flag",
        lambda name: "latest",
    )

    expected_path = envpath / "emsdk"

    monkeypatch.setattr(
        "pyodide_build.xbuildenv.CrossBuildEnvManager.install_emscripten",
        lambda self, version: expected_path,
    )

    result = runner.invoke(
        xbuildenv.app,
        [
            "install-emscripten",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.output

    # Verify output format - check for key messages (logger adds extra lines)
    assert "Installing emsdk..." in result.output
    assert "Installing emsdk complete." in result.output
    assert "Use `source" in result.output
    assert "emsdk_env.sh` to set up the environment." in result.output
