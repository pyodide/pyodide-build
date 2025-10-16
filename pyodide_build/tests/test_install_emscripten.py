"""Tests for install_emscripten functionality"""

import subprocess
from unittest.mock import MagicMock, call

import pytest

from pyodide_build.xbuildenv import CrossBuildEnvManager


def test_clone_emscripten_no_active_xbuildenv(tmp_path):
    """Test that clone_emscripten raises error when no xbuildenv is active"""
    manager = CrossBuildEnvManager(tmp_path)

    with pytest.raises(
        ValueError,
        match="No active xbuildenv. Run `pyodide xbuildenv install` first.",
    ):
        manager.clone_emscripten()


def test_clone_emscripten_fresh_clone(tmp_path, monkeypatch):
    """Test cloning emsdk for the first time"""
    manager = CrossBuildEnvManager(tmp_path)

    # Setup: create active xbuildenv
    version_dir = tmp_path / "0.28.0"
    version_dir.mkdir()
    manager.use_version("0.28.0")

    emsdk_dir = version_dir / "emsdk"

    # Mock subprocess.run to avoid actual git clone
    mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(subprocess, "run", mock_run)

    # Execute
    result = manager.clone_emscripten()

    # Verify
    assert result == emsdk_dir
    mock_run.assert_called_once_with(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/emscripten-core/emsdk.git",
            str(emsdk_dir),
        ],
        check=True,
    )


def test_clone_emscripten_already_exists(tmp_path, monkeypatch):
    """Test that clone_emscripten pulls updates when emsdk already exists"""
    manager = CrossBuildEnvManager(tmp_path)

    # Setup: create active xbuildenv with existing emsdk
    version_dir = tmp_path / "0.28.0"
    version_dir.mkdir()
    emsdk_dir = version_dir / "emsdk"
    emsdk_dir.mkdir()  # Simulate existing emsdk
    manager.use_version("0.28.0")

    # Mock subprocess.run
    mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(subprocess, "run", mock_run)

    # Execute
    result = manager.clone_emscripten()

    # Verify - should pull instead of clone
    assert result == emsdk_dir
    mock_run.assert_called_once_with(["git", "-C", str(emsdk_dir), "pull"], check=True)


def test_install_emscripten_no_active_xbuildenv(tmp_path):
    """Test that install_emscripten raises error when no xbuildenv is active"""
    manager = CrossBuildEnvManager(tmp_path)

    with pytest.raises(
        ValueError,
        match="No active xbuildenv. Run `pyodide xbuildenv install` first.",
    ):
        manager.install_emscripten()


def test_install_emscripten_fresh_install(tmp_path, monkeypatch):
    """Test installing Emscripten SDK for the first time"""
    manager = CrossBuildEnvManager(tmp_path)

    # Setup: create active xbuildenv
    version_dir = tmp_path / "0.28.0"
    version_dir.mkdir()
    manager.use_version("0.28.0")

    emsdk_dir = version_dir / "emsdk"
    upstream_emscripten = emsdk_dir / "upstream" / "emscripten"

    # Mock subprocess.run to track all calls
    def mock_run_side_effect(cmd, **kwargs):
        # Create upstream/emscripten directory after clone
        if isinstance(cmd, list) and "clone" in cmd:
            upstream_emscripten.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess([], 0)

    mock_run = MagicMock(side_effect=mock_run_side_effect)
    monkeypatch.setattr(subprocess, "run", mock_run)

    # Execute with default version
    result = manager.install_emscripten()

    # Verify
    assert result == emsdk_dir
    assert mock_run.call_count == 4  # clone + install + patch + activate

    # Check the four subprocess calls
    calls = mock_run.call_args_list

    # 1. Clone emsdk
    assert calls[0] == call(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/emscripten-core/emsdk.git",
            str(emsdk_dir),
        ],
        check=True,
    )

    # 2. Install emsdk
    assert calls[1] == call(
        ["./emsdk", "install", "--build=Release", "latest"],
        cwd=emsdk_dir,
        check=True,
    )

    # 3. Apply patches (before activate)
    patch_cmd = calls[2][0][0]
    assert "cat" in patch_cmd
    assert "patches/*.patch" in patch_cmd
    assert "patch -p1 --verbose" in patch_cmd
    assert calls[2][1]["shell"] is True
    assert calls[2][1]["cwd"] == upstream_emscripten

    # 4. Activate emsdk
    assert calls[3] == call(
        ["./emsdk", "activate", "--embedded", "--build=Release", "latest"],
        cwd=emsdk_dir,
        check=True,
    )


def test_install_emscripten_specific_version(tmp_path, monkeypatch):
    """Test installing a specific Emscripten SDK version"""
    manager = CrossBuildEnvManager(tmp_path)

    # Setup: create active xbuildenv
    version_dir = tmp_path / "0.28.0"
    version_dir.mkdir()
    manager.use_version("0.28.0")

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

    # Execute with specific version
    emscripten_version = "3.1.46"
    result = manager.install_emscripten(emscripten_version)

    # Verify
    assert result == emsdk_dir
    assert mock_run.call_count == 4  # clone + install + patch + activate

    calls = mock_run.call_args_list

    # Verify version is passed correctly to install (call 1)
    assert calls[1] == call(
        ["./emsdk", "install", "--build=Release", emscripten_version],
        cwd=emsdk_dir,
        check=True,
    )
    # Verify patch command (call 2)
    patch_cmd = calls[2][0][0]
    assert "patch" in patch_cmd
    # Verify version is passed correctly to activate (call 3)
    assert calls[3] == call(
        [
            "./emsdk",
            "activate",
            "--embedded",
            "--build=Release",
            emscripten_version,
        ],
        cwd=emsdk_dir,
        check=True,
    )


def test_install_emscripten_with_existing_emsdk(tmp_path, monkeypatch):
    """Test installing Emscripten when emsdk directory already exists"""
    manager = CrossBuildEnvManager(tmp_path)

    # Setup: create active xbuildenv with existing emsdk
    version_dir = tmp_path / "0.28.0"
    version_dir.mkdir()
    emsdk_dir = version_dir / "emsdk"
    emsdk_dir.mkdir()  # Simulate existing emsdk
    patches_dir = emsdk_dir / "patches"
    patches_dir.mkdir()
    (patches_dir / "test.patch").write_text("--- a/test\n+++ b/test\n")
    upstream_emscripten = emsdk_dir / "upstream" / "emscripten"
    upstream_emscripten.mkdir(parents=True)
    manager.use_version("0.28.0")

    # Mock subprocess.run
    mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(subprocess, "run", mock_run)

    # Execute
    result = manager.install_emscripten()

    # Verify - should pull, then install, patch, and activate
    assert result == emsdk_dir
    assert mock_run.call_count == 4

    calls = mock_run.call_args_list

    # 1. Pull latest changes (not clone)
    assert calls[0] == call(["git", "-C", str(emsdk_dir), "pull"], check=True)

    # 2. Install emsdk
    assert calls[1] == call(
        ["./emsdk", "install", "--build=Release", "latest"],
        cwd=emsdk_dir,
        check=True,
    )

    # 3. Apply patches
    patch_cmd = calls[2][0][0]
    assert "patch" in patch_cmd
    assert calls[2][1]["shell"] is True
    assert calls[2][1]["cwd"] == upstream_emscripten

    # 4. Activate emsdk
    assert calls[3] == call(
        ["./emsdk", "activate", "--embedded", "--build=Release", "latest"],
        cwd=emsdk_dir,
        check=True,
    )


def test_install_emscripten_patch_application(tmp_path, monkeypatch):
    """Test that patches are applied correctly"""
    manager = CrossBuildEnvManager(tmp_path)

    # Setup: create active xbuildenv
    version_dir = tmp_path / "0.28.0"
    version_dir.mkdir()
    manager.use_version("0.28.0")

    emsdk_dir = version_dir / "emsdk"
    upstream_emscripten = emsdk_dir / "upstream" / "emscripten"

    # Mock subprocess.run to track patch command
    def mock_run_side_effect(cmd, **kwargs):
        # Create upstream/emscripten directory after clone
        if isinstance(cmd, list) and "clone" in cmd:
            upstream_emscripten.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess([], 0)

    mock_run = MagicMock(side_effect=mock_run_side_effect)
    monkeypatch.setattr(subprocess, "run", mock_run)

    # Execute
    manager.install_emscripten()

    # Get the patch command (3rd call: clone, install, patch, activate)
    patch_call = mock_run.call_args_list[2]

    # Verify it's a shell command
    assert patch_call[1]["shell"] is True
    assert patch_call[1]["check"] is True
    assert patch_call[1]["cwd"] == upstream_emscripten

    # Verify the command structure
    patch_cmd = patch_call[0][0]
    assert f"cat {emsdk_dir / 'patches'}/*.patch" in patch_cmd
    assert "patch -p1 --verbose" in patch_cmd


def test_install_emscripten_patch_fails(tmp_path, monkeypatch):
    """Test handling of patch application failure"""
    manager = CrossBuildEnvManager(tmp_path)

    # Setup: create active xbuildenv
    version_dir = tmp_path / "0.28.0"
    version_dir.mkdir()
    manager.use_version("0.28.0")

    # Mock subprocess.run to fail on patch command
    def mock_run_with_error(cmd, **kwargs):
        # Fail on patch command (shell=True command with "patch" in it)
        if kwargs.get("shell") and isinstance(cmd, str) and "patch" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr="Patch failed")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", mock_run_with_error)

    # Execute and verify error is raised
    with pytest.raises(subprocess.CalledProcessError):
        manager.install_emscripten()


def test_install_emscripten_patch_application_sequence(tmp_path, monkeypatch):
    """Test that patches are applied AFTER install but BEFORE activate"""
    manager = CrossBuildEnvManager(tmp_path)

    # Setup
    version_dir = tmp_path / "0.28.0"
    version_dir.mkdir()
    manager.use_version("0.28.0")

    emsdk_dir = version_dir / "emsdk"
    upstream_emscripten = emsdk_dir / "upstream" / "emscripten"
    patches_dir = emsdk_dir / "patches"

    # Track operation sequence
    operations = []

    def mock_run_sequence(cmd, **kwargs):
        if isinstance(cmd, list):
            if "clone" in cmd:
                operations.append("clone")
                emsdk_dir.mkdir(exist_ok=True)
                upstream_emscripten.mkdir(parents=True, exist_ok=True)
                patches_dir.mkdir(parents=True, exist_ok=True)
                (patches_dir / "test.patch").write_text("--- a/test\n+++ b/test\n")
            elif "./emsdk" in cmd and "install" in cmd:
                operations.append("install")
            elif "./emsdk" in cmd and "activate" in cmd:
                operations.append("activate")
        elif isinstance(cmd, str) and "patch" in cmd:
            operations.append("patch")

        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", mock_run_sequence)

    # Execute
    manager.install_emscripten()

    # According to the reference script, order should be:
    # 1. clone, 2. install, 3. patch, 4. activate
    assert operations == ["clone", "install", "patch", "activate"], (
        f"Expected order: clone -> install -> patch -> activate, "
        f"but got: {' -> '.join(operations)}"
    )
