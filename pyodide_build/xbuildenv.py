import json
import shutil
import subprocess
import sys
from pathlib import Path

from pyodide_lock import PyodideLockSpec

from pyodide_build import build_env, uv_helper
from pyodide_build.common import download_and_unpack_archive
from pyodide_build.create_package_index import create_package_index
from pyodide_build.logger import logger
from pyodide_build.xbuildenv_releases import (
    CrossBuildEnvReleaseSpec,
    cross_build_env_metadata_url,
    load_cross_build_env_metadata,
)

CDN_BASE = "https://cdn.jsdelivr.net/pyodide/v{version}/full/"
PYTHON_VERSION_MARKER_FILE = ".build-python-version"


class CrossBuildEnvManager:
    """
    Manager for the cross-build environment.
    """

    def __init__(self, env_dir: str | Path, metadata_url: str | None = None) -> None:
        """
        Parameters
        ----------
        env_dir
            The directory to store the cross-build environments.
        metadata_url
            URL to the metadata file that contains the information about the available
            cross-build environments. If not specified, the default metadata file is used.
        """
        self.env_dir = Path(env_dir).resolve()
        self.metadata_url = metadata_url or cross_build_env_metadata_url()

        try:
            self.env_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValueError(
                f"Failed to create cross-build environment at {self.env_dir}"
            ) from e

    @property
    def symlink_dir(self):
        """
        Returns the path to the symlink that points to the currently used xbuildenv version.
        """
        return self.env_dir / "xbuildenv"

    @property
    def pyodide_root(self) -> Path:
        """
        Returns the path to the pyodide-root directory inside the xbuildenv directory.
        """
        return self.symlink_dir.resolve() / "xbuildenv" / "pyodide-root"

    @property
    def current_version(self) -> str | None:
        """
        Returns the currently used xbuildenv version.
        """
        if not self.symlink_dir.exists():
            return None

        return self.symlink_dir.resolve().name

    def _find_remote_release(self, version: str) -> CrossBuildEnvReleaseSpec:
        """
        Find the cross-build environment release with the given version from remote metadata.
        """
        metadata = load_cross_build_env_metadata(self.metadata_url)
        return metadata.get_release(version)

    def _path_for_version(self, version: str) -> Path:
        """Returns the path to the xbuildenv for the given version."""
        return self.env_dir / version

    def list_versions(self) -> list[str]:
        """
        List the downloaded xbuildenv versions.

        TODO: add a parameter to list only compatible versions
        """
        versions = []
        for version_dir in self.env_dir.glob("*"):
            if not version_dir.is_dir() or version_dir == self.symlink_dir:
                continue

            versions.append(version_dir.name)

        return sorted(versions)

    def use_version(self, version: str) -> None:
        """
        Select the xbuildenv version to use.

        This creates a symlink to the selected version in the xbuildenv directory.

        Parameters
        ----------
        version
            The version of xbuildenv to use.
        """
        logger.info("Using Pyodide cross-build environment version: %s", version)

        version_path = self._path_for_version(version)
        if not version_path.exists():
            raise ValueError(
                f"Cannot find cross-build environment version {version}, available versions: {self.list_versions()}"
            )

        symlink_dir = self.symlink_dir

        if symlink_dir.exists():
            if symlink_dir.is_symlink():
                # symlink to a directory, expected case
                symlink_dir.unlink()
            elif symlink_dir.is_dir():
                # real directory, for backwards compatibility
                shutil.rmtree(symlink_dir)
            else:
                # file. This should not happen unless the user manually created a file
                # but we will remove it anyway
                symlink_dir.unlink()

        symlink_dir.symlink_to(version_path)

    def install(
        self,
        version: str | None = None,
        *,
        url: str | None = None,
        skip_install_cross_build_packages: bool = False,
        force_install: bool = False,
    ) -> Path:
        """
        Install cross-build environment.

        Parameters
        ----------
        version
            The version of the cross-build environment to install. If not specified,
            use the same version as the current version of pyodide-build.
        url
            URL to download the cross-build environment from.
            The URL should point to a tarball containing the cross-build environment.
            This is useful for testing unreleased version of the cross-build environment.

            Warning: if you are downloading from a version that is not the same
            as the current version of pyodide-build, make sure that the cross-build
            environment is compatible with the current version of Pyodide.
        skip_install_cross_build_packages
            If True, skip installing the cross-build packages. This is mostly for testing purposes.
        force_install
            If True, force the installation even if the cross-build environment is not compatible

        Returns
        -------
        Path to the root directory for the cross-build environment.
        """

        if url and version:
            raise ValueError("Cannot specify both version and url")

        if url:
            version = _url_to_version(url)
            download_url = url
        # if default version is specified in the configuration, use that
        elif not version and (default_url := self._get_default_xbuildenv_url()):
            version = _url_to_version(default_url)
            download_url = default_url
        else:
            version = version or self._find_latest_version()

            local_versions = build_env.local_versions()
            release = self._find_remote_release(version)
            if not force_install and not release.is_compatible(
                python_version=local_versions["python"],
                pyodide_build_version=local_versions["pyodide-build"],
            ):
                raise ValueError(
                    f"Version {version} is not compatible with the current environment."
                )

            download_url = release.url

        download_path = self._path_for_version(version)

        if download_path.exists():
            logger.info(
                "The cross-build environment already exists at '%s', skipping download",
                download_path,
            )
        else:
            download_and_unpack_archive(
                download_url, download_path, "Pyodide cross-build environment"
            )

        try:
            # there is an redundant directory "xbuildenv" inside the xbuildenv archive
            # TODO: remove the redundant directory from the archive
            xbuildenv_root = download_path / "xbuildenv"
            xbuildenv_pyodide_root = xbuildenv_root / "pyodide-root"
            install_marker = download_path / ".installed"
            if not install_marker.exists():
                logger.info(
                    "Installing Pyodide cross-build environment to %s", download_path
                )

                if not skip_install_cross_build_packages:
                    self._install_cross_build_packages(
                        xbuildenv_root, xbuildenv_pyodide_root
                    )

                if not url:
                    # If installed from url, skip creating the PyPI index (version is not known)
                    self._create_package_index(xbuildenv_pyodide_root, version)

            install_marker.touch()
            self.use_version(version)
            self._add_version_marker()
        except Exception as e:
            # if the installation failed, remove the downloaded directory
            shutil.rmtree(download_path)
            raise e

        return xbuildenv_pyodide_root

    def _find_latest_version(self) -> str:
        """
        Find the latest compatible cross-build environment release.
        """
        metadata = load_cross_build_env_metadata(self.metadata_url)
        local = build_env.local_versions()
        latest = metadata.get_latest_compatible_release(
            python_version=local["python"],
            pyodide_build_version=local["pyodide-build"],
        )

        if not latest:
            # Check for Python version mismatch
            python_versions = [
                v.python_version_tuple[:2] for v in metadata.list_compatible_releases()
            ]
            pyver = tuple(int(x) for x in local["python"].split("."))
            if pyver > python_versions[0]:
                latest_supported = ".".join(str(x) for x in python_versions[0])
                raise ValueError(
                    f"Python version {local['python']} is not yet supported. The newest supported version of Python is {latest_supported}."
                )

            if pyver < python_versions[-1]:
                oldest_supported = ".".join(str(x) for x in python_versions[-1])
                raise ValueError(
                    f"Python version {local['python']} is too old. The oldest supported version of Python is {oldest_supported}."
                )

            raise ValueError(
                f"Python version {local['python']} is not compatible with pyodide build version {local['pyodide-build']}"
            )

        return latest.version

    def _get_default_xbuildenv_url(self) -> str:
        """
        Get the default URL for the cross-build environment. If not specified, return empty string (no default).
        """
        return build_env.get_host_build_flag("DEFAULT_CROSS_BUILD_ENV_URL")

    def _install_cross_build_packages(
        self, xbuildenv_root: Path, xbuildenv_pyodide_root: Path
    ) -> None:
        """
        Install package that are used in the cross-build environment.

        Parameters
        ----------
        xbuildenv_root
            Path to the xbuildenv directory.
        xbuildenv_pyodide_root
            Path to the pyodide-root directory inside the xbuildenv directory.
        """
        host_site_packages = self._host_site_packages_dir(xbuildenv_pyodide_root)
        host_site_packages.mkdir(exist_ok=True, parents=True)

        install_prefix = (
            [
                uv_helper.find_uv_bin(),
                "pip",
                "install",
            ]
            if uv_helper.should_use_uv()
            else [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-user",
            ]
        )

        result = subprocess.run(
            [
                *install_prefix,
                "-r",
                str(xbuildenv_root / "requirements.txt"),
                "--target",
                str(host_site_packages),
            ],
            capture_output=True,
            encoding="utf8",
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to install cross-build packages: {result.stderr}"
            )

        # Copy the site-packages-extras (coming from the cross-build-files meta.yaml
        # key) over the site-packages directory with the newly installed packages.
        shutil.copytree(
            xbuildenv_root / "site-packages-extras",
            host_site_packages,
            dirs_exist_ok=True,
        )

    def _host_site_packages_dir(
        self, xbuildenv_pyodide_root: Path | None = None
    ) -> Path:
        """
        Returns the path to the hostsitepackages directory in the xbuild environment.
        This is inferred using the current version of the xbuild environment,
        but can optionally be overridden by passing the pyodide root directory as a parameter.

        Parameters
        ----------
        xbuildenv_pyodide_root
            The path to the pyodide root directory inside the xbuild environment.
        """

        if xbuildenv_pyodide_root is None:
            xbuildenv_pyodide_root = self.pyodide_root

        return Path(
            build_env.get_build_environment_vars(pyodide_root=xbuildenv_pyodide_root)[
                "HOSTSITEPACKAGES"
            ]
        )

    def _create_package_index(self, xbuildenv_pyodide_root: Path, version: str) -> None:
        """
        Create the PyPI index for the packages in the xbuild environment.
        TODO: Creating the PyPI Index is not required for the xbuild environment to work, so maybe we can
              move this to a separate command (to pyodide venv?)
        """

        cdn_base = CDN_BASE.format(version=version)
        lockfile_path = xbuildenv_pyodide_root / "dist" / "pyodide-lock.json"

        if not lockfile_path.exists():
            logger.warning(
                "Pyodide lockfile not found at %s. Skipping PyPI index creation",
                lockfile_path,
            )
            return

        lockfile = PyodideLockSpec(**json.loads(lockfile_path.read_bytes()))
        create_package_index(lockfile.packages, xbuildenv_pyodide_root, cdn_base)

    def uninstall_version(self, version: str | None) -> str:
        """
        Uninstall the installed xbuildenv version.

        Parameters
        ----------
        version
            The version of xbuildenv to uninstall.
        """
        if version is None:
            version = self.current_version

        if version is None:
            raise ValueError("No xbuildenv version is currently in use")

        version_path = self._path_for_version(version)

        # if the target version is the current version, remove the symlink
        # to prevent symlinking to a non-existent directory
        if self.symlink_dir.resolve() == version_path:
            self.symlink_dir.unlink()

        if version_path.is_dir():
            shutil.rmtree(version_path)
        else:
            raise ValueError(
                f"Cannot find cross-build environment version {version}, available versions: {self.list_versions()}"
            )

        return version

    def _clone_emscripten(self, emsdk_dir: Path | str | None = None) -> Path:
        """
        Clone the Emscripten SDK repository into the currently selected xbuildenv.

        Parameters
        ----------
        emsdk_dir
            The directory to clone the emsdk into. If not specified, uses the default location
            inside the currently selected xbuildenv.

        Returns
        -------
        Path
            Path to the emsdk directory inside the xbuildenv.
        """
        if not self.symlink_dir.exists():
            raise ValueError(
                "No active xbuildenv. Run `pyodide xbuildenv install` first."
            )

        if emsdk_dir is None:
            xbuild_root = self.symlink_dir.resolve()
            emsdk_dir = xbuild_root / "emsdk"
        else:
            emsdk_dir = Path(emsdk_dir)

        logger.info("Cloning Emscripten SDK into %s", emsdk_dir)

        if emsdk_dir.exists():
            logger.info("Emsdk directory already exists, pulling latest changes...")
            subprocess.run(["git", "-C", str(emsdk_dir), "pull"], check=True)
        else:
            subprocess.run(
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

        return emsdk_dir

    def install_emscripten(self, emscripten_version: str = "latest") -> Path:
        """
        Install and activate Emscripten SDK inside the currently selected xbuildenv.

        Parameters
        ----------
        emscripten_version
            The Emscripten SDK version to install (default: 'latest').

        Returns
        -------
        Path
            Path to the emsdk directory inside the xbuildenv.
        """
        if not self.symlink_dir.exists():
            raise ValueError(
                "No active xbuildenv. Run `pyodide xbuildenv install` first."
            )

        xbuild_root = self.symlink_dir.resolve()
        emsdk_dir = xbuild_root / "emsdk"
        patches_dir = self.pyodide_root / "emsdk" / "patches"
        emscripten_root = emsdk_dir / "upstream" / "emscripten"

        logger.info(
            "Installing Emscripten SDK (version: %s) into %s",
            emscripten_version,
            emsdk_dir,
        )

        # Clone or update emsdk directory
        self._clone_emscripten()

        # Install the specified Emscripten version
        subprocess.run(
            ["./emsdk", "install", "--build=Release", emscripten_version],
            cwd=emsdk_dir,
            check=True,
        )

        # Apply patches from xbuildenv/emsdk/patches directory to upstream/emscripten
        try:
            subprocess.run(
                f"cat {patches_dir}/*.patch | patch -p1 --verbose",
                check=True,
                shell=True,
                cwd=emscripten_root,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to apply Emscripten patches. This may occur if the Emscripten version "
                f"({emscripten_version}) does not match the version for which the patches were generated. "
                f"Please ensure you are using a compatible Emscripten version or update the patches "
                f"in {patches_dir}"
            ) from e

        # Activate the specified Emscripten version
        subprocess.run(
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

        logger.info("Emscripten SDK installed successfully at %s", emsdk_dir)
        return emsdk_dir

    def _add_version_marker(self) -> None:
        """
        Store the Python version in the xbuildenv directory, so we can check compatibility later.
        """
        if not self.symlink_dir.is_dir():
            raise ValueError("cross-build env directory does not exist")

        version_file = self.symlink_dir / PYTHON_VERSION_MARKER_FILE
        version_file.write_text(build_env.local_versions()["python"])

    def version_marker_matches(self) -> tuple[bool, str | None]:
        if not self.symlink_dir.is_dir():
            return False, "cross-build env directory does not exist"

        version_file = self.symlink_dir / PYTHON_VERSION_MARKER_FILE
        if not version_file.exists():
            return False, "Python version marker file not found"

        version_local = build_env.local_versions()["python"]
        version_on_install = version_file.read_text().strip()
        if version_on_install != version_local:
            return False, (
                f"local Python version ({version_local}) does not match the Python version ({version_on_install}) "
                "used to create the Pyodide cross-build environment. "
                "Please switch back to the original Python version, "
                "or reinstall the xbuildenv, by running `pyodide xbuildenv uninstall` and then `pyodide xbuildenv install`"
            )
        return True, None


def _url_to_version(url: str) -> str:
    return url.replace("://", "_").replace(".", "_").replace("/", "_")
