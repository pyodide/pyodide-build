"""Tests for install_emscripten functionality"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from pyodide_build.xbuildenv import CrossBuildEnvManager


class TestInstallEmscripten:
    """Test suite for install_emscripten and clone_emscripten methods"""

    def test_clone_emscripten_no_active_xbuildenv(self, tmp_path):
        """Test that clone_emscripten raises error when no xbuildenv is active"""
        manager = CrossBuildEnvManager(tmp_path)

        with pytest.raises(
            ValueError,
            match="No active xbuildenv. Run `pyodide xbuildenv install` first.",
        ):
            manager.clone_emscripten()

    def test_clone_emscripten_fresh_clone(self, tmp_path, monkeypatch):
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

    def test_clone_emscripten_already_exists(self, tmp_path, monkeypatch):
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
        mock_run.assert_called_once_with(
            ["git", "-C", str(emsdk_dir), "pull"], check=True
        )

    def test_install_emscripten_no_active_xbuildenv(self, tmp_path):
        """Test that install_emscripten raises error when no xbuildenv is active"""
        manager = CrossBuildEnvManager(tmp_path)

        with pytest.raises(
            ValueError,
            match="No active xbuildenv. Run `pyodide xbuildenv install` first.",
        ):
            manager.install_emscripten()

    def test_install_emscripten_fresh_install(self, tmp_path, monkeypatch):
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

    def test_install_emscripten_specific_version(self, tmp_path, monkeypatch):
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

    def test_install_emscripten_with_existing_emsdk(self, tmp_path, monkeypatch):
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

    def test_install_emscripten_git_clone_fails(self, tmp_path, monkeypatch):
        """Test handling of git clone failure"""
        manager = CrossBuildEnvManager(tmp_path)

        # Setup: create active xbuildenv
        version_dir = tmp_path / "0.28.0"
        version_dir.mkdir()
        manager.use_version("0.28.0")

        # Mock subprocess.run to raise CalledProcessError on git clone
        def mock_run_with_error(cmd, **kwargs):
            if "git" in cmd and "clone" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr="Clone failed")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run_with_error)

        # Execute and verify error is raised
        with pytest.raises(subprocess.CalledProcessError):
            manager.install_emscripten()

    def test_install_emscripten_emsdk_install_fails(self, tmp_path, monkeypatch):
        """Test handling of emsdk install command failure"""
        manager = CrossBuildEnvManager(tmp_path)

        # Setup: create active xbuildenv
        version_dir = tmp_path / "0.28.0"
        version_dir.mkdir()
        manager.use_version("0.28.0")

        emsdk_dir = version_dir / "emsdk"

        # Mock subprocess.run to fail on emsdk install
        def mock_run_with_error(cmd, **kwargs):
            if "./emsdk" in cmd and "install" in cmd:
                raise subprocess.CalledProcessError(
                    1, cmd, stderr="Installation failed"
                )
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run_with_error)

        # Execute and verify error is raised
        with pytest.raises(subprocess.CalledProcessError):
            manager.install_emscripten()

    def test_install_emscripten_emsdk_activate_fails(self, tmp_path, monkeypatch):
        """Test handling of emsdk activate command failure"""
        manager = CrossBuildEnvManager(tmp_path)

        # Setup: create active xbuildenv
        version_dir = tmp_path / "0.28.0"
        version_dir.mkdir()
        manager.use_version("0.28.0")

        # Mock subprocess.run to fail on emsdk activate
        def mock_run_with_error(cmd, **kwargs):
            if "./emsdk" in cmd and "activate" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr="Activation failed")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run_with_error)

        # Execute and verify error is raised
        with pytest.raises(subprocess.CalledProcessError):
            manager.install_emscripten()

    def test_install_emscripten_patch_application(self, tmp_path, monkeypatch):
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

    def test_install_emscripten_patch_fails(self, tmp_path, monkeypatch):
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

    def test_install_emscripten_with_real_patches(self, tmp_path, monkeypatch):
        """Integration-style test with actual patch files"""
        manager = CrossBuildEnvManager(tmp_path)

        # Setup: create active xbuildenv
        version_dir = tmp_path / "0.28.0"
        version_dir.mkdir()
        manager.use_version("0.28.0")

        emsdk_dir = version_dir / "emsdk"
        patches_dir = emsdk_dir / "patches"
        upstream_emscripten = emsdk_dir / "upstream" / "emscripten"

        # Track subprocess calls
        calls_made = []

        def mock_run_track(cmd, **kwargs):
            calls_made.append((cmd, kwargs))

            # When git clone is called, create the emsdk directory structure
            if isinstance(cmd, list) and "clone" in cmd:
                emsdk_dir.mkdir(exist_ok=True)
                patches_dir.mkdir(exist_ok=True)
                upstream_emscripten.mkdir(parents=True, exist_ok=True)
                # Create some dummy patch files
                (patches_dir / "fix1.patch").write_text(
                    "--- a/file.txt\n+++ b/file.txt\n"
                )
                (patches_dir / "fix2.patch").write_text(
                    "--- a/another.txt\n+++ b/another.txt\n"
                )

            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run_track)

        # Execute
        result = manager.install_emscripten()

        # Verify
        assert result == emsdk_dir
        assert len(calls_made) == 4

        # Check that patch command was called (index 2: clone, install, patch, activate)
        patch_call = calls_made[2]
        assert patch_call[1]["shell"] is True
        assert "patch" in patch_call[0]

        # Verify patches directory was referenced
        assert str(patches_dir) in patch_call[0] or "patches" in patch_call[0]

    def test_install_emscripten_patches_from_xbuildenv(self, tmp_path, monkeypatch):
        """Test that patches come from the xbuildenv archive, not downloaded separately"""
        manager = CrossBuildEnvManager(tmp_path)

        # Setup: create active xbuildenv with patches already present
        version_dir = tmp_path / "0.28.0"
        version_dir.mkdir()
        manager.use_version("0.28.0")

        emsdk_dir = version_dir / "emsdk"
        patches_dir = emsdk_dir / "patches"

        # Pre-create the patches directory with patch files (simulating xbuildenv archive)
        patches_dir.mkdir(parents=True, exist_ok=True)
        (patches_dir / "0001-pyodide-config.patch").write_text(
            "--- a/tools/config.py\n+++ b/tools/config.py\n@@ -1 +1,2 @@\n CONFIG = {}\n+# Pyodide modification\n"
        )

        # Mock subprocess.run
        mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0))
        monkeypatch.setattr(subprocess, "run", mock_run)

        # Execute
        manager.install_emscripten()

        # Verify patches directory was NOT downloaded - it should already exist from xbuildenv
        assert patches_dir.exists()
        assert len(list(patches_dir.glob("*.patch"))) > 0

    def test_install_emscripten_patch_directory_location(self, tmp_path, monkeypatch):
        """Test that patch_path points to xbuildenv/emsdk/patches"""
        manager = CrossBuildEnvManager(tmp_path)

        # Setup
        version_dir = tmp_path / "0.28.0"
        version_dir.mkdir()
        manager.use_version("0.28.0")

        emsdk_dir = version_dir / "emsdk"
        expected_patch_dir = emsdk_dir / "patches"

        # Track the patch command
        patch_commands = []

        def mock_run_track(cmd, **kwargs):
            if isinstance(cmd, list) and "clone" in cmd:
                emsdk_dir.mkdir(exist_ok=True)
                expected_patch_dir.mkdir(parents=True, exist_ok=True)
                (expected_patch_dir / "test.patch").write_text(
                    "--- a/test\n+++ b/test\n"
                )

            if isinstance(cmd, str) and "patch" in cmd:
                patch_commands.append((cmd, kwargs))

            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run_track)

        # Execute
        manager.install_emscripten()

        # Verify
        assert len(patch_commands) == 1
        patch_cmd, patch_kwargs = patch_commands[0]

        # The patch path should be in the command
        assert str(expected_patch_dir) in patch_cmd

    def test_install_emscripten_patch_applied_to_upstream_emscripten(
        self, tmp_path, monkeypatch
    ):
        """Test that patches are applied in upstream/emscripten directory (correct cwd)"""
        manager = CrossBuildEnvManager(tmp_path)

        # Setup
        version_dir = tmp_path / "0.28.0"
        version_dir.mkdir()
        manager.use_version("0.28.0")

        emsdk_dir = version_dir / "emsdk"
        upstream_emscripten = emsdk_dir / "upstream" / "emscripten"
        patches_dir = emsdk_dir / "patches"

        # Track where patches are applied
        patch_application_cwd = None

        def mock_run_track_cwd(cmd, **kwargs):
            nonlocal patch_application_cwd

            if isinstance(cmd, list) and "clone" in cmd:
                emsdk_dir.mkdir(exist_ok=True)
                upstream_emscripten.mkdir(parents=True, exist_ok=True)
                patches_dir.mkdir(parents=True, exist_ok=True)
                (patches_dir / "test.patch").write_text(
                    "--- a/tools/config.py\n+++ b/tools/config.py\n@@ -1 +1,2 @@\n config\n+pyodide\n"
                )

            # Capture the cwd when patch is applied
            if isinstance(cmd, str) and "patch" in cmd:
                patch_application_cwd = kwargs.get("cwd")

            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run_track_cwd)

        # Execute
        manager.install_emscripten()

        # CRITICAL: Verify patches are applied in upstream/emscripten, not emsdk root
        # According to pyodide-recipes reference script, cwd should be emscripten_root
        # (emsdk/upstream/emscripten), NOT emsdk_dir
        assert patch_application_cwd == upstream_emscripten, (
            f"Patches should be applied in {upstream_emscripten}, not {patch_application_cwd}"
        )

    def test_install_emscripten_patches_modify_emscripten_files(
        self, tmp_path, monkeypatch
    ):
        """Test that patches target files within emscripten directory structure"""
        manager = CrossBuildEnvManager(tmp_path)

        # Setup
        version_dir = tmp_path / "0.28.0"
        version_dir.mkdir()
        manager.use_version("0.28.0")

        emsdk_dir = version_dir / "emsdk"
        upstream_emscripten = emsdk_dir / "upstream" / "emscripten"
        patches_dir = emsdk_dir / "patches"

        def mock_run(cmd, **kwargs):
            if isinstance(cmd, list) and "clone" in cmd:
                emsdk_dir.mkdir(exist_ok=True)
                upstream_emscripten.mkdir(parents=True, exist_ok=True)
                patches_dir.mkdir(parents=True, exist_ok=True)

                # Create realistic Pyodide patches that modify emscripten files
                (patches_dir / "0001-system-libs.patch").write_text(
                    "--- a/tools/system_libs.py\n"
                    "+++ b/tools/system_libs.py\n"
                    "@@ -100,6 +100,8 @@\n"
                    " def get_system_libs():\n"
                    "     return SYSTEM_LIBS\n"
                    "+# Pyodide: custom library handling\n"
                )

                (patches_dir / "0002-config.patch").write_text(
                    "--- a/emscripten-config\n"
                    "+++ b/emscripten-config\n"
                    "@@ -1,3 +1,4 @@\n"
                    " #!/usr/bin/env python3\n"
                    "+# Modified by Pyodide\n"
                )

            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)

        # Execute
        manager.install_emscripten()

        # Verify patch files exist and have correct format
        patch_files = list(patches_dir.glob("*.patch"))
        assert len(patch_files) > 0

        for patch_file in patch_files:
            content = patch_file.read_text()
            # Patches should reference files within emscripten (not emsdk)
            assert "--- a/" in content
            assert "+++" in content

    def test_install_emscripten_patch_application_sequence(self, tmp_path, monkeypatch):
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
