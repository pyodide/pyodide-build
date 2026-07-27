import os
import shutil
import sys
from collections import namedtuple

import pytest

from pyodide_build import build_env
from pyodide_build.common import download_and_unpack_archive
from pyodide_build.xbuildenv import CrossBuildEnvManager, _url_to_version
from pyodide_build.xbuildenv_releases import (
    NIGHTLY_CROSS_BUILD_ENV_METADATA_URL,
    NIGHTLY_DEBUG_CROSS_BUILD_ENV_METADATA_URL,
    STABLE_DEBUG_CROSS_BUILD_ENV_METADATA_URL,
    parse_source_url,
)


@pytest.fixture()
def monkeypatch_subprocess_run_pip(monkeypatch):
    import subprocess

    called_with = []
    orig_run = subprocess.run

    def monkeypatch_func(cmds, *args, **kwargs):
        if cmds[0] == "pip" or cmds[0:3] == [sys.executable, "-m", "pip"]:
            called_with.extend(cmds)
            return subprocess.CompletedProcess(cmds, 0, "", "")
        else:
            return orig_run(cmds, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", monkeypatch_func)
    yield called_with


class TestCrossBuildEnvManager:
    def test_symlink_dir(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)
        assert manager.symlink_dir == tmp_path / "xbuildenv"

    def test_list_versions(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)

        versions = [
            "0.25.0",
            "0.25.0dev0",
            "0.25.1",
            "0.26.0a1",
            "0.26.0a2",
            _url_to_version("https://github.com/url/xbuildenv-0.26.0a3.tar.bz2"),
        ]

        for version in versions:
            (tmp_path / version).mkdir()

        (tmp_path / "xbuildenv").mkdir()
        (tmp_path / "not_version").touch()

        assert set(manager.list_versions()) == set(versions)

    def test_use_version(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)
        cur_version_dir = manager.symlink_dir

        cur_version_dir.mkdir(exist_ok=True)
        (cur_version_dir / "file").touch()

        (tmp_path / "0.25.0").mkdir()
        (tmp_path / "0.25.0" / "0.25.0_file").touch()

        with pytest.raises(
            ValueError, match="Cannot find cross-build environment version not_version"
        ):
            manager.use_version("not_version")

        manager.use_version("0.25.0")

        assert cur_version_dir.is_symlink()
        assert cur_version_dir.resolve() == tmp_path / "0.25.0"
        assert (cur_version_dir / "0.25.0_file").exists()
        assert not (cur_version_dir / "file").exists()

    def test_current_version(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)

        assert manager.current_version is None

        (tmp_path / "0.25.0").mkdir()
        (tmp_path / "0.26.0").mkdir()

        manager.use_version("0.25.0")
        assert manager.current_version == "0.25.0"

        manager.use_version("0.26.0")
        assert manager.current_version == "0.26.0"

        manager.uninstall_version("0.26.0")
        assert manager.current_version is None

        manager.use_version("0.25.0")
        assert manager.current_version == "0.25.0"

    def test_download(self, tmp_path, dummy_xbuildenv_url):
        download_path = tmp_path / "test"
        download_and_unpack_archive(dummy_xbuildenv_url, download_path, "")

        assert download_path.exists()
        assert (download_path / "xbuildenv").exists()
        assert (download_path / "xbuildenv" / "pyodide-root").exists()

    def test_download_path_exists(self, tmp_path):
        download_path = tmp_path / "test"
        download_path.mkdir()

        with pytest.raises(FileExistsError, match="Path .* already exists"):
            download_and_unpack_archive(
                "https://example.com/xbuildenv-0.25.0.tar.bz2", download_path, ""
            )

    def test_find_latest_version(self, tmp_path, fake_xbuildenv_releases_compatible):
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_compatible)
        )
        latest_version = manager._find_latest_version()
        assert latest_version == "0.2.0", latest_version

    def test_find_latest_version_incompat(
        self, tmp_path, fake_xbuildenv_releases_incompatible, monkeypatch
    ):
        PatchedVersionInfo = namedtuple(
            "PatchedVersionInfo", ["major", "minor", "patch"]
        )
        monkeypatch.setattr(sys, "version_info", PatchedVersionInfo(3, 11, 0))
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_incompatible)
        )

        with pytest.raises(
            ValueError,
            match="Python version 3.11 is too old. The oldest supported version of Python is 4.5.",
        ):
            manager._find_latest_version()

        monkeypatch.setattr(sys, "version_info", PatchedVersionInfo(5, 11, 0))
        with pytest.raises(
            ValueError,
            match="Python version 5.11 is not yet supported. The newest supported version of Python is 4.5.",
        ):
            manager._find_latest_version()

    def test_get_default_xbuildenv_url(
        self, tmp_path, fake_xbuildenv_releases_compatible, reset_cache, reset_env_vars
    ):
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_compatible)
        )
        url = manager._get_default_xbuildenv_url()
        assert url == ""

        reset_cache()

        os.environ["DEFAULT_CROSS_BUILD_ENV_URL"] = (
            "https://example.com/xbuildenv-0.25.0.tar.bz2"
        )

        url = manager._get_default_xbuildenv_url()
        assert url == "https://example.com/xbuildenv-0.25.0.tar.bz2"

    def test_install_version(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_compatible,
    ):
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_compatible)
        )
        version = "0.1.0"

        manager.install(version)

        assert (tmp_path / version).exists()
        assert (tmp_path / version / ".installed").exists()
        assert manager.current_version == version

        assert manager.symlink_dir.is_symlink()
        assert manager.symlink_dir.resolve() == tmp_path / version
        assert (manager.symlink_dir / "xbuildenv").exists()
        assert (manager.symlink_dir / "xbuildenv" / "pyodide-root").exists()
        assert (
            manager.symlink_dir / "xbuildenv" / "pyodide-root" / "package_index"
        ).exists()
        assert (manager.symlink_dir / "xbuildenv" / "site-packages-extras").exists()

        assert (manager.symlink_dir / ".build-python-version").exists()
        assert (
            manager.symlink_dir / ".build-python-version"
        ).read_text() == f"{sys.version_info.major}.{sys.version_info.minor}"

        # installing the same version again should be a no-op
        manager.install(version)

    def test_install_url(
        self, tmp_path, dummy_xbuildenv_url, monkeypatch, monkeypatch_subprocess_run_pip
    ):
        manager = CrossBuildEnvManager(tmp_path)

        manager.install(version=None, url=dummy_xbuildenv_url)
        version = _url_to_version(dummy_xbuildenv_url)

        assert (tmp_path / version).exists()
        assert (tmp_path / version / ".installed").exists()
        assert manager.current_version == version

        assert manager.symlink_dir.is_symlink()
        assert manager.symlink_dir.resolve() == tmp_path / version
        assert (manager.symlink_dir / "xbuildenv").exists()
        assert (manager.symlink_dir / "xbuildenv" / "pyodide-root").exists()
        assert not (
            manager.symlink_dir / "xbuildenv" / "pyodide-root" / "package_index"
        ).exists()
        assert (manager.symlink_dir / "xbuildenv" / "site-packages-extras").exists()

        assert (manager.symlink_dir / ".build-python-version").exists()
        assert (
            manager.symlink_dir / ".build-python-version"
        ).read_text() == f"{sys.version_info.major}.{sys.version_info.minor}"

    def test_install_url_default(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch,
        monkeypatch_subprocess_run_pip,
        reset_cache,
        reset_env_vars,
    ):
        manager = CrossBuildEnvManager(tmp_path)

        os.environ["DEFAULT_CROSS_BUILD_ENV_URL"] = dummy_xbuildenv_url
        manager.install(version=None)
        version = _url_to_version(dummy_xbuildenv_url)

        assert (tmp_path / version).exists()
        assert (tmp_path / version / ".installed").exists()
        assert manager.current_version == version

        assert manager.symlink_dir.is_symlink()
        assert manager.symlink_dir.resolve() == tmp_path / version
        assert (manager.symlink_dir / "xbuildenv").exists()
        assert (manager.symlink_dir / "xbuildenv" / "pyodide-root").exists()
        assert (manager.symlink_dir / "xbuildenv" / "site-packages-extras").exists()

        assert (manager.symlink_dir / ".build-python-version").exists()
        assert (
            manager.symlink_dir / ".build-python-version"
        ).read_text() == f"{sys.version_info.major}.{sys.version_info.minor}"

    def test_install_force(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_incompatible,
    ):
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_incompatible)
        )
        version = "0.1.0"

        with pytest.raises(
            ValueError,
            match=f"Version {version} is not compatible with the current environment",
        ):
            manager.install(version)

        manager.install(version, force_install=True)

        assert (tmp_path / version).exists()
        assert (tmp_path / version / ".installed").exists()
        assert manager.current_version == version

    def test_install_cross_build_packages(
        self, tmp_path, dummy_xbuildenv_url, monkeypatch_subprocess_run_pip
    ):
        pip_called_with = monkeypatch_subprocess_run_pip
        manager = CrossBuildEnvManager(tmp_path)

        download_path = tmp_path / "test"
        download_and_unpack_archive(dummy_xbuildenv_url, download_path, "")

        xbuildenv_root = download_path / "xbuildenv"
        xbuildenv_pyodide_root = xbuildenv_root / "pyodide-root"
        manager._install_cross_build_packages(xbuildenv_root, xbuildenv_pyodide_root)

        assert len(pip_called_with) == 9
        assert pip_called_with[0:8] == [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-user",
            "-r",
            str(xbuildenv_root / "requirements.txt"),
            "--target",
        ]
        assert pip_called_with[8].startswith(
            str(xbuildenv_pyodide_root)
        )  # hostsitepackages

        hostsitepackages = manager._host_site_packages_dir(xbuildenv_pyodide_root)
        assert hostsitepackages.exists()

        cross_build_files = xbuildenv_root / "site-packages-extras"
        for file in cross_build_files.iterdir():
            assert (hostsitepackages / file.name).exists()

    def test_create_package_index(self, tmp_path, dummy_xbuildenv_url):
        manager = CrossBuildEnvManager(tmp_path)

        download_path = tmp_path / "test"
        download_and_unpack_archive(dummy_xbuildenv_url, download_path, "")

        xbuildenv_root = download_path / "xbuildenv"
        xbuildenv_pyodide_root = xbuildenv_root / "pyodide-root"

        manager._create_package_index(xbuildenv_pyodide_root, version="0.25.0")
        (xbuildenv_pyodide_root / "package_index").exists()

    def test_uninstall_version(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)

        versions = [
            "0.25.0",
            "0.25.0dev0",
            "0.25.1",
            "0.26.0a1",
            "0.26.0a2",
            _url_to_version("https://github.com/url/xbuildenv-0.26.0a3.tar.bz2"),
        ]

        for version in versions:
            (tmp_path / version).mkdir()

        manager.use_version("0.25.0")

        assert manager.symlink_dir.is_symlink()
        assert manager.symlink_dir.resolve() == tmp_path / "0.25.0"

        with pytest.raises(
            ValueError, match="Cannot find cross-build environment version not_version"
        ):
            manager.uninstall_version("not_version")

        manager.uninstall_version("0.25.1")
        assert not manager._path_for_version("0.25.1").exists()

        manager.uninstall_version("0.25.0")
        assert not manager._path_for_version("0.25.0").exists()
        assert not manager.symlink_dir.exists()

        assert set(manager.list_versions()) == set(versions) - {"0.25.0", "0.25.1"}

    def test_version_marker(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_compatible,
    ):
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_compatible)
        )
        version = "0.1.0"

        manager.install(version)

        assert (manager.symlink_dir / ".build-python-version").exists()
        assert (
            manager.symlink_dir / ".build-python-version"
        ).read_text() == f"{sys.version_info.major}.{sys.version_info.minor}"

        # No error
        assert manager.version_marker_matches() == (True, None)

        (manager.symlink_dir / ".build-python-version").write_text("2.7.10")

        res, err = manager.version_marker_matches()
        assert not res
        assert "does not match the Python version" in err

    def test__init_xbuild_env(
        self, monkeypatch, monkeypatch_subprocess_run_pip, tmp_path
    ):
        manager = CrossBuildEnvManager(tmp_path)
        VersionInfo = namedtuple("VersionInfo", ("major", "minor"))
        monkeypatch.setattr(sys, "version_info", VersionInfo(3, 13))
        build_env._init_xbuild_env(xbuildenv_path=tmp_path)
        assert manager.current_version >= "0.28.2"
        monkeypatch.setattr(sys, "version_info", VersionInfo(3, 12))
        build_env._init_xbuild_env(xbuildenv_path=tmp_path)
        assert manager.current_version >= "0.27.7"

    def test_ensure_cross_build_packages_installed_idempotent(
        self, tmp_path, dummy_xbuildenv_url, monkeypatch_subprocess_run_pip
    ):
        pip_called_with = monkeypatch_subprocess_run_pip
        manager = CrossBuildEnvManager(tmp_path)

        # Lazy install path: no cross-build packages installed yet
        manager.install(
            version=None,
            url=dummy_xbuildenv_url,
            skip_install_cross_build_packages=True,
        )
        assert pip_called_with == []

        # First ensure installs once
        manager.ensure_cross_build_packages_installed()
        assert len(pip_called_with) == 9

        # Second ensure is a no-op
        manager.ensure_cross_build_packages_installed()
        assert len(pip_called_with) == 9

        marker = manager.symlink_dir.resolve() / ".cross-build-packages-installed"
        assert marker.exists()

    def test_use_version_dangling_symlink(self, tmp_path):
        # Regression test: a dangling xbuildenv symlink (target removed) must be
        # cleaned up so that use_version() does not raise FileExistsError.
        manager = CrossBuildEnvManager(tmp_path)

        (tmp_path / "0.25.0").mkdir()
        (tmp_path / "0.26.0").mkdir()

        # Point the symlink at a directory and then delete that directory,
        # leaving a dangling symlink behind.
        manager.use_version("0.25.0")
        shutil.rmtree(tmp_path / "0.25.0")

        assert manager.symlink_dir.is_symlink()
        assert not manager.symlink_dir.exists()  # dangling

        # This previously raised FileExistsError.
        manager.use_version("0.26.0")

        assert manager.symlink_dir.is_symlink()
        assert manager.symlink_dir.resolve() == tmp_path / "0.26.0"

    def test_install_preexisting_not_deleted_on_failure(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch,
        monkeypatch_subprocess_run_pip,
    ):
        # Regression test: if a valid xbuildenv is already installed and a later
        # step (e.g. use_version) of a subsequent install() fails, the existing
        # installation must NOT be deleted.
        manager = CrossBuildEnvManager(tmp_path)

        manager.install(version=None, url=dummy_xbuildenv_url)
        version = _url_to_version(dummy_xbuildenv_url)
        download_path = tmp_path / version
        assert download_path.exists()

        # Make a later step fail on the second install() call.
        def boom(_version):
            raise OSError("simulated symlink failure (e.g. Windows privilege)")

        monkeypatch.setattr(manager, "use_version", boom)

        with pytest.raises(OSError, match="simulated symlink failure"):
            manager.install(version=None, url=dummy_xbuildenv_url)

        # The pre-existing installation must still be present.
        assert download_path.exists()
        assert (download_path / ".installed").exists()

    def test_install_new_deleted_on_failure(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch,
        monkeypatch_subprocess_run_pip,
    ):
        # Complement: when THIS call created the directory and a later step
        # fails, the freshly downloaded directory should be removed.
        manager = CrossBuildEnvManager(tmp_path)
        version = _url_to_version(dummy_xbuildenv_url)
        download_path = tmp_path / version

        def boom(_version):
            raise OSError("simulated symlink failure")

        monkeypatch.setattr(manager, "use_version", boom)

        with pytest.raises(OSError, match="simulated symlink failure"):
            manager.install(version=None, url=dummy_xbuildenv_url)

        assert not download_path.exists()

    def test_install_url_default_no_mangled_package_index(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch,
        monkeypatch_subprocess_run_pip,
        reset_cache,
        reset_env_vars,
    ):
        # Regression test: installing via DEFAULT_CROSS_BUILD_ENV_URL must be
        # treated like an explicit-url install and NOT create a package index
        # baked with a mangled (URL-derived) version string.
        manager = CrossBuildEnvManager(tmp_path)

        os.environ["DEFAULT_CROSS_BUILD_ENV_URL"] = dummy_xbuildenv_url
        manager.install(version=None)

        assert not (
            manager.symlink_dir / "xbuildenv" / "pyodide-root" / "package_index"
        ).exists()

    def test_install_version_marker_mismatch_triggers_reinstall(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch,
        monkeypatch_subprocess_run_pip,
    ):
        # Regression test: when an already-installed xbuildenv has a Python
        # version marker that does not match the current Python, a subsequent
        # install() must rewrite the marker (and refresh host packages) rather
        # than skipping work and leaving the stale marker / silently passing.
        manager = CrossBuildEnvManager(tmp_path)

        manager.install(
            version=None,
            url=dummy_xbuildenv_url,
            skip_install_cross_build_packages=True,
        )
        version = _url_to_version(dummy_xbuildenv_url)
        download_path = tmp_path / version

        # Simulate the env having been installed under a different Python and
        # mark cross-build packages as already installed.
        marker_file = download_path / ".build-python-version"
        marker_file.write_text("2.7.10")
        cross_build_marker = download_path / ".cross-build-packages-installed"
        cross_build_marker.touch()

        matches, _ = manager.version_marker_matches()
        assert not matches

        # Reinstall should rewrite the marker to the current Python version.
        manager.install(
            version=None,
            url=dummy_xbuildenv_url,
            skip_install_cross_build_packages=True,
        )

        matches, err = manager.version_marker_matches()
        assert matches, err
        assert (
            marker_file.read_text()
            == f"{sys.version_info.major}.{sys.version_info.minor}"
        )
        # Host-package marker dropped so packages get reinstalled lazily.
        assert not cross_build_marker.exists()

    def test_install_version_marker_match_no_marker_rewrite(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch,
        monkeypatch_subprocess_run_pip,
    ):
        # When the marker already matches, a repeat install() should be a no-op
        # and must not re-run installation work or drop the cross-build marker.
        manager = CrossBuildEnvManager(tmp_path)

        manager.install(
            version=None,
            url=dummy_xbuildenv_url,
            skip_install_cross_build_packages=True,
        )
        version = _url_to_version(dummy_xbuildenv_url)
        download_path = tmp_path / version
        cross_build_marker = download_path / ".cross-build-packages-installed"
        cross_build_marker.touch()

        manager.install(
            version=None,
            url=dummy_xbuildenv_url,
            skip_install_cross_build_packages=True,
        )

        # Marker preserved (install did no work).
        assert cross_build_marker.exists()

    def test_install_records_source(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_compatible,
    ):
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_compatible), source="nightly-debug"
        )
        version = "0.1.0"

        manager.install(version)

        assert (tmp_path / version / ".xbuildenv-source").read_text() == "nightly-debug"
        assert manager.installed_source(tmp_path / version) == "nightly-debug"
        assert manager.current_source == "nightly-debug"

    def test_install_source_defaults_to_stable(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_compatible,
    ):
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_compatible)
        )
        version = "0.1.0"

        manager.install(version)

        assert manager.current_source == "stable"
        # An environment installed before the marker existed has no source.
        (tmp_path / version / ".xbuildenv-source").unlink()
        assert manager.installed_source(tmp_path / version) is None
        assert manager.current_source is None

    def test_install_unlabelled_reused_by_stable(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_compatible,
    ):
        # An environment from before the marker is kept by a plain install
        # rather than re-downloading a working one for everybody.
        version = "0.1.0"
        metadata = str(fake_xbuildenv_releases_compatible)

        manager = CrossBuildEnvManager(tmp_path, metadata)
        manager.install(version)
        (tmp_path / version / ".xbuildenv-source").unlink()

        canary = tmp_path / version / "canary.txt"
        canary.touch()

        CrossBuildEnvManager(tmp_path, metadata).install(version)

        assert canary.exists()
        # Now labelled, so later installs do not have to guess.
        assert manager.installed_source(tmp_path / version) == "stable"

    def test_install_unlabelled_replaced_by_debug(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_compatible,
    ):
        # An unlabelled environment cannot be shown to be the debug variant, so
        # a debug install has to replace it rather than trust it.
        version = "0.1.0"
        metadata = str(fake_xbuildenv_releases_compatible)

        manager = CrossBuildEnvManager(tmp_path, metadata)
        manager.install(version)
        (tmp_path / version / ".xbuildenv-source").unlink()

        canary = tmp_path / version / "canary.txt"
        canary.touch()

        debug = CrossBuildEnvManager(tmp_path, metadata, source="stable-debug")
        debug.install(version)

        assert not canary.exists()
        # Relabelled, so it no longer reports the source it was replaced from
        assert debug.installed_source(tmp_path / version) == "stable-debug"
        assert debug.current_source == "stable-debug"

    def test_failed_reinstall_keeps_the_replaced_environment(
        self,
        tmp_path,
        monkeypatch,
        dummy_xbuildenv_url,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_compatible,
    ):
        # Replacing an environment must not leave the user with nothing when
        # the download for its replacement fails.
        version = "0.1.0"
        metadata = str(fake_xbuildenv_releases_compatible)

        stable = CrossBuildEnvManager(tmp_path, metadata)
        stable.install(version)

        canary = tmp_path / version / "canary.txt"
        canary.touch()

        def fail_download(*args, **kwargs):
            raise RuntimeError("network is down")

        monkeypatch.setattr(
            "pyodide_build.xbuildenv.download_and_unpack_archive", fail_download
        )

        debug = CrossBuildEnvManager(tmp_path, metadata, source="stable-debug")
        with pytest.raises(RuntimeError, match="network is down"):
            debug.install(version)

        # The original is back, rather than a half-installed or missing one
        assert canary.exists()
        assert stable.installed_source(tmp_path / version) == "stable"
        assert not (tmp_path / f"{version}.replaced").exists()

    def test_install_url_records_the_url_as_the_source(
        self, tmp_path, dummy_xbuildenv_url, monkeypatch_subprocess_run_pip
    ):
        # There is no release behind a URL install to name, and calling it
        # 'stable' would claim a provenance we cannot check, so record the URL.
        manager = CrossBuildEnvManager(tmp_path)

        manager.install(version=None, url=dummy_xbuildenv_url)
        version = _url_to_version(dummy_xbuildenv_url)

        assert (
            tmp_path / version / ".xbuildenv-source"
        ).read_text() == dummy_xbuildenv_url
        assert manager.installed_source(tmp_path / version) == dummy_xbuildenv_url
        assert manager.current_source == dummy_xbuildenv_url

    def test_install_url_twice_keeps_the_environment(
        self, tmp_path, dummy_xbuildenv_url, monkeypatch_subprocess_run_pip
    ):
        # The directory name comes from the URL, so a cached one came from this
        # same URL and must not be treated as a source mismatch.
        manager = CrossBuildEnvManager(tmp_path)
        manager.install(version=None, url=dummy_xbuildenv_url)
        version = _url_to_version(dummy_xbuildenv_url)

        canary = tmp_path / version / "canary.txt"
        canary.touch()

        CrossBuildEnvManager(tmp_path).install(version=None, url=dummy_xbuildenv_url)

        assert canary.exists()

    def test_install_source_mismatch_triggers_reinstall(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_compatible,
    ):
        # Regression test: a stable release and its debug variant share a version
        # string, so a cached stable environment must not satisfy a request for
        # the debug one.
        version = "0.1.0"
        metadata = str(fake_xbuildenv_releases_compatible)

        stable = CrossBuildEnvManager(tmp_path, metadata)
        stable.install(version)

        canary = tmp_path / version / "canary.txt"
        canary.touch()

        debug = CrossBuildEnvManager(tmp_path, metadata, source="stable-debug")
        debug.install(version)

        # The environment was downloaded again rather than reused in place.
        assert not canary.exists()
        assert debug.installed_source(tmp_path / version) == "stable-debug"
        assert debug.current_source == "stable-debug"

    def test_install_source_match_reuses_existing(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_compatible,
    ):
        version = "0.1.0"
        metadata = str(fake_xbuildenv_releases_compatible)

        manager = CrossBuildEnvManager(tmp_path, metadata, source="nightly")
        manager.install(version)

        canary = tmp_path / version / "canary.txt"
        canary.touch()

        CrossBuildEnvManager(tmp_path, metadata, source="nightly").install(version)

        assert canary.exists()

    def test_source_derived_from_metadata_url(self, tmp_path):
        manager = CrossBuildEnvManager(
            tmp_path, NIGHTLY_DEBUG_CROSS_BUILD_ENV_METADATA_URL
        )

        assert manager.source == "nightly-debug"

    def test_source_derived_from_metadata_url_env_var(
        self, tmp_path, monkeypatch, reset_cache
    ):
        monkeypatch.setenv(
            "PYODIDE_CROSS_BUILD_ENV_METADATA_URL", NIGHTLY_CROSS_BUILD_ENV_METADATA_URL
        )

        manager = CrossBuildEnvManager(tmp_path)

        assert manager.source == "nightly"
        assert manager.metadata_url == NIGHTLY_CROSS_BUILD_ENV_METADATA_URL

    def test_source_wins_over_metadata_url_env_var(
        self, tmp_path, monkeypatch, reset_cache
    ):
        # Asking for a source explicitly is already a choice of metadata file,
        # so the environment variable must not redirect it.
        monkeypatch.setenv(
            "PYODIDE_CROSS_BUILD_ENV_METADATA_URL", NIGHTLY_CROSS_BUILD_ENV_METADATA_URL
        )

        manager = CrossBuildEnvManager(tmp_path, source="stable-debug")

        assert manager.source == "stable-debug"
        assert manager.metadata_url == STABLE_DEBUG_CROSS_BUILD_ENV_METADATA_URL

    def test_installed_source_missing_env(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)

        assert manager.installed_source(tmp_path / "0.1.0") is None
        assert manager.current_source is None

    def test_find_latest_version_empty_releases(self, tmp_path):
        # Regression test: empty releases metadata must produce a clear error,
        # not an IndexError.
        import json

        metadata_path = tmp_path / "empty-metadata.json"
        metadata_path.write_text(json.dumps({"releases": {}}))

        manager = CrossBuildEnvManager(tmp_path, str(metadata_path))

        with pytest.raises(
            ValueError, match="No cross-build environment releases are available"
        ):
            manager._find_latest_version()


@pytest.mark.parametrize(
    "url, version",
    [
        (
            "https://example.com/xbuildenv-0.25.0.tar.bz2",
            "https_example_com_xbuildenv-0_25_0_tar_bz2",
        ),
        (
            "http://example.com/subdir/subsubdir/xbuildenv-0.25.0dev0.tar.gz2",
            "http_example_com_subdir_subsubdir_xbuildenv-0_25_0dev0_tar_gz2",
        ),
    ],
)
def test_url_to_version(url: str, version: str) -> None:
    assert _url_to_version(url) == version


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/xbuildenv-0.25.0.tar.bz2",
        "http://example.com/a/b.tar.gz",
        "file:///home/me/xbuildenv.tar.bz2",
        # urlopen is not limited to http and file, so neither is this
        "ftp://example.com/xbuildenv.tar.bz2",
    ],
)
def test_parse_source_url_accepts_urls(value: str) -> None:
    assert parse_source_url(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "stable",
        "nightly-debug",
        "",
        "not a url",
        # Contains "://" but has no scheme to go with it
        "://example.com",
        # A scheme addressing nothing
        "https://",
    ],
)
def test_parse_source_url_rejects_other_strings(value: str) -> None:
    assert parse_source_url(value) is None
