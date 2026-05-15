import os
import sys
from collections import namedtuple

import pytest

from pyodide_build import build_env
from pyodide_build.common import download_and_unpack_archive
from pyodide_build.xbuildenv import CrossBuildEnvManager, _url_to_version


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
