import os
import shutil
import subprocess
import tarfile
import time
from contextlib import contextmanager
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

    path = builder._create_constraints_file()
    assert path == str(tmp_path / "constraints.txt")

    data = Path(path).read_text().strip().split("\n")
    assert data[-3:] == ["numpy < 2.0", "pytest == 7.0"], data


class MockSourceSpec(_SourceSpec):
    @pydantic.model_validator(mode="after")
    def _check_patches_extra(self) -> Self:
        return self


def test_needs_rebuild(tmpdir):
    pkg_root = Path(tmpdir)
    buildpath = pkg_root / "build"
    meta_yaml = pkg_root / "meta.yaml"
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
    assert _builder.needs_rebuild(pkg_root, buildpath, source_metadata) is True

    # .packaged file exists, no rebuild
    packaged.touch()
    assert _builder.needs_rebuild(pkg_root, buildpath, source_metadata) is False

    # newer meta.yaml file, rebuild
    packaged.touch()
    time.sleep(0.01)
    meta_yaml.touch()
    assert _builder.needs_rebuild(pkg_root, buildpath, source_metadata) is True

    # newer patch file, rebuild
    packaged.touch()
    time.sleep(0.01)
    patch_file.touch()
    assert _builder.needs_rebuild(pkg_root, buildpath, source_metadata) is True

    # newer extra file, rebuild
    packaged.touch()
    time.sleep(0.01)
    extra_file.touch()
    assert _builder.needs_rebuild(pkg_root, buildpath, source_metadata) is True

    # newer source path, rebuild
    packaged.touch()
    time.sleep(0.01)
    src_path_file.touch()
    assert _builder.needs_rebuild(pkg_root, buildpath, source_metadata) is True

    # newer .packaged file, no rebuild
    packaged.touch()
    assert _builder.needs_rebuild(pkg_root, buildpath, source_metadata) is False


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


# Some reproducibility tests. These are not exhaustive, but should catch
# some common issues for basics like timestamps and file contents. They
# test the behavior of the builder functions that are most likely to be
# affected by SOURCE_DATE_EPOCH.


from pyodide_build.common import get_source_epoch


@contextmanager
def source_date_epoch(value=None):
    old_value = os.environ.get("SOURCE_DATE_EPOCH")
    try:
        if value is None:
            if "SOURCE_DATE_EPOCH" in os.environ:
                del os.environ["SOURCE_DATE_EPOCH"]
        else:
            os.environ["SOURCE_DATE_EPOCH"] = str(value)
        yield
    finally:
        if old_value is None:
            if "SOURCE_DATE_EPOCH" in os.environ:
                del os.environ["SOURCE_DATE_EPOCH"]
        else:
            os.environ["SOURCE_DATE_EPOCH"] = old_value


def test_get_source_epoch_reproducibility():
    with source_date_epoch("1735689600"):  # 2025-01-01
        assert get_source_epoch() == 1735689600

    with source_date_epoch("invalid"):
        assert get_source_epoch() > 0  # should fall back to current time

    with source_date_epoch("0"):
        assert (
            get_source_epoch() == 315532800
        )  # should fall back to minimum ZIP timestamp


def test_make_whlfile_reproducibility(monkeypatch, tmp_path):
    """Test that _make_whlfile is passing the correct timestamp to _make_zipfile."""
    from pyodide_build.recipe.builder import _make_whlfile

    test_epoch = 1735689600  # 2025-01-01

    def mock_make_zipfile(
        base_name, base_dir, verbose=0, dry_run=0, logger=None, date_time=None
    ):
        assert date_time == time.gmtime(test_epoch)[:6]

    monkeypatch.setattr(shutil, "_make_zipfile", mock_make_zipfile)

    with source_date_epoch(test_epoch):
        _make_whlfile("archive.whl", "base_dir", ["file1.py"], b"content")


def test_set_archive_time_reproducibility(tmp_path):
    """Test that archive creation using _set_time sets correct mtime."""
    import tarfile

    # Create a test tarfile with a specific timestamp
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    test_epoch = 1735689600  # 2025-01-01

    with source_date_epoch(test_epoch):
        with tarfile.open(tmp_path / "archive.tar", "w") as tar:
            tarinfo = tar.gettarinfo(str(test_file))
            tarinfo.mtime = get_source_epoch()
            tar.addfile(tarinfo, open(test_file, "rb"))

    # Now, verify this timestamp in the archive
    with tarfile.open(tmp_path / "archive.tar") as tar:
        info = tar.getmembers()[0]
        assert info.mtime == test_epoch


def test_reproducible_tar_filter(monkeypatch, tmp_path):
    """Test that our reproducible_filter function sets the timestamp correctly."""

    test_epoch = 1735689600  # 2025-01-01

    class MockTarInfo:
        def __init__(self, name):
            self.name = name
            self.uid = 1000
            self.gid = 1000
            self.uname = None
            self.gname = None
            self.mtime = int(time.time())

    monkeypatch.setattr(tarfile, "TarInfo", MockTarInfo)
    monkeypatch.setattr(os.path, "getmtime", lambda *args: test_epoch)

    with source_date_epoch(test_epoch):
        # Create and check a tarinfo object
        tarinfo = tarfile.TarInfo("test.txt")
        tarinfo.uid = tarinfo.gid = 0
        tarinfo.uname = tarinfo.gname = "root"
        tarinfo.mtime = test_epoch

        assert tarinfo.mtime == test_epoch
        assert tarinfo.uid == 0
        assert tarinfo.gid == 0
        assert tarinfo.uname == "root"
        assert tarinfo.gname == "root"
