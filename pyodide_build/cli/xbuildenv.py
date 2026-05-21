from pathlib import Path

import click

from pyodide_build.build_env import get_build_flag, local_versions
from pyodide_build.common import default_xbuildenv_path
from pyodide_build.views import MetadataView
from pyodide_build.xbuildenv import CrossBuildEnvManager
from pyodide_build.xbuildenv_releases import (
    NIGHTLY_CROSS_BUILD_ENV_METADATA_URL,
    NIGHTLY_DEBUG_CROSS_BUILD_ENV_METADATA_URL,
    cross_build_env_metadata_url,
    load_cross_build_env_metadata,
)

DEFAULT_PATH = default_xbuildenv_path()


@click.group(invoke_without_command=True)
@click.pass_context
def app(ctx: click.Context) -> None:
    """Manage cross-build environment for building packages for Pyodide."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def check_xbuildenv_root(path: Path) -> None:
    if not path.is_dir():
        click.echo(f"Cross-build environment not found in {path.resolve()}")
        raise SystemExit(1)


@app.command("install")
@click.argument("version", default=None, required=False)
@click.option(
    "--path",
    type=click.Path(path_type=Path),
    default=DEFAULT_PATH,
    envvar="PYODIDE_XBUILDENV_PATH",
    show_envvar=True,
    help="destination to download cross-build environment directory to.",
)
@click.option(
    "--url",
    default=None,
    help="URL to download cross-build environment from.",
)
@click.option(
    "--force",
    "-f",
    "force_install",
    is_flag=True,
    default=False,
    help="force installation even if the version is not compatible.",
)
@click.option(
    "--nightly",
    is_flag=True,
    default=False,
    help="install a nightly cross-build environment instead of a stable release.",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="install the debug variant of the cross-build environment (nightly only).",
)
@click.option(
    "--skip-cross-build-packages",
    is_flag=True,
    default=False,
    envvar="PYODIDE_SKIP_CROSS_BUILD_PACKAGES",
    show_envvar=True,
    help="Deprecated, no-op. Cross-build packages are installed lazily "
    "when required by build dependencies.",
)
def _install(
    version: str | None,
    path: Path,
    url: str | None,
    force_install: bool,
    nightly: bool,
    debug: bool,
    skip_cross_build_packages: bool,
) -> None:
    """Install cross-build environment.

    The installed environment is the same as the one that would result from
    `PYODIDE_PACKAGES='scipy' make` except that it is much faster.
    The goal is to enable out-of-tree builds for binary packages that depend
    on numpy or scipy.

    \b
    Arguments:
        VERSION: version of cross-build environment to install (optional)
    """
    manager = CrossBuildEnvManager(path)

    if url:
        manager.install(url=url, force_install=force_install)
    elif nightly or debug:
        nightly_url = (
            NIGHTLY_DEBUG_CROSS_BUILD_ENV_METADATA_URL
            if debug
            else NIGHTLY_CROSS_BUILD_ENV_METADATA_URL
        )
        metadata = load_cross_build_env_metadata(nightly_url)
        if version:
            release = metadata.get_release(version)
        else:
            releases = list(metadata.releases.values())
            if not releases:
                click.echo(f"No {'debug ' if debug else ''}nightly releases found.")
                raise SystemExit(1)
            release = releases[0]  # sorted newest-first
        manager.install(url=release.url, force_install=force_install)
    else:
        manager.install(version=version, force_install=force_install)

    click.echo(f"Pyodide cross-build environment installed at {path.resolve()}")


@app.command("version")
@click.option(
    "--path",
    type=click.Path(path_type=Path),
    default=DEFAULT_PATH,
    help="path to cross-build environment directory.",
)
def _version(path: Path) -> None:
    """Print current version of cross-build environment."""
    check_xbuildenv_root(path)
    manager = CrossBuildEnvManager(path)
    version = manager.current_version
    if not version:
        click.echo("No version selected")
        raise SystemExit(1)
    else:
        click.echo(version)


@app.command("versions")
@click.option(
    "--path",
    type=click.Path(path_type=Path),
    default=DEFAULT_PATH,
    help="path to cross-build environment directory.",
)
def _versions(path: Path) -> None:
    """Print all installed versions of cross-build environment."""
    check_xbuildenv_root(path)
    manager = CrossBuildEnvManager(path)
    versions = manager.list_versions()
    current_version = manager.current_version

    for version in versions:
        if version == current_version:
            click.echo(f"* {version}")
        else:
            click.echo(f"  {version}")


@app.command("uninstall")
@click.argument("version", default=None, required=False)
@click.option(
    "--path",
    type=click.Path(path_type=Path),
    default=DEFAULT_PATH,
    help="path to cross-build environment directory.",
)
def _uninstall(version: str | None, path: Path) -> None:
    """Uninstall cross-build environment.

    \b
    Arguments:
        VERSION: version of cross-build environment to uninstall (optional)
    """
    check_xbuildenv_root(path)
    manager = CrossBuildEnvManager(path)
    v = manager.uninstall_version(version)
    click.echo(f"Pyodide cross-build environment {v} uninstalled")


@app.command("use")
@click.argument("version")
@click.option(
    "--path",
    type=click.Path(path_type=Path),
    default=DEFAULT_PATH,
    help="path to cross-build environment directory.",
)
def _use(version: str, path: Path) -> None:
    """Select a version of cross-build environment to use.

    \b
    Arguments:
        VERSION: version of cross-build environment to use (required)
    """
    check_xbuildenv_root(path)
    manager = CrossBuildEnvManager(path)
    manager.use_version(version)
    click.echo(f"Pyodide cross-build environment {version} is now in use")


@app.command("search")
@click.option(
    "--metadata",
    "metadata_path",
    default=None,
    help=(
        "path to cross-build environment metadata file. It can be a URL or a local file. "
        "If not given, the default metadata file is used."
    ),
)
@click.option(
    "--all",
    "-a",
    "show_all",
    is_flag=True,
    default=False,
    help="search all versions, without filtering out incompatible ones.",
)
@click.option(
    "--nightly",
    is_flag=True,
    default=False,
    help="include nightly releases alongside stable ones.",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="include nightly debug releases alongside stable ones.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="output results in JSON format.",
)
def _search(
    metadata_path: str | None,
    show_all: bool,
    nightly: bool,
    debug: bool,
    json_output: bool,
) -> None:
    """Search for available versions of cross-build environment."""

    # TODO: cache the metadata file somewhere to avoid downloading it every time

    local = local_versions()

    def _compat_kwargs() -> dict:
        if show_all:
            return {}
        return {
            "python_version": local["python"],
            "pyodide_build_version": local["pyodide-build"],
        }

    def _make_view(release, source: str = "stable") -> MetadataView:
        return MetadataView(
            version=release.version,
            python=release.python_version,
            emscripten=release.emscripten_version,
            pyodide_build={
                "min": release.min_pyodide_build_version,
                "max": release.max_pyodide_build_version,
            },
            published_at=release.published_at,
            source=source,
            compatible=release.is_compatible(
                python_version=local["python"],
                pyodide_build_version=local["pyodide-build"],
            ),
        )

    # Stable releases (always included)
    stable_metadata = load_cross_build_env_metadata(
        metadata_path or cross_build_env_metadata_url()
    )
    views = [
        _make_view(r, "stable")
        for r in stable_metadata.list_compatible_releases(**_compat_kwargs())
    ]

    # Nightly and/or debug releases (additive)
    extra_sources = []
    if nightly:
        extra_sources.append(("nightly", NIGHTLY_CROSS_BUILD_ENV_METADATA_URL))
    if debug:
        extra_sources.append(
            ("nightly-debug", NIGHTLY_DEBUG_CROSS_BUILD_ENV_METADATA_URL)
        )
    for source, url in extra_sources:
        nightly_metadata = load_cross_build_env_metadata(url)
        views += [
            _make_view(r, source)
            for r in nightly_metadata.releases.values()
            if show_all or r.is_compatible(**_compat_kwargs())
        ]

    if not views:
        click.echo(
            "No compatible cross-build environment found for your system. Try using --all to see all versions."
        )
        raise SystemExit(1)

    show_source = nightly or debug
    if json_output:
        print(MetadataView.to_json(views, show_source=show_source))
    else:
        print(MetadataView.to_table(views, show_source=show_source))


@app.command("install-emscripten")
@click.option(
    "--version",
    default=None,
    help="Emscripten version corresponding to the target Pyodide version",
)
@click.option(
    "--path",
    type=click.Path(path_type=Path),
    default=DEFAULT_PATH,
    help="Pyodide cross-env path",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="force reinstallation even if the same version is already installed.",
)
def _install_emscripten(
    version: str | None,
    path: Path,
    force: bool,
) -> None:
    """Install Emscripten SDK into the cross-build environment.

    This command clones the emsdk repository, installs and activates the specified
    Emscripten version, and applies Pyodide-specific patches.

    If the requested version is already installed, the command is a no-op unless
    --force is passed.
    """
    check_xbuildenv_root(path)
    manager = CrossBuildEnvManager(path)

    if version is None:
        version = get_build_flag("PYODIDE_EMSCRIPTEN_VERSION")

    print("Installing emsdk...")

    emsdk_dir = manager.install_emscripten(version, force=force)

    print("Installing emsdk complete.")
    print(f"Use `source {emsdk_dir}/emsdk_env.sh` to set up the environment.")
