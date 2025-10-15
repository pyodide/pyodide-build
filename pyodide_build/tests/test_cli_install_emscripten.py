"""Tests for install-emscripten CLI command"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

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

    assert result.exit_code != 0, result.stdout
    assert "Cross-build environment not found" in result.stdout, result.stdout


def test_install_emscripten_default_version(tmp_path, monkeypatch):
    """Test installing Emscripten with default version"""
    envpath = Path(tmp_path) / ".xbuildenv"

    # Setup: create a fake xbuildenv structure
    version_dir = envpath / "0.28.0"
    version_dir.mkdir(parents=True)
    (envpath / "xbuildenv").symlink_to(version_dir)

    emsdk_dir = version_dir / "emsdk"
    upstream_emscripten = emsdk_dir / "upstream" / "emscripten"

    # Mock subprocess.run to avoid actual git operations
    def mock_run_side_effect(cmd, **kwargs):
        # Create upstream/emscripten directory after clone
        if isinstance(cmd, list) and "clone" in cmd:
            upstream_emscripten.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess([], 0)

    mock_run = MagicMock(side_effect=mock_run_side_effect)
    monkeypatch.setattr(subprocess, "run", mock_run)

    result = runner.invoke(
        xbuildenv.app,
        [
            "install-emscripten",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Cloning Emscripten" in result.stdout, result.stdout
    assert "Installing emsdk..." in result.stdout, result.stdout
    assert "Installing emsdk complete." in result.stdout, result.stdout
    assert "Use `source" in result.stdout, result.stdout
    assert "emsdk_env.sh` to set up the environment." in result.stdout, result.stdout

    # Verify subprocess calls
    # install_emscripten makes 4 calls: clone + install + patch + activate
    assert mock_run.call_count == 4
    calls = mock_run.call_args_list

    # First call: git clone
    git_clone_cmd = calls[0][0][0]
    assert "git" in git_clone_cmd
    assert "clone" in git_clone_cmd

    # Second call: emsdk install
    emsdk_install_cmd = calls[1][0][0]
    assert "./emsdk" in emsdk_install_cmd
    assert "install" in emsdk_install_cmd
    assert "latest" in emsdk_install_cmd

    # Third call: patch
    patch_cmd = calls[2][0][0]
    assert isinstance(patch_cmd, str)
    assert "patch" in patch_cmd

    # Fourth call: emsdk activate
    emsdk_activate_cmd = calls[3][0][0]
    assert "./emsdk" in emsdk_activate_cmd
    assert "activate" in emsdk_activate_cmd
    assert "latest" in emsdk_activate_cmd


def test_install_emscripten_specific_version(tmp_path, monkeypatch):
    """Test installing Emscripten with a specific version"""
    envpath = Path(tmp_path) / ".xbuildenv"

    # Setup: create a fake xbuildenv structure
    version_dir = envpath / "0.28.0"
    version_dir.mkdir(parents=True)
    (envpath / "xbuildenv").symlink_to(version_dir)

    emsdk_dir = version_dir / "emsdk"
    upstream_emscripten = emsdk_dir / "upstream" / "emscripten"

    # Mock subprocess.run
    def mock_run_side_effect(cmd, **kwargs):
        # Create upstream/emscripten directory after clone
        if isinstance(cmd, list) and "clone" in cmd:
            upstream_emscripten.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess([], 0)

    mock_run = MagicMock(side_effect=mock_run_side_effect)
    monkeypatch.setattr(subprocess, "run", mock_run)

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

    assert result.exit_code == 0, result.stdout
    assert "Cloning Emscripten" in result.stdout, result.stdout
    assert "Installing emsdk..." in result.stdout, result.stdout

    # Verify the specific version was used
    assert mock_run.call_count == 4
    calls = mock_run.call_args_list

    # Check emsdk install was called with specific version (second call)
    emsdk_install_cmd = calls[1][0][0]
    assert emscripten_version in emsdk_install_cmd

    # Check emsdk activate was called with specific version (fourth call)
    emsdk_activate_cmd = calls[3][0][0]
    assert emscripten_version in emsdk_activate_cmd


def test_install_emscripten_with_existing_emsdk(tmp_path, monkeypatch):
    """Test installing Emscripten when emsdk already exists (should pull updates)"""
    envpath = Path(tmp_path) / ".xbuildenv"

    # Setup: create a fake xbuildenv with existing emsdk
    version_dir = envpath / "0.28.0"
    version_dir.mkdir(parents=True)
    emsdk_dir = version_dir / "emsdk"
    emsdk_dir.mkdir()  # Existing emsdk directory
    patches_dir = emsdk_dir / "patches"
    patches_dir.mkdir()
    (patches_dir / "test.patch").write_text("--- a/test\n+++ b/test\n")
    upstream_emscripten = emsdk_dir / "upstream" / "emscripten"
    upstream_emscripten.mkdir(parents=True)
    (envpath / "xbuildenv").symlink_to(version_dir)

    # Mock subprocess.run
    mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(subprocess, "run", mock_run)

    result = runner.invoke(
        xbuildenv.app,
        [
            "install-emscripten",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout

    # Verify subprocess calls - should use git pull instead of clone
    # With existing emsdk: pull + install + patch + activate
    assert mock_run.call_count == 4
    calls = mock_run.call_args_list

    # First call should be git pull (not clone)
    git_cmd = calls[0][0][0]
    assert "git" in git_cmd
    assert "pull" in git_cmd


def test_install_emscripten_git_failure(tmp_path, monkeypatch):
    """Test handling of git clone failure"""
    envpath = Path(tmp_path) / ".xbuildenv"

    # Setup: create a fake xbuildenv structure
    (envpath / "0.28.0").mkdir(parents=True)
    (envpath / "xbuildenv").symlink_to(envpath / "0.28.0")

    # Mock subprocess.run to fail on git clone
    def mock_run_with_error(cmd, **kwargs):
        if "git" in cmd and "clone" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr="Clone failed")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", mock_run_with_error)

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

    # Setup: create a fake xbuildenv structure
    (envpath / "0.28.0").mkdir(parents=True)
    (envpath / "xbuildenv").symlink_to(envpath / "0.28.0")

    # Mock subprocess.run to fail on emsdk install
    def mock_run_with_error(cmd, **kwargs):
        if "./emsdk" in cmd and "install" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr="Installation failed")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", mock_run_with_error)

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

    # Setup: create a fake xbuildenv structure
    version_dir = envpath / "0.28.0"
    version_dir.mkdir(parents=True)
    (envpath / "xbuildenv").symlink_to(version_dir)

    # Mock subprocess.run
    mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(subprocess, "run", mock_run)

    result = runner.invoke(
        xbuildenv.app,
        [
            "install-emscripten",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout

    # Verify output format - check for key messages (logger adds extra lines)
    assert "Cloning Emscripten" in result.stdout
    assert "Installing emsdk..." in result.stdout
    assert "Installing emsdk complete." in result.stdout
    assert "Use `source" in result.stdout
    assert "emsdk_env.sh` to set up the environment." in result.stdout
