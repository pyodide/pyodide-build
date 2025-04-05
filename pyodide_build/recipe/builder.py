"""
Builds a Pyodide package.
"""

import fnmatch
import http.client
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime
from email.message import Message
from functools import cache
from pathlib import Path
from typing import Any, cast

import requests
from packaging.utils import parse_wheel_filename

from pyodide_build import common, pypabuild
from pyodide_build.build_env import (
    RUST_BUILD_PRELUDE,
    BuildArgs,
    _create_constraints_file,
    get_build_environment_vars,
    get_build_flag,
    get_pyodide_root,
    get_pyversion_major,
    get_pyversion_minor,
    pyodide_tags,
    replace_so_abi_tags,
    wheel_platform,
)
from pyodide_build.common import (
    _environment_substitute_str,
    _get_sha256_checksum,
    chdir,
    exit_with_stdio,
    find_matching_wheel,
    make_zip_archive,
    modify_wheel,
    retag_wheel,
    retrying_rmtree,
)
from pyodide_build.logger import logger
from pyodide_build.recipe.bash_runner import (
    BashRunnerWithSharedEnvironment,
    get_bash_runner,
)
from pyodide_build.recipe.spec import MetaConfig, _SourceSpec


def _make_whlfile(
    *args: Any, owner: int | None = None, group: int | None = None, **kwargs: Any
) -> str:
    return shutil._make_zipfile(*args, **kwargs)  # type: ignore[attr-defined]


shutil.register_archive_format("whl", _make_whlfile, description="Wheel file")
try:
    shutil.register_unpack_format(
        "whl",
        [".whl", ".wheel"],
        shutil._unpack_zipfile,  # type: ignore[attr-defined]
        description="Wheel file",
    )
except shutil.RegistryError:
    # Error: .whl is already registered for "whl"
    pass


def _extract_tarballname(url: str, headers: dict) -> str:
    tarballname = url.split("/")[-1]

    if "Content-Disposition" in headers:
        msg = Message()
        msg["Content-Disposition"] = headers["Content-Disposition"]

        filename = msg.get_filename()
        if filename is not None:
            tarballname = filename

    return tarballname


def check_versions_match(pkg_name: str, wheel_name: str, version: str):
    wheel_version = str(parse_wheel_filename(wheel_name)[1])
    if wheel_version != version:
        raise ValueError(
            f"Version mismatch in {pkg_name}: version in meta.yaml is '{version}' but version from wheel name is '{wheel_version}'"
        )


class RecipeBuilder:
    """
    A class to build a Pyodide meta.yaml recipe.
    """

    def __init__(
        self,
        recipe: str | Path,
        build_args: BuildArgs,
        build_dir: str | Path | None = None,
        force_rebuild: bool = False,
        continue_: bool = False,
    ):
        """
        Parameters
        ----------
        recipe
            The path to the meta.yaml file or the directory containing
            the meta.yaml file.
        build_args
            The extra build arguments passed to the build script.
        build_dir
            The path to the build directory. By default, it will be
            <the directory containing the meta.yaml file> / build
        force_rebuild
            If True, the package will be rebuilt even if it is already up-to-date.
        continue_
            If True, continue a build from the middle. For debugging. Implies "force_rebuild".
        """
        recipe = Path(recipe).resolve()
        self.pkg_root, self.recipe = _load_recipe(recipe)

        self.name = self.recipe.package.name
        self.version = self.recipe.package.version
        self.fullname = f"{self.name}-{self.version}"

        self.source_metadata = self.recipe.source
        self.build_metadata = self.recipe.build
        self.package_type = self.build_metadata.package_type
        self.is_wheel = self.package_type in ["package", "cpython_module"]

        self.build_dir = (
            Path(build_dir).resolve() if build_dir else self.pkg_root / "build"
        )
        if len(str(self.build_dir).split(maxsplit=1)) > 1:
            raise ValueError(
                "PIP_CONSTRAINT contains spaces so pip will misinterpret it. Make sure the path to the package build directory has no spaces.\n"
                "See https://github.com/pypa/pip/issues/13283"
            )
        self.library_install_prefix = self.build_dir.parent.parent / ".libs"
        self.src_extract_dir = (
            self.build_dir / self.fullname
        )  # where we extract the source

        # where the built artifacts are put.
        # For wheels, this is the default location where the built wheels are put by pypa/build.
        # For shared libraries, users should use this directory to put the built shared libraries (can be accessed by DISTDIR env var)
        self.src_dist_dir = self.src_extract_dir / "dist"

        # where Pyodide will look for the built artifacts when building pyodide-lock.json.
        # after building packages, artifacts in src_dist_dir will be copied to dist_dir
        self.dist_dir = self.pkg_root / "dist"
        self.build_args = build_args
        self.force_rebuild = force_rebuild or continue_
        self.continue_ = continue_

    @classmethod
    def get_builder(
        cls,
        recipe: str | Path,
        build_args: BuildArgs,
        build_dir: str | Path | None = None,
        force_rebuild: bool = False,
        continue_: bool = False,
    ) -> "RecipeBuilder":
        recipe = Path(recipe).resolve()
        _, config = _load_recipe(recipe)
        match config.build.package_type:
            case "package" | "cpython_module":
                builder = RecipeBuilderPackage
            case "static_library":
                builder = RecipeBuilderStaticLibrary
            case "shared_library":
                builder = RecipeBuilderSharedLibrary
            case _:
                raise ValueError(f"Unknown package type: {config.build.package_type}")

        return builder(recipe, build_args, build_dir, force_rebuild, continue_)

    def build(self) -> None:
        """
        Build the package. This is the only public method of this class.
        """
        self._check_executables()

        t0 = datetime.now()
        timestamp = t0.strftime("%Y-%m-%d %H:%M:%S")
        logger.info("[%s] Building package %s...", timestamp, self.name)
        success = True
        try:
            self._build()

            if not self.is_wheel:
                (self.build_dir / ".packaged").touch()
        except (Exception, KeyboardInterrupt):
            success = False
            raise
        except SystemExit as e:
            success = e.code == 0
            raise
        finally:
            t1 = datetime.now()
            datestamp = "[{}]".format(t1.strftime("%Y-%m-%d %H:%M:%S"))
            total_seconds = f"{(t1 - t0).total_seconds():.1f}"
            status = "Succeeded" if success else "Failed"
            msg = f"{datestamp} {status} building package {self.name} in {total_seconds} seconds."
            if success:
                logger.success(msg)
            else:
                logger.error(msg)

    def _build_package(self, bash_runner: BashRunnerWithSharedEnvironment) -> None:
        raise NotImplementedError("Subclasses must implement this method")

    def _build(self) -> None:
        if not self.force_rebuild and not needs_rebuild(
            self.pkg_root,
            self.build_dir,
            self.source_metadata,
            self.is_wheel,
            self.version,
        ):
            return

        if self.continue_ and not self.src_extract_dir.exists():
            raise OSError(
                "Cannot find source for rebuild. Expected to find the source "
                f"directory at the path {self.src_extract_dir}, but that path does not exist."
            )

        self._redirect_stdout_stderr_to_logfile()

        if not self.continue_:
            self._prepare_source()
            self._patch()

        with (
            chdir(self.pkg_root),
            get_bash_runner(self._get_helper_vars() | os.environ.copy()) as bash_runner,
        ):
            self._build_package(bash_runner)

    def _check_executables(self) -> None:
        """
        Check that the executables required to build the package are available.
        """
        missing_executables = common.find_missing_executables(
            self.recipe.requirements.executable
        )
        if missing_executables:
            missing_string = ", ".join(missing_executables)
            error_msg = (
                f"The following executables are required to build {self.name}, but missing in the host system: "
                + missing_string
            )
            raise RuntimeError(error_msg)

    def _prepare_source(self) -> None:
        """
        Figure out from the "source" key in the package metadata where to get the source
        from, then get the source into the build directory.
        """

        # clear the build directory
        if self.build_dir.resolve().is_dir():
            retrying_rmtree(self.build_dir)

        self.build_dir.mkdir(parents=True, exist_ok=True)

        if self.source_metadata.url is not None:
            self._download_and_extract()
            return

        # Build from local source, mostly for testing purposes.
        if self.source_metadata.path is None:
            raise ValueError(
                "Incorrect source provided. Either a url or a path must be provided."
            )

        srcdir = self.source_metadata.path.resolve()
        if not srcdir.is_dir():
            raise ValueError(f"path={srcdir} must point to a directory that exists")

        def ignore(path: str, names: list[str]) -> list[str]:
            ignored: list[str] = []

            if fnmatch.fnmatch(path, "*/dist"):
                # Do not copy dist/*.whl files from a dirty source tree;
                # this can lead to "Exception: Unexpected number of wheels" later.
                ignored.extend(name for name in names if name.endswith(".whl"))
            return ignored

        shutil.copytree(srcdir, self.src_extract_dir, ignore=ignore)

        self.src_dist_dir.mkdir(parents=True, exist_ok=True)

    def _download_and_extract(self) -> None:
        """
        Download the source from specified in the package metadata,
        then checksum it, then extract the archive into the build directory.
        """
        build_env = get_build_environment_vars(get_pyodide_root())
        url = cast(str, self.source_metadata.url)  # we know it's not None
        url = _environment_substitute_str(url, build_env)

        max_retry = 3
        for retry_cnt in range(max_retry):
            try:
                response = requests.get(url)
                response.raise_for_status()
            except (
                requests.exceptions.RequestException,
                http.client.HTTPException,
            ) as e:
                if retry_cnt == max_retry - 1:
                    raise RuntimeError(
                        f"Failed to download {url} after {max_retry} trials"
                    ) from e

                continue

            break

        self.build_dir.mkdir(parents=True, exist_ok=True)

        tarballname = _extract_tarballname(url, response.headers)
        tarballpath = self.build_dir / tarballname
        tarballpath.write_bytes(response.content)

        checksum = self.source_metadata.sha256
        if checksum is not None:
            try:
                checksum = _environment_substitute_str(checksum, build_env)
                check_checksum(tarballpath, checksum)
            except Exception:
                tarballpath.unlink()
                raise

        # already built
        if tarballpath.suffix == ".whl":
            check_versions_match(self.name, tarballpath.name, self.version)
            self.src_dist_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(tarballpath, self.src_dist_dir)
            return

        # Use a Python 3.14-like filter (see https://github.com/python/cpython/issues/112760)
        # Can be removed once we use Python 3.14
        # The "data" filter will reset ownership but preserve permissions and modification times
        # Without it, permissions and modification times will be silently skipped if the uid/git
        # is too large for the chown() call. This behavior can lead to "Permission denied" errors
        # (missing x bit) or random strange `make` behavior (due to wrong mtime order) in the CI
        # pipeline.
        shutil.unpack_archive(
            tarballpath,
            self.build_dir,
            filter=None if tarballpath.suffix == ".zip" else "data",
        )

        extract_dir_name = self.source_metadata.extract_dir
        if extract_dir_name is None:
            extract_dir_name = trim_archive_extension(tarballname)

        shutil.move(self.build_dir / extract_dir_name, self.src_extract_dir)
        self.src_dist_dir.mkdir(parents=True, exist_ok=True)

    def _create_constraints_file(self) -> str:
        """
        Creates a pip constraints file by concatenating global constraints (PIP_CONSTRAINT)
        with constraints specific to this package.

        returns the path to the new constraints file.
        """
        host_constraints = _create_constraints_file()

        constraints = self.recipe.requirements.constraint
        if not constraints:
            # nothing to override
            return host_constraints

        new_constraints_file = self.build_dir / "constraints.txt"
        with new_constraints_file.open("w") as f:
            for constraint in constraints:
                f.write(constraint + "\n")

        return host_constraints + " " + str(new_constraints_file)

    def _compile(
        self,
        bash_runner: BashRunnerWithSharedEnvironment,
    ) -> None:
        """
        Runs pypa/build for the package.

        Parameters
        ----------
        bash_runner
            The runner we will use to execute our bash commands. Preserves environment
            variables from one invocation to the next.

        target_install_dir
            The path to the target Python installation

        """

        cflags = self.build_metadata.cflags + " " + self.build_args.cflags
        cxxflags = self.build_metadata.cxxflags + " " + self.build_args.cxxflags
        ldflags = self.build_metadata.ldflags + " " + self.build_args.ldflags

        build_env_ctx = pypabuild.get_build_env(
            env=bash_runner.env,
            pkgname=self.name,
            cflags=cflags,
            cxxflags=cxxflags,
            ldflags=ldflags,
            target_install_dir=self.build_args.target_install_dir,
            exports=self.build_metadata.exports,
            build_dir=self.build_dir,
        )
        config_settings = pypabuild.parse_backend_flags(
            self.build_metadata.backend_flags
        )

        with build_env_ctx as build_env:
            if self.build_metadata.cross_script is not None:
                with BashRunnerWithSharedEnvironment(build_env) as runner:
                    runner.run(
                        self.build_metadata.cross_script,
                        script_name="cross script",
                        cwd=self.src_extract_dir,
                    )
                    build_env = runner.env

            build_env["PIP_CONSTRAINT"] = str(self._create_constraints_file())

            wheel_path = pypabuild.build(
                self.src_extract_dir, self.src_dist_dir, build_env, config_settings
            )
            check_versions_match(self.name, Path(wheel_path).name, self.version)

    def _patch(self) -> None:
        """
        Apply patches to the source.
        """
        token_path = self.src_extract_dir / ".patched"
        if token_path.is_file():
            return

        patches = self.source_metadata.patches
        extras = self.source_metadata.extras
        cast(str, self.source_metadata.url)

        if not patches and not extras:
            return

        # Apply all the patches
        for patch in patches:
            patch_abspath = self.pkg_root / patch
            result = subprocess.run(
                ["patch", "-p1", "--binary", "--verbose", "-i", patch_abspath],
                check=False,
                encoding="utf-8",
                cwd=self.src_extract_dir,
            )
            if result.returncode != 0:
                logger.error("ERROR: Patch %s failed", patch_abspath)
                exit_with_stdio(result)

        # Add any extra files
        for src, dst in extras:
            shutil.copyfile(self.pkg_root / src, self.src_extract_dir / dst)

        token_path.touch()

    def _redirect_stdout_stderr_to_logfile(self) -> None:
        """
        Redirect stdout and stderr to a log file.
        """
        try:
            stdout_fileno = sys.stdout.fileno()
            stderr_fileno = sys.stderr.fileno()

            tee = subprocess.Popen(
                ["tee", self.pkg_root / "build.log"], stdin=subprocess.PIPE
            )

            # Cause tee's stdin to get a copy of our stdin/stdout (as well as that
            # of any child processes we spawn)
            os.dup2(tee.stdin.fileno(), stdout_fileno)  # type: ignore[union-attr]
            os.dup2(tee.stdin.fileno(), stderr_fileno)  # type: ignore[union-attr]
        except OSError:
            # This normally happens when testing
            logger.warning("stdout/stderr does not have a fileno, not logging to file")

    def _get_helper_vars(self) -> dict[str, str]:
        """
        Get the helper variables for the build script.
        """
        return {
            "PKGDIR": str(self.pkg_root),
            "PKG_VERSION": self.version,
            "PKG_BUILD_DIR": str(self.src_extract_dir),
            "DISTDIR": str(self.src_dist_dir),
            # TODO: rename this to something more compatible with Makefile or CMake conventions
            "WASM_LIBRARY_DIR": str(self.library_install_prefix),
            # Emscripten will use this variable to configure pkg-config in emconfigure
            "EM_PKG_CONFIG_PATH": str(self.library_install_prefix / "lib/pkgconfig"),
            # This variable is usually overwritten by emconfigure
            # The value below will only be used if pkg-config is called without emconfigure
            # We use PKG_CONFIG_LIBDIR instead of PKG_CONFIG_PATH,
            # so pkg-config will not look in the default system directories
            "PKG_CONFIG_LIBDIR": str(self.library_install_prefix / "lib/pkgconfig"),
        }


class RecipeBuilderPackage(RecipeBuilder):
    """
    Recipe builder for python packages.
    """

    def _build_package(self, bash_runner: BashRunnerWithSharedEnvironment) -> None:
        if self.recipe.is_rust_package():
            bash_runner.run(
                RUST_BUILD_PRELUDE,
                script_name="rust build prelude",
                cwd=self.src_extract_dir,
            )

        bash_runner.run(
            self.build_metadata.script,
            script_name="build script",
            cwd=self.src_extract_dir,
        )

        url = self.source_metadata.url
        prebuilt_wheel = url and url.endswith(".whl")
        if not prebuilt_wheel:
            self._compile(bash_runner)

        self._package_wheel(bash_runner)
        shutil.copytree(self.src_dist_dir, self.dist_dir, dirs_exist_ok=True)

    def _package_wheel(
        self,
        bash_runner: BashRunnerWithSharedEnvironment,
    ) -> None:
        """Package a wheel

        This unpacks the wheel, runs and "build.post"
        script, and then repacks the wheel.

        Parameters
        ----------
        bash_runner
            The runner we will use to execute our bash commands. Preserves
            environment variables from one invocation to the next.
        """
        wheel = find_matching_wheel(
            self.src_dist_dir.glob("*.whl"), pyodide_tags(), version=self.version
        )
        if not wheel:
            raise RuntimeError(
                f"Found no wheel while building {self.name}. Candidates:\n"
                + "\n".join(f.name for f in self.src_dist_dir.glob("*.whl"))
            )

        if self.package_type == "cpython_module":
            abi = f"cp{get_pyversion_major()}{get_pyversion_minor()}"
            wheel = retag_wheel(wheel, wheel_platform(), python=abi, abi=abi)
        elif "emscripten" in wheel.name:
            # Retag platformed wheels to pyodide
            wheel = retag_wheel(wheel, wheel_platform())

        logger.info("Unpacking wheel to %s", str(wheel))

        name, ver, _ = wheel.name.split("-", 2)

        with modify_wheel(wheel) as wheel_dir:
            # update so abi tags after build is complete but before running post script
            # to maximize sanity.
            replace_so_abi_tags(wheel_dir)
            bash_runner.run(
                self.build_metadata.post, script_name="post script", cwd=wheel_dir
            )

            if self.build_metadata.vendor_sharedlib:
                lib_dir = self.library_install_prefix
                # Old version of Emscripten does not have RUNTIME_PATH section, so only
                # patch the rpath if it is present.
                should_modify_rpath = get_build_flag("PYODIDE_ABI_VERSION") > "2025"
                copy_sharedlibs(
                    wheel, wheel_dir, lib_dir, modify_rpath=should_modify_rpath
                )

            python_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
            host_site_packages = (
                Path(self.build_args.host_install_dir)
                / f"lib/{python_dir}/site-packages"
            )
            if self.build_metadata.cross_build_env:
                subprocess.run(
                    [
                        "pip",
                        "install",
                        "--upgrade",
                        "-t",
                        str(host_site_packages),
                        f"{name}=={ver}",
                    ],
                    check=True,
                )

            for cross_build_file in self.build_metadata.cross_build_files:
                shutil.copy(
                    (wheel_dir / cross_build_file),
                    host_site_packages / cross_build_file,
                )


class RecipeBuilderStaticLibrary(RecipeBuilder):
    """
    Recipe builder for static libraries.
    """

    def _build_package(self, bash_runner: BashRunnerWithSharedEnvironment) -> None:
        bash_runner.run(
            self.build_metadata.script,
            script_name="build script",
            cwd=self.src_extract_dir,
        )


class RecipeBuilderSharedLibrary(RecipeBuilder):
    """
    Recipe builder for shared libraries.
    """

    def _build_package(self, bash_runner: BashRunnerWithSharedEnvironment) -> None:
        bash_runner.run(
            self.build_metadata.script,
            script_name="build script",
            cwd=self.src_extract_dir,
        )

        # copy .so files to dist_dir
        # and create a zip archive of the .so files
        shutil.rmtree(self.dist_dir, ignore_errors=True)
        self.dist_dir.mkdir(parents=True)
        make_zip_archive(self.dist_dir / f"{self.fullname}.zip", self.src_dist_dir)


@cache
def _load_recipe(package_dir: Path) -> tuple[Path, MetaConfig]:
    """
    Load the package configuration from the given directory.

    Parameters
    ----------
    package_dir
        The directory containing the package configuration, or the path to the
        package configuration file.

    Returns
    -------
    pkg_dir
        The directory containing the package configuration.
    pkg
        The package configuration.
    """
    if not package_dir.exists():
        raise FileNotFoundError(f"Package directory {package_dir} does not exist")

    if package_dir.is_dir():
        meta_file = package_dir / "meta.yaml"
    else:
        meta_file = package_dir
        package_dir = meta_file.parent

    return package_dir, MetaConfig.from_yaml(meta_file)


def check_checksum(archive: Path, checksum: str) -> None:
    """
    Checks that an archive matches the checksum in the package metadata.


    Parameters
    ----------
    archive
        the path to the archive we wish to checksum
    checksum
        the checksum we expect the archive to have
    """
    real_checksum = _get_sha256_checksum(archive)
    if real_checksum != checksum:
        raise ValueError(
            f"Invalid sha256 checksum: {real_checksum} != {checksum} (expected)"
        )


def trim_archive_extension(tarballname: str) -> str:
    for extension in [
        ".tar.gz",
        ".tgz",
        ".tar",
        ".tar.bz2",
        ".tbz2",
        ".tar.xz",
        ".txz",
        ".zip",
        ".whl",
    ]:
        if tarballname.endswith(extension):
            return tarballname[: -len(extension)]
    return tarballname


def copy_sharedlibs(
    wheel_file: Path,
    wheel_dir: Path,
    lib_dir: Path,
    modify_rpath=False,
) -> dict[str, Path]:
    from auditwheel_emscripten import copylib, modify_runtime_path, resolve_sharedlib
    from auditwheel_emscripten.wheel_utils import WHEEL_INFO_RE

    match = WHEEL_INFO_RE.match(wheel_file.name)
    if match is None:
        raise RuntimeError(f"Failed to parse wheel file name: {wheel_file.name}")

    dep_map: dict[str, Path] = resolve_sharedlib(
        wheel_dir,
        lib_dir,
    )
    lib_sdir: str = match.group("name") + ".libs"
    if dep_map:
        dep_map_new = copylib(wheel_dir, dep_map, lib_sdir)
        if modify_rpath:
            modify_runtime_path(wheel_dir, lib_sdir)
        logger.info("Copied shared libraries:")
        for lib, path in dep_map_new.items():
            original_path = dep_map[lib]
            logger.info("  %s -> %s", original_path, path)

        return dep_map_new

    return {}


# TODO: move this to common.py or somewhere else
def needs_rebuild(
    pkg_root: Path,
    buildpath: Path,
    source_metadata: _SourceSpec,
    is_wheel: bool = True,
    version: str | None = None,
) -> bool:
    """
    Determines if a package needs a rebuild because its meta.yaml, patches, or
    sources are newer than the `.packaged` thunk.

    pkg_root
        The path to the root directory for the package. Generally
        $PYODIDE_ROOT/packages/<PACKAGES>

    buildpath
        The path to the build directory. By default, it will be
        $(PYOIDE_ROOT)/packages/<PACKAGE>/build/.

    src_metadata
        The source section from meta.yaml.
    """
    dist_dir = pkg_root / "dist"
    if is_wheel:
        previous_wheel = find_matching_wheel(
            dist_dir.glob("*.whl"), pyodide_tags(), version=version
        )
        if not previous_wheel:
            return True
        package_time = previous_wheel.stat().st_mtime
    else:
        packaged_token = buildpath / ".packaged"
        if not packaged_token.is_file():
            logger.debug(
                "%s needs rebuild because %s does not exist", pkg_root, packaged_token
            )
            return True
        package_time = packaged_token.stat().st_mtime

    def source_files() -> Iterator[Path]:
        yield pkg_root / "meta.yaml"
        yield from (pkg_root / patch_path for patch_path in source_metadata.patches)
        yield from (pkg_root / patch_path for [patch_path, _] in source_metadata.extras)
        src_path = source_metadata.path
        if src_path:
            yield from (pkg_root / src_path).resolve().glob("**/*")

    for source_file in source_files():
        source_file = Path(source_file)
        if source_file.stat().st_mtime > package_time:
            return True
    return False
