#!/usr/bin/env python3

import contextlib
import json
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib import request

from packaging.version import Version
from ruamel.yaml import YAML

from pyodide_build.common import parse_top_level_import_name
from pyodide_build.logger import logger


class URLDict(TypedDict):
    comment_text: str
    digests: dict[str, Any]
    downloads: int
    filename: str
    has_sig: bool
    md5_digest: str
    packagetype: str
    python_version: str
    requires_python: str
    size: int
    upload_time: str
    upload_time_iso_8601: str
    url: str
    yanked: bool
    yanked_reason: str | None


class MetadataDict(TypedDict):
    info: dict[str, Any]
    last_serial: int
    releases: dict[str, list[dict[str, Any]]]
    urls: list[URLDict]
    vulnerabilities: list[Any]


class MkpkgSkipped(Exception):
    pass


class MkpkgFailedException(Exception):
    pass


SDIST_EXTENSIONS = tuple(
    extension
    for (name, extensions, description) in shutil.get_unpack_formats()
    for extension in extensions
)


def _find_sdist(pypi_metadata: MetadataDict) -> URLDict | None:
    """Get sdist file path from the metadata"""
    # The first one we can use. Usually a .tar.gz
    for entry in pypi_metadata["urls"]:
        if entry["packagetype"] == "sdist" and entry["filename"].endswith(
            SDIST_EXTENSIONS
        ):
            return entry
    return None


def _find_wheel(pypi_metadata: MetadataDict, native: bool = False) -> URLDict | None:
    """Get wheel file path from the metadata"""
    predicate = lambda filename: filename.endswith(
        ".whl" if native else "py3-none-any.whl"
    )

    for entry in pypi_metadata["urls"]:
        if entry["packagetype"] == "bdist_wheel" and predicate(entry["filename"]):
            return entry
    return None


def _find_dist(
    pypi_metadata: MetadataDict, source_types: list[Literal["wheel", "sdist"]]
) -> URLDict:
    """Find a wheel or sdist, as appropriate.

    source_types controls which types (wheel and/or sdist) are accepted and also
    the priority order.
    E.g., ["wheel", "sdist"] means accept either wheel or sdist but prefer wheel.
    ["sdist", "wheel"] means accept either wheel or sdist but prefer sdist.
    """
    result = None
    for source in source_types:
        if source == "wheel":
            result = _find_wheel(pypi_metadata)
        if source == "sdist":
            result = _find_sdist(pypi_metadata)
        if result:
            return result

    types_str = " or ".join(source_types)
    name = pypi_metadata["info"].get("name")
    url = pypi_metadata["info"].get("package_url")
    raise MkpkgFailedException(f"No {types_str} found for package {name} ({url})")


def _get_metadata(package: str, version: str | None = None) -> MetadataDict:
    """Download metadata for a package from PyPI"""
    version = ("/" + version) if version is not None else ""
    url = f"https://pypi.org/pypi/{package}{version}/json"

    try:
        with urllib.request.urlopen(url) as fd:
            pypi_metadata = json.load(fd)
    except urllib.error.HTTPError as e:
        raise MkpkgFailedException(
            f"Failed to load metadata for {package}{version} from "
            f"https://pypi.org/pypi/{package}{version}/json: {e}"
        ) from e

    return pypi_metadata


@contextlib.contextmanager
def _download_wheel(pypi_metadata: URLDict) -> Iterator[Path]:
    response = request.urlopen(pypi_metadata["url"])
    whlname = Path(response.geturl()).name

    with tempfile.TemporaryDirectory() as tmpdirname:
        whlpath = Path(tmpdirname, whlname)
        whlpath.write_bytes(response.read())
        yield whlpath


def run_prettier(meta_path: str | Path) -> None:
    subprocess.run(["npx", "prettier", "-w", meta_path])


def make_package(
    packages_dir: Path,
    package: str,
    version: str | None = None,
    source_fmt: Literal["wheel", "sdist"] | None = None,
) -> None:
    """
    Creates a template that will work for most pure Python packages,
    but will have to be edited for more complex things.
    """
    logger.info("Creating meta.yaml package for %s", package)

    yaml = YAML()

    pypi_metadata = _get_metadata(package, version)

    if source_fmt:
        sources = [source_fmt]
    else:
        # Prefer wheel unless sdist is specifically requested.
        sources = ["wheel", "sdist"]
    dist_metadata = _find_dist(pypi_metadata, sources)

    native_wheel_metadata = _find_wheel(pypi_metadata, native=True)

    top_level = None
    if native_wheel_metadata is not None:
        with _download_wheel(native_wheel_metadata) as native_wheel_path:
            top_level = parse_top_level_import_name(native_wheel_path)

    url = dist_metadata["url"]
    sha256 = dist_metadata["digests"]["sha256"]
    version = pypi_metadata["info"]["version"]

    homepage = pypi_metadata["info"]["home_page"]
    summary = pypi_metadata["info"]["summary"]
    license = pypi_metadata["info"]["license"]
    pypi = "https://pypi.org/project/" + package

    yaml_content = {
        "package": {
            "name": package,
            "version": version,
            "top-level": top_level or ["PUT_TOP_LEVEL_IMPORT_NAMES_HERE"],
        },
        "source": {"url": url, "sha256": sha256},
        "about": {
            "home": homepage,
            "PyPI": pypi,
            "summary": summary,
            "license": license,
        },
        "extra": {"recipe-maintainers": ["PUT_YOUR_GITHUB_USERNAME_HERE"]},
    }

    package_dir = packages_dir / package
    package_dir.mkdir(parents=True, exist_ok=True)

    meta_path = package_dir / "meta.yaml"
    if meta_path.exists():
        raise MkpkgFailedException(f"The package {package} already exists")

    yaml.representer.ignore_aliases = lambda *_: True
    yaml.dump(yaml_content, meta_path)
    try:
        run_prettier(meta_path)
    except FileNotFoundError:
        warnings.warn(
            "'npx' executable missing, output has not been prettified.", stacklevel=1
        )

    logger.success(f"Output written to {meta_path}")


def update_package(
    root: Path,
    package: str,
    version: str | None = None,
    update_patched: bool = True,
    source_fmt: Literal["wheel", "sdist"] | None = None,
) -> None:
    yaml = YAML()

    meta_path = root / package / "meta.yaml"
    if not meta_path.exists():
        logger.error("%s does not exist", meta_path)
        raise MkpkgFailedException(f"{package} recipe not found at {meta_path}")

    yaml_content = yaml.load(meta_path.read_bytes())

    build_info = yaml_content.get("build", {})
    ty = build_info.get("type", None)
    if ty in ["static_library", "shared_library", "cpython_module"]:
        raise MkpkgSkipped(f"{package} is a {ty.replace('_', ' ')}!")

    if "url" not in yaml_content["source"]:
        raise MkpkgSkipped(f"{package} is a local package!")

    if yaml_content["source"]["url"].endswith("whl"):
        old_fmt = "wheel"
    else:
        old_fmt = "sdist"

    pypi_metadata = _get_metadata(package, version)

    # Grab versions from metadata
    pypi_ver = Version(pypi_metadata["info"]["version"])
    local_ver = Version(yaml_content["package"]["version"])

    # and grab checksums from metadata
    source_fmt = source_fmt or old_fmt
    dist_metadata = _find_dist(pypi_metadata, [source_fmt])
    sha256 = dist_metadata["digests"]["sha256"]
    sha256_local = yaml_content["source"].get("sha256")

    # fail if local version is newer than PyPI version
    # since updating isn't possible in that case
    if pypi_ver < local_ver:
        raise MkpkgFailedException(
            f"Local version {local_ver} is newer than PyPI version {pypi_ver}, "
            f"cannot update {package}. Please verify in case the version was "
            "updated manually and is correct."
        )

    # conditions to check if the package is up to date
    is_sha256_up_to_date = sha256 == sha256_local
    is_version_up_to_date = pypi_ver == local_ver

    already_up_to_date = (is_sha256_up_to_date and is_version_up_to_date) and (
        source_fmt is None or source_fmt == old_fmt
    )
    if already_up_to_date:
        logger.success(
            f"{package} already up to date."
            f" Local: {local_ver} and PyPI: {pypi_ver}"
            f" and checksum received: {sha256} matches local: {sha256_local} ✅"
        )
        return

    logger.info(
        "%s is out of date: either %s < %s or checksums might have mismatched: received %s against local %s 🚨",
        package,
        local_ver,
        pypi_ver,
        sha256,
        sha256_local,
    )

    if yaml_content["source"].get("patches"):
        if update_patched:
            logger.warning(
                "Pyodide applies patches to %s. Update the patches (if needed) to avoid build failing.",
                package,
            )
        else:
            raise MkpkgFailedException(
                f"Pyodide applies patches to {package}. Skipping update."
                f" Use --update-patched to force updating {package}."
            )

    if source_fmt:
        # require the type requested
        sources = [source_fmt]
    elif old_fmt == "wheel":
        # prefer wheel to sdist
        sources = ["wheel", "sdist"]
    else:
        # prefer sdist to wheel
        sources = ["sdist", "wheel"]

    dist_metadata = _find_dist(pypi_metadata, sources)

    yaml_content["source"]["url"] = dist_metadata["url"]
    yaml_content["source"].pop("md5", None)
    yaml_content["source"]["sha256"] = dist_metadata["digests"]["sha256"]
    yaml_content["package"]["version"] = pypi_metadata["info"]["version"]

    yaml.dump(yaml_content, meta_path)
    run_prettier(meta_path)

    logger.success(f"Updated {package} from {local_ver} to {pypi_ver}.")
