# Common functions shared by other modules.
# Notes for contributors:
#   This module should not import any other modules from pyodide-build except logger to avoid circular imports.

import contextlib
import hashlib
import os
import shutil
import subprocess
import sys
import textwrap
import time
import tomllib
import warnings
import zipfile
from collections import deque
from collections.abc import Generator, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, NoReturn
from urllib.request import urlopen
from zipfile import ZipFile

import platformdirs
from packaging.tags import Tag
from packaging.utils import canonicalize_name as canonicalize_package_name
from packaging.utils import parse_wheel_filename

from pyodide_build.logger import logger


def xbuildenv_dirname() -> str:
    try:
        from pyodide_build import __version__
    except ImportError:
        __version__ = "0.0.0"

    return f".pyodide-xbuildenv-{__version__}"


@lru_cache(maxsize=1)
def default_xbuildenv_path() -> Path:
    """
    Return the default path to the cross-build environment directory.

    This directory is used when no path is provided to the `pyodide xbuildenv` subcommands.
    """
    dirname = xbuildenv_dirname()
    candidates = []

    # 1. default cache directory
    candidates.append(Path(platformdirs.user_cache_dir()) / dirname)

    # 2. current working directory
    candidates.append(Path.cwd() / dirname)

    for candidate in candidates:
        if _has_write_access(candidate):
            return candidate


def _has_write_access(folder: Path) -> bool:
    """
    Checks if the current user has write access to the given folder using pathlib.
    """
    try:
        if not folder.exists() and folder.parent != folder:
            return _has_write_access(folder.parent)

        return os.access(str(folder), os.W_OK)
    except OSError:
        return False


def _find_matching_wheels(
    wheel_paths: Iterable[Path],
    supported_tags: Sequence[Tag],
    version: str | None = None,
) -> Iterator[Path]:
    """
    Returns the sequence wheels whose tags match the Pyodide interpreter.

    We don't bother ordering them carefully because we are only hoping to find one.

    Parameters
    ----------
    wheel_paths
        A list of paths to wheels
    supported_tags
        A list of tags that the environment supports

    Returns
    -------
    The subset of wheel_paths that have tags that match the Pyodide interpreter.
    """
    for wheel_path in wheel_paths:
        _, wheel_version, _, wheel_tags = parse_wheel_filename(wheel_path.name)
        if version and version != str(wheel_version):
            continue
        for supported_tag in supported_tags:
            if supported_tag in wheel_tags:
                yield wheel_path
                continue


def find_matching_wheel(
    wheel_paths: Iterable[Path], supported_tags: Sequence[Tag], version: str = None
) -> Path | None:
    """
    Find a matching wheel or raise an error if none is present.

    Parameters
    ----------
    wheel_paths
        A list of paths to wheels
    supported_tags
        A list of tags that the environment supports

    Returns
    -------
    The subset of wheel_paths that have tags that match the Pyodide interpreter.
    """
    result = list(_find_matching_wheels(wheel_paths, supported_tags, version))
    if not result:
        return None
    if len(result) > 1:
        raise RuntimeError(
            "Found multiple matching wheels:\n" + "\n".join(w.name for w in result)
        )
    return result[0]


def parse_top_level_import_name(whlfile: Path) -> list[str] | None:
    """
    Parse the top-level import names from a wheel file.
    """

    if not whlfile.name.endswith(".whl"):
        raise RuntimeError(f"{whlfile} is not a wheel file.")

    whlzip = zipfile.Path(whlfile)

    def _valid_package_name(dirname: str) -> bool:
        return all(invalid_chr not in dirname for invalid_chr in ".- ")

    def _has_python_file(subdir: zipfile.Path) -> bool:
        queue = deque([subdir])
        while queue:
            nested_subdir = queue.pop()
            for subfile in nested_subdir.iterdir():
                if subfile.is_file() and subfile.name.endswith(".py"):
                    return True
                elif subfile.is_dir() and _valid_package_name(subfile.name):
                    queue.append(subfile)

        return False

    # If there is no top_level.txt file, we will find top level imports by
    # 1) a python file on a top-level directory
    # 2) a sub directory with __init__.py
    # following: https://github.com/pypa/setuptools/blob/d680efc8b4cd9aa388d07d3e298b870d26e9e04b/setuptools/discovery.py#L122
    top_level_imports = []
    for subdir in whlzip.iterdir():
        if subdir.is_file() and subdir.name.endswith(".py"):
            top_level_imports.append(subdir.name[:-3])
        elif subdir.is_dir() and _valid_package_name(subdir.name):
            if _has_python_file(subdir):
                top_level_imports.append(subdir.name)

    if not top_level_imports:
        logger.warning(
            "WARNING: failed to parse top level import name from %s.", whlfile
        )
        return None

    return top_level_imports


def _environment_substitute_str(
    string: str, env: Mapping[str, str] | None = None
) -> str:
    """
    Substitute $(VAR) in string with the value of the environment variable VAR.

    Parameters
    ----------
    string
        A string

    env
        A dictionary of environment variables. If None, use os.environ.

    Returns
    -------
    A string with the substitutions applied.
    """
    if env is None:
        env = dict(os.environ)

    for e_name, e_value in env.items():
        string = string.replace(f"$({e_name})", e_value)

    return string


def environment_substitute_args(
    args: dict[str, str], env: dict[str, str] | None = None
) -> dict[str, Any]:
    """
    Substitute $(VAR) in args with the value of the environment variable VAR.

    Parameters
    ----------
    args
        A dictionary of arguments

    env
        A dictionary of environment variables. If None, use os.environ.

    Returns
    -------
    A dictionary of arguments with the substitutions applied.
    """
    if env is None:
        env = dict(os.environ)
    subbed_args = {}
    for arg, value in args.items():
        if isinstance(value, str):
            value = _environment_substitute_str(value, env)
        subbed_args[arg] = value
    return subbed_args


@contextlib.contextmanager
def replace_env(build_env: Mapping[str, str]) -> Generator[None, None, None]:
    old_environ = dict(os.environ)
    os.environ.clear()
    os.environ.update(build_env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)


def exit_with_stdio(result: subprocess.CompletedProcess[str]) -> NoReturn:
    if result.stdout:
        logger.error("  stdout:")
        logger.error(textwrap.indent(result.stdout, "    "))
    if result.stderr:
        logger.error("  stderr:")
        logger.error(textwrap.indent(result.stderr, "    "))
    raise SystemExit(result.returncode)


def find_missing_executables(executables: list[str]) -> list[str]:
    return list(filter(lambda exe: shutil.which(exe) is None, executables))


@contextmanager
def chdir(new_dir: Path) -> Generator[None, None, None]:
    orig_dir = Path.cwd()
    try:
        os.chdir(new_dir)
        yield
    finally:
        os.chdir(orig_dir)


def get_num_cores() -> int:
    """
    Return the number of CPUs the current process can use.
    If the number of CPUs cannot be determined, return 1.
    """
    from pyodide_build.vendor.loky import cpu_count

    return cpu_count()


def make_zip_archive(
    archive_path: Path,
    input_dir: Path,
    compression_level: int = 6,
) -> None:
    """Create a zip archive out of a input folder

    Parameters
    ----------
    archive_path
       Path to the zip file that will be created
    input_dir
       input dir to compress
    compression_level
       compression level of the resulting zip file.
    """
    if compression_level > 0:
        compression = zipfile.ZIP_DEFLATED
    else:
        compression = zipfile.ZIP_STORED

    with zipfile.ZipFile(
        archive_path, "w", compression=compression, compresslevel=compression_level
    ) as zf:
        for file in input_dir.rglob("*"):
            zf.write(file, file.relative_to(input_dir))


def repack_zip_archive(archive_path: Path, compression_level: int = 6) -> None:
    """Repack zip archive with a different compression level"""
    if compression_level > 0:
        compression = zipfile.ZIP_DEFLATED
    else:
        compression = zipfile.ZIP_STORED

    with TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / archive_path.name
        shutil.move(archive_path, input_path)
        with (
            zipfile.ZipFile(input_path) as fh_zip_in,
            zipfile.ZipFile(
                archive_path,
                "w",
                compression=compression,
                compresslevel=compression_level,
            ) as fh_zip_out,
        ):
            for name in fh_zip_in.namelist():
                fh_zip_out.writestr(name, fh_zip_in.read(name))


def _get_sha256_checksum(archive: Path) -> str:
    """Compute the sha256 checksum of a file

    Parameters
    ----------
    archive
        the path to the archive we wish to checksum

    Returns
    -------
    checksum
         sha256 checksum of the archive
    """
    CHUNK_SIZE = 1 << 16
    h = hashlib.sha256()
    with open(archive, "rb") as fd:
        while True:
            chunk = fd.read(CHUNK_SIZE)
            h.update(chunk)
            if len(chunk) < CHUNK_SIZE:
                break
    return h.hexdigest()


def unpack_wheel(wheel_path: Path, target_dir: Path | None = None) -> None:
    if target_dir is None:
        target_dir = wheel_path.parent
    result = subprocess.run(
        [sys.executable, "-m", "wheel", "unpack", wheel_path, "-d", target_dir],
        check=False,
        encoding="utf-8",
    )
    if result.returncode != 0:
        logger.error("ERROR: Unpacking wheel %s failed", wheel_path.name)
        exit_with_stdio(result)


def pack_wheel(wheel_dir: Path, target_dir: Path | None = None) -> None:
    if target_dir is None:
        target_dir = wheel_dir.parent
    result = subprocess.run(
        [sys.executable, "-m", "wheel", "pack", wheel_dir, "-d", target_dir],
        check=False,
        encoding="utf-8",
    )
    if result.returncode != 0:
        logger.error("ERROR: Packing wheel %s failed", wheel_dir)
        exit_with_stdio(result)


@contextmanager
def modify_wheel(wheel: Path) -> Iterator[Path]:
    """Unpacks the wheel into a temp directory and yields the path to the
    unpacked directory.

    The body of the with block is expected to inspect the wheel contents and
    possibly change it. If the body of the "with" block is successful, on
    exiting the with block the wheel contents are replaced with the updated
    contents of unpacked directory. If an exception is raised, then the original
    wheel is left unchanged.
    """
    with TemporaryDirectory() as temp_dir:
        unpack_wheel(wheel, Path(temp_dir))
        name, ver, _ = wheel.name.split("-", 2)
        wheel_dir_name = f"{name}-{ver}"
        wheel_dir = Path(temp_dir) / wheel_dir_name
        yield wheel_dir
        wheel.unlink()
        pack_wheel(wheel_dir, wheel.parent)


def retag_wheel(
    wheel_path: Path,
    platform: str,
    *,
    python: str | None = None,
    abi: str | None = None,
) -> Path:
    extra_flags = []
    if python:
        extra_flags += ["--python-tag", python]
    if abi:
        extra_flags += ["--abi-tag", abi]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "wheel",
            "tags",
            wheel_path,
            "--platform-tag",
            platform,
            "--remove",
            *extra_flags,
        ],
        check=False,
        encoding="utf-8",
        capture_output=True,
    )
    if result.returncode != 0:
        logger.error("ERROR: Retagging wheel %s to %s failed", wheel_path, platform)
        exit_with_stdio(result)
    return wheel_path.parent / result.stdout.splitlines()[-1].strip()


def extract_wheel_metadata_file(wheel_path: Path, output_path: Path) -> None:
    """Extracts the METADATA file from the given wheel and writes it to the
    output path.

    Raises a RuntimeError if the METADATA file does not exist.

    For a wheel called "NAME-VERSION-...", the METADATA file is expected to be
    found in a directory inside the wheel archive, whose name starts with NAME
    and ends with ".dist-info". See:
    https://packaging.python.org/en/latest/specifications/binary-distribution-format/#file-contents
    """
    with ZipFile(wheel_path, mode="r") as wheel:
        pkg_name = wheel_path.name.split("-", 1)[0]
        dist_info_dir = get_wheel_dist_info_dir(wheel, pkg_name)
        metadata_path = f"{dist_info_dir}/METADATA"
        try:
            wheel.getinfo(metadata_path).filename = output_path.name
            wheel.extract(metadata_path, output_path.parent)
        except KeyError as err:
            raise RuntimeError(f"METADATA file not found for {pkg_name}") from err


def get_wheel_dist_info_dir(wheel: ZipFile, pkg_name: str) -> str:
    """Returns the path of the contained .dist-info directory.

    Raises a RuntimeError if the directory is not found, more than
    one is found, or it does not match the provided `pkg_name`.

    Adapted from:
    https://github.com/pypa/pip/blob/ea727e4d6ab598f34f97c50a22350febc1214a97/src/pip/_internal/utils/wheel.py#L38
    """

    # Zip file path separators must be /
    subdirs = {name.split("/", 1)[0] for name in wheel.namelist()}
    info_dirs = [subdir for subdir in subdirs if subdir.endswith(".dist-info")]

    if len(info_dirs) == 0:
        raise RuntimeError(f".dist-info directory not found for {pkg_name}")

    if len(info_dirs) > 1:
        raise RuntimeError(
            f"multiple .dist-info directories found for {pkg_name}: {', '.join(info_dirs)}"
        )

    (info_dir,) = info_dirs

    info_dir_name = canonicalize_package_name(info_dir)
    canonical_name = canonicalize_package_name(pkg_name)

    if not info_dir_name.startswith(canonical_name):
        raise RuntimeError(
            f".dist-info directory {info_dir!r} does not start with {canonical_name!r}"
        )

    return info_dir


def check_wasm_magic_number(file_path: Path) -> bool:
    WASM_BINARY_MAGIC = b"\0asm"
    with file_path.open(mode="rb") as file:
        return file.read(4) == WASM_BINARY_MAGIC


def search_pyproject_toml(
    curdir: str | Path, max_depth: int = 10
) -> tuple[Path, dict[str, Any]] | tuple[None, None]:
    """
    Recursively search for the pyproject.toml file in the parent directories.
    """

    # We want to include "curdir" in parent_dirs, so add a garbage suffix
    parent_dirs = (Path(curdir) / "garbage").parents[:max_depth]

    for base in parent_dirs:
        pyproject_file = base / "pyproject.toml"

        if not pyproject_file.is_file():
            continue

        try:
            with pyproject_file.open("rb") as f:
                configs = tomllib.load(f)
                return pyproject_file, configs
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Could not parse {pyproject_file}.") from e

    return None, None


def to_bool(value: str) -> bool:
    """
    Convert a string to a boolean value. Useful for parsing environment variables.
    """
    return value.lower() not in {"", "0", "false", "no", "off"}


def download_and_unpack_archive(
    url: str, path: Path, descr: str, *, exists_ok: bool = False
) -> None:
    """
    Download the cross-build environment from the given URL and extract it to the given path.

    Parameters
    ----------
    url
        URL to download the cross-build environment from.
    path
        Path to extract the cross-build environment to.
        If the path already exists, raise an error.
    """
    logger.info("Downloading %s from %s", descr, url)

    if not exists_ok and path.exists():
        raise FileExistsError(f"Path {path} already exists")

    try:
        resp = urlopen(url)
        data = resp.read()
    except Exception as e:
        raise ValueError(f"Failed to download {descr} from {url}") from e

    # FIXME: requests makes a verbose output (see: https://github.com/pyodide/pyodide/issues/4810)
    # r = requests.get(url)

    # if r.status_code != 200:
    #     raise ValueError(
    #         f"Failed to download cross-build environment from {url} (status code: {r.status_code})"
    #     )

    with NamedTemporaryFile(suffix=".tar") as f:
        f_path = Path(f.name)
        f_path.write_bytes(data)
        with warnings.catch_warnings():
            # Python 3.12-3.13 emits a DeprecationWarning when using shutil.unpack_archive without a filter,
            # but filter doesn't work well for zip files, so we suppress the warning until we find a better solution.
            # https://github.com/python/cpython/issues/112760
            warnings.simplefilter("ignore")
            shutil.unpack_archive(str(f_path), path)


def retrying_rmtree(d):
    """Sometimes rmtree fails with OSError: Directory not empty

    Try again a few times if this happens.
    See: https://github.com/python/cpython/issues/128076
    """
    for _ in range(3):
        try:
            return shutil.rmtree(d)
        except OSError as e:
            if e.strerror == "Directory not empty":
                # wait a bit and try again up to 3 tries
                time.sleep(0.01)
            else:
                raise
    raise RuntimeError(f"shutil.rmtree('{d}') failed with ENOTEMPTY three times")
