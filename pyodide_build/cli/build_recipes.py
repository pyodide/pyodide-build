import dataclasses
import sys
from pathlib import Path

import typer

from pyodide_build import build_env
from pyodide_build.build_env import BuildArgs, init_environment
from pyodide_build.common import get_num_cores
from pyodide_build.logger import logger
from pyodide_build.recipe import graph_builder, loader
from pyodide_build.recipe.builder import RecipeBuilder

# Typer application for `pyodide build-recipes`


@dataclasses.dataclass(eq=False, order=False, kw_only=True)
class Args:
    recipe_dir: Path
    build_dir: Path
    install_dir: Path
    build_args: BuildArgs
    skip_rust_setup: bool
    force_rebuild: bool
    n_jobs: int
    clean: bool

    def __init__(
        self,
        *,
        recipe_dir: Path | str | None,
        build_dir: Path | str | None,
        install_dir: Path | str | None = None,
        build_args: BuildArgs,
        force_rebuild: bool,
        skip_rust_setup: bool = False,
        n_jobs: int | None = None,
        clean: bool = False,
    ):
        cwd = Path.cwd()
        root = build_env.search_pyodide_root(cwd) or cwd
        self.recipe_dir = (
            root / "packages" if not recipe_dir else Path(recipe_dir).resolve()
        )
        self.build_dir = self.recipe_dir if not build_dir else Path(build_dir).resolve()
        self.install_dir = (
            root / "dist" if not install_dir else Path(install_dir).resolve()
        )
        self.build_args = build_args
        self.force_rebuild = force_rebuild
        self.skip_rust_setup = skip_rust_setup
        self.n_jobs = n_jobs or get_num_cores()
        self.clean = clean
        if not self.recipe_dir.is_dir():
            raise FileNotFoundError(f"Recipe directory {self.recipe_dir} not found")


@dataclasses.dataclass(eq=False, order=False, kw_only=True)
class InstallOptions:
    compression_level: int
    metadata_files: bool


def build_recipes_no_deps(
    packages: list[str] = typer.Argument(
        ..., help="Packages to build, or ``*`` for all packages in recipe directory"
    ),
    recipe_dir: str = typer.Option(
        None,
        help="The directory containing the recipe of packages. "
        "If not specified, the default is ``./packages``",
    ),
    build_dir: str = typer.Option(
        None,
        envvar="PYODIDE_RECIPE_BUILD_DIR",
        help="The directory where build directories for packages are created. "
        "Default: recipe_dir.",
    ),
    cflags: str = typer.Option("", help="Extra compiling flags."),
    cxxflags: str = typer.Option("", help="Extra compiling flags."),
    ldflags: str = typer.Option("", help="Extra linking flags."),
    target_install_dir: str = typer.Option(
        "",
        help="The path to the target Python installation.",
    ),
    host_install_dir: str = typer.Option(
        "",
        help="Directory for installing built host packages.",
    ),
    force_rebuild: bool = typer.Option(
        False,
        help="Force rebuild of all packages regardless of whether they appear to have been updated",
    ),
    continue_: bool = typer.Option(
        False,
        "--continue",
        help="Continue a build from the middle. For debugging. Implies '--force-rebuild'",
    ),
    skip_rust_setup: bool = typer.Option(
        False,
        "--skip-rust-setup",
        help="Don't setup rust environment when building a rust package",
    ),
    clean: bool = typer.Option(
        False,
        help="Remove the build directory after a successful build of each package.",
    ),
) -> None:
    """Build packages using yaml recipes but don't try to resolve dependencies"""
    init_environment()

    if build_env.in_xbuildenv():
        build_env.check_emscripten_version()

    build_args = BuildArgs(
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir=target_install_dir,
        host_install_dir=host_install_dir,
    )
    build_args = graph_builder.set_default_build_args(build_args)
    args = Args(
        build_args=build_args,
        build_dir=build_dir,
        recipe_dir=recipe_dir,
        force_rebuild=force_rebuild,
        skip_rust_setup=skip_rust_setup,
        clean=clean,
    )

    return build_recipes_no_deps_impl(packages, args, continue_)


def _rust_setup(recipe_dir: Path, packages: list[str]) -> None:
    recipes = loader.load_recipes(recipe_dir, packages, False)
    if any(recipe.is_rust_package() for recipe in recipes.values()):
        graph_builder._ensure_rust_toolchain()


def build_recipes_no_deps_impl(
    packages: list[str], args: Args, continue_: bool
) -> None:
    # TODO: use multiprocessing?
    if not args.skip_rust_setup:
        _rust_setup(args.recipe_dir, packages)

    for package in packages:
        package_path = args.recipe_dir / package
        package_build_dir = args.build_dir / package / "build"
        builder = RecipeBuilder.get_builder(
            package_path,
            args.build_args,
            package_build_dir,
            args.force_rebuild,
            continue_,
        )
        builder.build()
        if args.clean:
            builder.clean(include_dist=False)


def build_recipes(
    packages: list[str] = typer.Argument(
        ..., help="Packages to build, or ``*`` for all packages in recipe directory"
    ),
    recipe_dir: str = typer.Option(
        None,
        help="The directory containing the recipe of packages. "
        "If not specified, the default is ``./packages``",
    ),
    build_dir: str = typer.Option(
        None,
        envvar="PYODIDE_RECIPE_BUILD_DIR",
        help="The directory where build directories for packages are created. "
        "Default: recipe_dir.",
    ),
    install: bool = typer.Option(
        False,
        help="If true, install the built packages into the install_dir. "
        "If false, build packages without installing.",
    ),
    install_dir: str = typer.Option(
        None,
        help="Path to install built packages and pyodide-lock.json. "
        "If not specified, the default is ``./dist``.",
    ),
    metadata_files: bool = typer.Option(
        False,
        help="If true, extract the METADATA file from the built wheels "
        "to a matching ``*.whl.metadata`` file. "
        "If false, no ``*.whl.metadata`` file is produced.",
    ),
    no_deps: bool = typer.Option(
        False, help="Removed, use `pyodide build-recipes-no-deps` instead."
    ),
    cflags: str = typer.Option(None, help="Extra compiling flags."),
    cxxflags: str = typer.Option(None, help="Extra compiling flags."),
    ldflags: str = typer.Option(None, help="Extra linking flags."),
    target_install_dir: str = typer.Option(
        "",
        help="The path to the target Python installation.",
    ),
    host_install_dir: str = typer.Option(
        "",
        help="Directory for installing built host packages.",
    ),
    log_dir: str = typer.Option(None, help="Directory to place log files"),
    force_rebuild: bool = typer.Option(
        False,
        help="Force rebuild of all packages regardless of whether they appear to have been updated",
    ),
    n_jobs: int = typer.Option(
        None,
        help="Number of packages to build in parallel  (default: # of cores in the system)",
    ),
    compression_level: int = typer.Option(
        6,
        envvar="PYODIDE_ZIP_COMPRESSION_LEVEL",
        help="Level of zip compression to apply when installing. 0 means no compression.",
    ),
    clean: bool = typer.Option(
        False,
        help="Remove the build directory after a successful build of each package.",
    ),
) -> None:
    if no_deps:
        logger.error(
            "--no-deps has been removed, use pyodide build-package-no-deps instead",
        )
        sys.exit(1)
    if metadata_files and not install:
        logger.warning(
            "WARNING: when --install is not set, the --metadata-files parameter is ignored",
        )

    install_options: InstallOptions | None = None
    if install:
        install_options = InstallOptions(
            metadata_files=metadata_files, compression_level=compression_level
        )

    init_environment()

    if build_env.in_xbuildenv():
        build_env.check_emscripten_version()

    build_args = BuildArgs(
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir=target_install_dir,
        host_install_dir=host_install_dir,
    )
    build_args = graph_builder.set_default_build_args(build_args)
    args = Args(
        build_args=build_args,
        build_dir=build_dir,
        install_dir=install_dir,
        recipe_dir=recipe_dir,
        force_rebuild=force_rebuild,
        n_jobs=n_jobs,
        clean=clean,
    )
    log_dir_ = Path(log_dir).resolve() if log_dir else None
    build_recipes_impl(packages, args, log_dir_, install_options)


def build_recipes_impl(
    packages: list[str],
    args: Args,
    log_dir: Path | None,
    install_options: InstallOptions | None,
) -> None:
    if len(packages) == 1 and "," in packages[0]:
        # Handle packages passed with old comma separated syntax.
        # This is to support `PYODIDE_PACKAGES="pkg1,pkg2,..." make` syntax.
        targets = packages[0].replace(" ", "")
    else:
        targets = ",".join(packages)

    pkg_map = graph_builder.build_packages(
        args.recipe_dir,
        targets=targets,
        build_args=args.build_args,
        build_dir=args.build_dir,
        n_jobs=args.n_jobs,
        force_rebuild=args.force_rebuild,
        clean=args.clean,
    )
    if log_dir:
        graph_builder.copy_logs(pkg_map, log_dir)

    if install_options:
        graph_builder.install_packages(
            pkg_map,
            args.install_dir,
            compression_level=install_options.compression_level,
            metadata_files=install_options.metadata_files,
        )
