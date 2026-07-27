import json
import logging
import os
from contextlib import contextmanager
from functools import cache
from typing import Any, Literal, NewType
from urllib.parse import urlparse

import cattrs
from attrs import asdict, define, field
from packaging.version import Version

DEFAULT_CROSS_BUILD_ENV_METADATA_URL = (
    "https://pyodide.github.io/pyodide/api/v2/pyodide-cross-build-environments.json"
)
NIGHTLY_CROSS_BUILD_ENV_METADATA_URL = (
    "https://pyodide.github.io/pyodide-build-environment-nightly/api/v2/release.json"
)
NIGHTLY_DEBUG_CROSS_BUILD_ENV_METADATA_URL = (
    "https://pyodide.github.io/pyodide-build-environment-nightly/api/v2/debug.json"
)
STABLE_DEBUG_CROSS_BUILD_ENV_METADATA_URL = (
    "https://pyodide.github.io/pyodide/api/v2/debug.json"
)
CROSS_BUILD_ENV_METADATA_URL_ENV_VAR = "PYODIDE_CROSS_BUILD_ENV_METADATA_URL"

# The published streams a cross-build environment can be installed from. These
# are the ones with release metadata behind them, so only these can be asked for
# by name, with --nightly and --debug.
type ReleaseSource = Literal["stable", "stable-debug", "nightly", "nightly-debug"]

# An environment installed with --url has no release behind it to name, so the
# URL it came from is its source. A distinct type rather than a bare str, so
# that a URL cannot be passed where a release stream is expected.
SourceURL = NewType("SourceURL", str)

# Where a cross-build environment came from, once installed
type SourceType = ReleaseSource | SourceURL

DEFAULT_SOURCE: ReleaseSource = "stable"

CROSS_BUILD_ENV_METADATA_URLS: dict[ReleaseSource, str] = {
    "stable": DEFAULT_CROSS_BUILD_ENV_METADATA_URL,
    "stable-debug": STABLE_DEBUG_CROSS_BUILD_ENV_METADATA_URL,
    "nightly": NIGHTLY_CROSS_BUILD_ENV_METADATA_URL,
    "nightly-debug": NIGHTLY_DEBUG_CROSS_BUILD_ENV_METADATA_URL,
}


def parse_source_url(value: str) -> SourceURL | None:
    """
    Return ``value`` as a `SourceURL`, or None when it is not one.

    Parameters
    ----------
    value
        The string to interpret as a URL an xbuildenv was downloaded from.

    Returns
    -------
    SourceURL | None
        The URL, or None if it does not parse as one. Any scheme is accepted:
        the archive is fetched with `urlopen`, which handles ftp and whatever
        else the openers in use support.
    """
    try:
        parsed = urlparse(value)
    except ValueError:
        return None

    # A URL needs a scheme, and something for that scheme to address
    if not parsed.scheme or not (parsed.netloc or parsed.path):
        return None

    return SourceURL(value)


@define
class CrossBuildEnvReleaseSpec:
    # The version of the Pyodide
    version: str
    # The URL to the cross-build environment tarball
    url: str
    # The version of the Python interpreter
    python_version: str
    # The version of the Emscripten SDK
    emscripten_version: str
    # The SHA256 hash of the cross-build environment tarball
    sha256: str | None = None
    # The UTC timestamp when the release was published on GitHub (ISO 8601)
    published_at: str = ""
    # Minimum and maximum pyodide-build versions that are compatible with this release
    min_pyodide_build_version: str | None = None
    max_pyodide_build_version: str | None = None

    @property
    def python_version_tuple(self) -> tuple[int, int, int]:
        v = Version(self.python_version)
        return (v.major, v.minor, v.micro)

    @property
    def emscripten_version_tuple(self) -> tuple[int, int, int]:
        v = Version(self.emscripten_version)
        return (v.major, v.minor, v.micro)

    def is_compatible(
        self,
        python_version: str | None = None,
        emscripten_version: str | None = None,
        pyodide_build_version: str | None = None,
    ) -> bool:
        """
        Check if the release is compatible with the given params

        Parameters
        ----------
        python_version
            The version of the Python interpreter. If None, it is not checked
        emscripten_version
            The version of the Emscripten SDK. If None, it is not checked
        pyodide_build_version
            The version of the pyodide-build. If None, it is not checked

        Returns
        -------
        bool
            True if the release is compatible with the given params, False otherwise
        """
        if python_version is not None:
            major, minor, _ = self.python_version_tuple
            v = Version(python_version)
            if major != v.major or minor != v.minor:
                return False

        if (
            emscripten_version is not None
            and self.emscripten_version != emscripten_version
        ):
            # TODO: relax the emscripten version check
            return False

        if pyodide_build_version is not None:
            if self.min_pyodide_build_version is not None:
                if Version(pyodide_build_version) < Version(
                    self.min_pyodide_build_version
                ):
                    return False
            if self.max_pyodide_build_version is not None:
                if Version(pyodide_build_version) > Version(
                    self.max_pyodide_build_version
                ):
                    return False

        return True


@define
class CrossBuildEnvMetaSpec:
    """
    The specification for the Pyodide cross-build environment metadata
    """

    releases: dict[str, CrossBuildEnvReleaseSpec] = field()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CrossBuildEnvMetaSpec":
        return _converter.structure(data, cls)

    @classmethod
    def from_json(cls, data: str) -> "CrossBuildEnvMetaSpec":
        return cls.from_dict(json.loads(data))

    def to_dict(self) -> dict[str, Any]:
        # ``None`` valued fields are omitted (mirrors pydantic's
        # ``model_dump(exclude_none=True)``) so that optional release fields such
        # as ``max_pyodide_build_version`` are left out of the serialized output.
        return asdict(self, filter=lambda _attr, value: value is not None)

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def list_compatible_releases(
        self,
        python_version: str | None = None,
        emscripten_version: str | None = None,
        pyodide_build_version: str | None = None,
    ) -> list[CrossBuildEnvReleaseSpec]:
        """
        Get the list of compatible releases

        Parameters
        ----------
        python_version
            The version of the Python interpreter. If None, it is not checked
        emscripten_version
            The version of the Emscripten SDK. If None, it is not checked
        pyodide_build_version
            The version of the pyodide-build. If None, it is not checked

        Returns
        -------
        The list of compatible releases, sorted by version number in descending order (latest first)
        """

        return sorted(
            [
                release
                for release in self.releases.values()
                if release.is_compatible(
                    python_version, emscripten_version, pyodide_build_version
                )
            ],
            key=lambda r: Version(r.version),
            reverse=True,
        )

    def get_latest_compatible_release(
        self,
        python_version: str | None = None,
        emscripten_version: str | None = None,
        pyodide_build_version: str | None = None,
    ) -> CrossBuildEnvReleaseSpec | None:
        """
        Get the latest compatible release

        Parameters
        ----------
        python_version
            The version of the Python interpreter. If None, it is not checked
        emscripten_version
            The version of the Emscripten SDK. If None, it is not checked
        pyodide_build_version
            The version of the pyodide-build. If None, it is not checked

        Returns
        -------
        The latest compatible release, or None if no compatible release is found
        """
        compatible_releases = self.list_compatible_releases(
            python_version, emscripten_version, pyodide_build_version
        )
        if not compatible_releases:
            return None

        return compatible_releases[0]

    def get_release(
        self,
        version: str,
    ) -> CrossBuildEnvReleaseSpec:
        """
        Get the release with the given version

        Parameters
        ----------
        version
            The version of the release

        Returns
        -------
        CrossBuildEnvReleaseSpec
            The release with the given version
        """
        if version not in self.releases:
            raise KeyError(f"Cannot find a version {version}")

        return self.releases[version]


_converter = cattrs.Converter(detailed_validation=False)


@contextmanager
def _suppress_urllib3_logging():
    """
    Temporarily suppresses urllib3 logging for internal use.
    """
    logger = logging.getLogger("urllib3")
    original_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(original_level)


def cross_build_env_metadata_url(source: ReleaseSource = DEFAULT_SOURCE) -> str:
    """
    Get the URL to the Pyodide cross-build environment metadata

    Parameters
    ----------
    source
        The source to get the metadata for. Only the stable source honours the
        environment variable override below, since naming any other source is
        already a choice of metadata file.

    Returns
    -------
    str
        The URL to the Pyodide cross-build environment metadata
    """

    # If it's not a stable environment, we know which metadata file to use, so don't check the environment variable
    if source != DEFAULT_SOURCE:
        return CROSS_BUILD_ENV_METADATA_URLS[source]

    # The default URL can be overridden by the PYODIDE_CROSS_BUILD_ENV_METADATA_URL environment variable
    # This has two purposes:
    # 1. When running tests, we can set this variable to use a local metadata file
    # 2. If we change the URL for the metadata file, people can set this variable to use the new URL

    url = os.environ.get(
        key=CROSS_BUILD_ENV_METADATA_URL_ENV_VAR,
        default=DEFAULT_CROSS_BUILD_ENV_METADATA_URL,
    )

    return url


def source_for_metadata_url(url: str) -> ReleaseSource | None:
    """
    Get the source that publishes its metadata at the given URL.

    Returns
    -------
    ReleaseSource | None
        The matching source, or None if the URL is not one of the known
        metadata files (a custom metadata file, for instance).
    """
    for source, source_url in CROSS_BUILD_ENV_METADATA_URLS.items():
        if url == source_url:
            return source

    return None


@cache
def load_cross_build_env_metadata(url_or_filename: str) -> CrossBuildEnvMetaSpec:
    """
    Load the Pyodide cross-build environment metadata from the given URL or filename

    Returns
    -------
    CrossBuildEnvMetaSpec
        The Pyodide cross-build environment metadata
    """
    if url_or_filename.startswith("http"):
        import requests

        with _suppress_urllib3_logging():
            with requests.get(url_or_filename) as response:
                response.raise_for_status()
            data = response.json()

        return CrossBuildEnvMetaSpec.from_dict(data)

    with open(url_or_filename) as f:
        return CrossBuildEnvMetaSpec.from_dict(json.load(f))
