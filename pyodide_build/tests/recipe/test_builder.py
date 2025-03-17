import shutil
import subprocess
import time
from pathlib import Path
from typing import Self

import pydantic
import pytest

from pyodide_build import common
from pyodide_build.build_env import BuildArgs, get_build_flag
from pyodide_build.recipe import builder as _builder
from pyodide_build.recipe.builder import (
    RecipeBuilder,
    RecipeBuilderPackage,
    RecipeBuilderSharedLibrary,
    RecipeBuilderStaticLibrary,
    _load_recipe,
)
from pyodide_build.recipe.spec import _SourceSpec

RECIPE_DIR = Path(__file__).parent / "_test_recipes"
WHEEL_DIR = Path(__file__).parent.parent / "_test_wheels"


@pytest.fixture
def tmp_builder(tmp_path):
    builder = RecipeBuilder.get_builder(
        recipe=RECIPE_DIR / "pkg_1",
        build_args=BuildArgs(),
        build_dir=tmp_path,
        force_rebuild=False,
        continue_=False,
    )

    yield builder


def test_constructor(tmp_path):
    builder = RecipeBuilder.get_builder(
        recipe=RECIPE_DIR / "beautifulsoup4",
        build_args=BuildArgs(),
        build_dir=tmp_path / "beautifulsoup4" / "build",
        force_rebuild=False,
        continue_=False,
    )

    assert builder.name == "beautifulsoup4"
    assert builder.version == "4.13.3"
    assert builder.fullname == "beautifulsoup4-4.13.3"

    assert builder.pkg_root == RECIPE_DIR / "beautifulsoup4"
    assert builder.build_dir == tmp_path / "beautifulsoup4" / "build"
    assert (
        builder.src_extract_dir
        == tmp_path / "beautifulsoup4" / "build" / "beautifulsoup4-4.13.3"
    )
    assert (
        builder.src_dist_dir
        == tmp_path / "beautifulsoup4" / "build" / "beautifulsoup4-4.13.3" / "dist"
    )
    assert builder.dist_dir == RECIPE_DIR / "beautifulsoup4" / "dist"
    assert builder.library_install_prefix == tmp_path / ".libs"


def test_get_builder(tmp_path):
    builder = RecipeBuilder.get_builder(
        recipe=RECIPE_DIR / "pkg_1",
        build_args=BuildArgs(),
        build_dir=tmp_path,
        force_rebuild=False,
        continue_=False,
    )

    assert isinstance(builder, RecipeBuilder)
    assert isinstance(builder, RecipeBuilderPackage)

    builder = RecipeBuilder.get_builder(
        recipe=RECIPE_DIR / "libtest",
        build_args=BuildArgs(),
        build_dir=tmp_path,
        force_rebuild=False,
        continue_=False,
    )

    assert isinstance(builder, RecipeBuilder)
    assert isinstance(builder, RecipeBuilderStaticLibrary)

    builder = RecipeBuilder.get_builder(
        recipe=RECIPE_DIR / "libtest_shared",
        build_args=BuildArgs(),
        build_dir=tmp_path,
        force_rebuild=False,
        continue_=False,
    )

    assert isinstance(builder, RecipeBuilder)
    assert isinstance(builder, RecipeBuilderSharedLibrary)


def test_load_recipe():
    root, recipe = _load_recipe(RECIPE_DIR / "pkg_1")
    assert root == RECIPE_DIR / "pkg_1"
    assert recipe.package.name == "pkg_1"

    root, recipe = _load_recipe(RECIPE_DIR / "pkg_1" / "meta.yaml")
    assert root == RECIPE_DIR / "pkg_1"
    assert recipe.package.name == "pkg_1"


def test_prepare_source(monkeypatch, tmp_path, dummy_xbuildenv):
    class subprocess_result:
        returncode = 0
        stdout = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess_result)
    monkeypatch.setattr(_builder, "check_checksum", lambda *args, **kwargs: True)
    monkeypatch.setattr(shutil, "unpack_archive", lambda *args, **kwargs: True)
    monkeypatch.setattr(shutil, "move", lambda *args, **kwargs: True)

    test_pkgs = [
        RECIPE_DIR / "packaging/meta.yaml",
        # RECIPE_DIR / "micropip/meta.yaml",
    ]

    for pkg in test_pkgs:
        builder = RecipeBuilder.get_builder(
            recipe=pkg,
            build_args=BuildArgs(),
            build_dir=tmp_path / "build",
        )
        builder._prepare_source()
        assert builder.src_extract_dir.is_dir()


def test_check_executables(tmp_path, monkeypatch):
    builder = RecipeBuilder.get_builder(
        recipe=RECIPE_DIR / "pkg_test_executable",
        build_args=BuildArgs(),
        build_dir=tmp_path,
    )

    monkeypatch.setattr(
        common, "find_missing_executables", lambda executables: ["echo"]
    )
    with pytest.raises(
        RuntimeError, match="The following executables are required to build"
    ):
        builder._check_executables()


def test_get_helper_vars(tmp_path):
    builder = RecipeBuilder.get_builder(
        recipe=RECIPE_DIR / "pkg_1",
        build_args=BuildArgs(),
        build_dir=tmp_path / "pkg_1" / "build",
    )

    helper_vars = builder._get_helper_vars()

    assert helper_vars["PKGDIR"] == str(RECIPE_DIR / "pkg_1")
    assert helper_vars["PKG_VERSION"] == "1.0.0"
    assert helper_vars["PKG_BUILD_DIR"] == str(
        tmp_path / "pkg_1" / "build" / "pkg_1-1.0.0"
    )
    assert helper_vars["DISTDIR"] == str(
        tmp_path / "pkg_1" / "build" / "pkg_1-1.0.0" / "dist"
    )
    assert helper_vars["WASM_LIBRARY_DIR"] == str(tmp_path / ".libs")
    assert helper_vars["EM_PKG_CONFIG_PATH"] == str(
        tmp_path / ".libs" / "lib" / "pkgconfig"
    )
    assert helper_vars["PKG_CONFIG_LIBDIR"] == str(
        tmp_path / ".libs" / "lib" / "pkgconfig"
    )


def test_unvendor_tests(tmpdir):
    def touch(path: Path) -> None:
        if path.is_dir():
            raise ValueError("Only files, not folders are supported")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    def rlist(input_dir):
        """Recursively list files in input_dir"""
        paths = sorted(input_dir.rglob("*"))
        res = []

        for el in paths:
            if el.is_file():
                res.append(str(el.relative_to(input_dir)))
        return res

    install_prefix = Path(str(tmpdir / "install"))
    test_install_prefix = Path(str(tmpdir / "install-tests"))

    # create the example package
    touch(install_prefix / "ex1" / "base.py")
    touch(install_prefix / "ex1" / "conftest.py")
    touch(install_prefix / "ex1" / "test_base.py")
    touch(install_prefix / "ex1" / "tests" / "data.csv")
    touch(install_prefix / "ex1" / "tests" / "test_a.py")

    n_moved = _builder.unvendor_tests(install_prefix, test_install_prefix, [])

    assert rlist(install_prefix) == ["ex1/base.py"]
    assert rlist(test_install_prefix) == [
        "ex1/conftest.py",
        "ex1/test_base.py",
        "ex1/tests/data.csv",
        "ex1/tests/test_a.py",
    ]

    # One test folder and two test file
    assert n_moved == 3


def test_create_constraints_file_no_override(tmp_path, dummy_xbuildenv):
    builder = RecipeBuilder.get_builder(
        recipe=RECIPE_DIR
        / "pkg_test_executable",  # constraints not set, so no override
        build_args=BuildArgs(),
        build_dir=tmp_path,
    )

    path = builder._create_constraints_file()
    assert path == get_build_flag("PIP_CONSTRAINT")


def test_create_constraints_file_override(tmp_path, dummy_xbuildenv):
    builder = RecipeBuilder.get_builder(
        recipe=RECIPE_DIR / "pkg_test_constraint",
        build_args=BuildArgs(),
        build_dir=tmp_path,
    )

    paths = builder._create_constraints_file()
    assert paths == get_build_flag("PIP_CONSTRAINT") + " " + str(
        tmp_path / "constraints.txt"
    )

    data = Path(paths.split()[-1]).read_text().strip().split("\n")
    assert data[-3:] == ["numpy < 2.0", "pytest == 7.0", "setuptools < 75"], data


class MockSourceSpec(_SourceSpec):
    @pydantic.model_validator(mode="after")
    def _check_patches_extra(self) -> Self:
        return self


@pytest.mark.parametrize("is_wheel", [False, True])
def test_needs_rebuild(tmpdir, is_wheel):
    pkg_root = Path(tmpdir)
    buildpath = pkg_root / "build"
    meta_yaml = pkg_root / "meta.yaml"
    version = "12"
    if is_wheel:
        dist_dir = pkg_root / "dist"
        dist_dir.mkdir()
        # Build of current version with wrong abi
        (dist_dir / "regex-12-cp311-cp311-pyodide_2024_0_wasm32.whl").touch()
        # Build of old version with current abi
        (dist_dir / "regex-11-cp312-cp312-pyodide_2024_0_wasm32.whl").touch()
        # the version we're trying to build
        packaged = dist_dir / "regex-12-cp312-cp312-pyodide_2024_0_wasm32.whl"
    else:
        packaged = buildpath / ".packaged"

    patch_file = pkg_root / "patch"
    extra_file = pkg_root / "extra"
    src_path = pkg_root / "src"
    src_path_file = src_path / "file"

    source_metadata = MockSourceSpec(
        patches=[
            str(patch_file),
        ],
        extras=[
            (str(extra_file), ""),
        ],
        path=str(src_path),
    )

    buildpath.mkdir()
    meta_yaml.touch()
    patch_file.touch()
    extra_file.touch()
    src_path.mkdir()
    src_path_file.touch()

    # No .packaged file, rebuild
    assert _builder.needs_rebuild(
        pkg_root, buildpath, source_metadata, is_wheel, version
    )

    # .packaged file exists, no rebuild
    packaged.touch()
    assert not _builder.needs_rebuild(
        pkg_root, buildpath, source_metadata, is_wheel, version
    )

    # newer meta.yaml file, rebuild
    packaged.touch()
    time.sleep(0.01)
    meta_yaml.touch()
    assert _builder.needs_rebuild(
        pkg_root, buildpath, source_metadata, is_wheel, version
    )

    # newer patch file, rebuild
    packaged.touch()
    time.sleep(0.01)
    patch_file.touch()
    assert _builder.needs_rebuild(
        pkg_root, buildpath, source_metadata, is_wheel, version
    )

    # newer extra file, rebuild
    packaged.touch()
    time.sleep(0.01)
    extra_file.touch()
    assert _builder.needs_rebuild(
        pkg_root, buildpath, source_metadata, is_wheel, version
    )

    # newer source path, rebuild
    packaged.touch()
    time.sleep(0.01)
    src_path_file.touch()
    assert _builder.needs_rebuild(
        pkg_root, buildpath, source_metadata, is_wheel, version
    )

    # newer .packaged file, no rebuild
    packaged.touch()
    assert not _builder.needs_rebuild(
        pkg_root, buildpath, source_metadata, is_wheel, version
    )


def test_copy_sharedlib(tmp_path):
    wheel_file_name = "sharedlib_test_py-1.0-cp310-cp310-emscripten_3_1_21_wasm32.whl"
    wheel = WHEEL_DIR / "wheel" / wheel_file_name
    libdir = WHEEL_DIR / "lib"

    wheel_copy = tmp_path / wheel_file_name
    shutil.copy(wheel, wheel_copy)

    common.unpack_wheel(wheel_copy)
    name, ver, _ = wheel.name.split("-", 2)
    wheel_dir_name = f"{name}-{ver}"
    wheel_dir = tmp_path / wheel_dir_name

    dep_map = _builder.copy_sharedlibs(wheel_copy, wheel_dir, libdir)

    deps = ("sharedlib-test.so", "sharedlib-test-dep.so", "sharedlib-test-dep2.so")
    for dep in deps:
        assert dep in dep_map


def test_extract_tarballname():
    url = "https://www.test.com/ball.tar.gz"
    headers = [
        {},
        {"Content-Disposition": "inline"},
        {"Content-Disposition": "attachment"},
        {"Content-Disposition": 'attachment; filename="ball 2.tar.gz"'},
        {"Content-Disposition": "attachment; filename*=UTF-8''ball%203.tar.gz"},
    ]
    tarballnames = [
        "ball.tar.gz",
        "ball.tar.gz",
        "ball.tar.gz",
        "ball 2.tar.gz",
        "ball 3.tar.gz",
    ]

    for header, tarballname in zip(headers, tarballnames, strict=True):
        assert _builder._extract_tarballname(url, header) == tarballname
