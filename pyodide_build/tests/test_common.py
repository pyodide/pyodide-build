import os
import sys
import zipfile
from pathlib import Path

import platformdirs
import pytest

from pyodide_build.common import (
    check_wasm_magic_number,
    default_xbuildenv_path,
    environment_substitute_args,
    extract_wheel_metadata_file,
    find_missing_executables,
    make_zip_archive,
    parse_top_level_import_name,
    repack_zip_archive,
    xbuildenv_dirname,
)


@pytest.mark.parametrize(
    "pkg",
    [
        {
            "name": "pkg_singlefile-1.0.0-py3-none-any.whl",
            "file": "singlefile.py",
            "content": "pass\n",
            "top_level": ["singlefile"],
        },
        {
            "name": "pkg_flit-1.0.0-py3-none-any.whl",
            "file": "pkg_flit/__init__.py",
            "content": "pass\n",
            "top_level": ["pkg_flit"],
        },
    ],
)
def test_parse_top_level_import_name(pkg, tmp_path):
    with zipfile.ZipFile(tmp_path / pkg["name"], "w") as whlzip:
        whlzip.writestr(pkg["file"], data=pkg["content"])

    top_level = parse_top_level_import_name(tmp_path / pkg["name"])
    assert top_level == pkg["top_level"]


def test_find_missing_executables(monkeypatch):
    import shutil

    pkgs = ["a", "b", "c"]
    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda exe: None)
        assert pkgs == find_missing_executables(pkgs)

    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda exe: "/bin")
        assert [] == find_missing_executables(pkgs)


def test_environment_var_substitution(monkeypatch):
    monkeypatch.setenv("PYODIDE_BASE", "pyodide_build_dir")
    monkeypatch.setenv("BOB", "Robert Mc Roberts")
    monkeypatch.setenv("FRED", "Frederick F. Freddertson Esq.")
    monkeypatch.setenv("JIM", "James Ignatius Morrison:Jimmy")
    args = environment_substitute_args(
        {
            "ldflags": '"-l$(PYODIDE_BASE)"',
            "cxxflags": "$(BOB)",
            "cflags": "$(FRED)",
        }
    )
    assert (
        args["cflags"] == "Frederick F. Freddertson Esq."
        and args["cxxflags"] == "Robert Mc Roberts"
        and args["ldflags"] == '"-lpyodide_build_dir"'
    )


@pytest.mark.parametrize(
    "compression_level, expected_compression_type",
    [(6, zipfile.ZIP_DEFLATED), (0, zipfile.ZIP_STORED)],
)
def test_make_zip_archive(tmp_path, compression_level, expected_compression_type):
    input_dir = tmp_path / "a"
    input_dir.mkdir()
    (input_dir / "b.txt").write_text(".")
    (input_dir / "c").mkdir()
    (input_dir / "c/d").write_bytes(b"")

    output_dir = tmp_path / "output.zip"

    make_zip_archive(output_dir, input_dir, compression_level=compression_level)

    with zipfile.ZipFile(output_dir) as fh:
        assert set(fh.namelist()) == {"b.txt", "c/", "c/d"}
        assert fh.read("b.txt") == b"."
        assert fh.getinfo("b.txt").compress_type == expected_compression_type


@pytest.mark.parametrize(
    "compression_level, expected_compression_type, expected_size",
    [(6, zipfile.ZIP_DEFLATED, 220), (0, zipfile.ZIP_STORED, 1207)],
)
def test_repack_zip_archive(
    tmp_path, compression_level, expected_compression_type, expected_size
):
    input_path = tmp_path / "archive.zip"

    data = "a" * 1000

    with zipfile.ZipFile(
        input_path, "w", compression=zipfile.ZIP_BZIP2, compresslevel=3
    ) as fh:
        fh.writestr("a/b.txt", data)
        fh.writestr("a/b/c.txt", "d")

    repack_zip_archive(input_path, compression_level=compression_level)

    with zipfile.ZipFile(input_path) as fh:
        assert fh.namelist() == ["a/b.txt", "a/b/c.txt"]
        assert fh.getinfo("a/b.txt").compress_type == expected_compression_type
    assert input_path.stat().st_size == expected_size


def test_extract_wheel_metadata_file(tmp_path):
    # Test extraction if metadata exists

    input_path = tmp_path / "pkg-0.1-abc.whl"
    metadata_path = "pkg-0.1.dist-info/METADATA"
    metadata_str = "This is METADATA"

    with zipfile.ZipFile(input_path, "w") as fh:
        fh.writestr(metadata_path, metadata_str)

    output_path = tmp_path / f"{input_path.name}.metadata"

    extract_wheel_metadata_file(input_path, output_path)
    assert output_path.read_text() == metadata_str

    # Test extraction if metadata is missing

    input_path_empty = tmp_path / "pkg-0.2-abc.whl"

    with zipfile.ZipFile(input_path_empty, "w") as fh:
        pass

    output_path_empty = tmp_path / f"{input_path_empty.name}.metadata"

    with pytest.raises(RuntimeError):
        extract_wheel_metadata_file(input_path_empty, output_path_empty)


def test_check_wasm_magic_number(tmp_path):
    wasm_magic_number = b"\x00asm\x01\x00\x00\x00\x00\x11"
    not_wasm_magic_number = b"\x7fELF\x02\x01\x01\x00\x00\x00"

    (tmp_path / "goodfile.so").write_bytes(wasm_magic_number)
    assert check_wasm_magic_number(tmp_path / "goodfile.so") is True

    (tmp_path / "badfile.so").write_bytes(not_wasm_magic_number)
    assert check_wasm_magic_number(tmp_path / "badfile.so") is False


class MockConfigManager:
    def __init__(self, mock_config=None):
        self._config = mock_config or {}

    @property
    def config(self):
        return self._config


def test_default_xbuildenv_path_default(monkeypatch):
    mock_config_manager = MockConfigManager({})
    monkeypatch.setattr(
        "pyodide_build.config.ConfigManager", lambda: mock_config_manager
    )

    dirname = xbuildenv_dirname()
    expected_path = Path(platformdirs.user_cache_dir()) / dirname

    assert default_xbuildenv_path() == expected_path


def test_default_xbuildenv_path_env_var_takes_precedence(
    tmp_path, reset_cache, monkeypatch
):
    custom_path = tmp_path / "custom" / "path"

    monkeypatch.setenv("PYODIDE_XBUILDENV_PATH", str(custom_path))

    assert default_xbuildenv_path() == custom_path


def test_default_xbuildenv_path_from_config(tmp_path, monkeypatch):
    """Test that the path is correctly read from the ConfigManager."""

    config_path = tmp_path / "config_path"
    mock_config_manager = MockConfigManager({"xbuildenv_path": str(config_path)})
    monkeypatch.setattr(
        "pyodide_build.config.ConfigManager", lambda: mock_config_manager
    )

    assert default_xbuildenv_path() == config_path


def test_default_xbuildenv_path_relative_config(reset_cache, monkeypatch):
    relative_path = "../relative/path/to/somewhere"

    mock_config_manager = MockConfigManager({"xbuildenv_path": relative_path})
    monkeypatch.setattr(
        "pyodide_build.config.ConfigManager", lambda: mock_config_manager
    )

    expected_path = Path.cwd() / relative_path

    assert default_xbuildenv_path() == expected_path


@pytest.mark.skipif(sys.platform != "linux", reason="Test only runs on Linux")
def test_default_xbuildenv_path_xdg_cache_home(tmp_path, reset_cache, monkeypatch):
    """Test XDG_CACHE_HOME on Linux."""

    os.environ.pop("XDG_CACHE_HOME", None)

    mock_config_manager = MockConfigManager({})
    monkeypatch.setattr(
        "pyodide_build.config.ConfigManager", lambda: mock_config_manager
    )

    dirname = xbuildenv_dirname()

    assert default_xbuildenv_path() == Path(platformdirs.user_cache_dir()) / dirname

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert default_xbuildenv_path() == tmp_path / dirname

    not_writeable_path = tmp_path / "not_writeable"
    not_writeable_path.mkdir()
    not_writeable_path.chmod(0o444)

    monkeypatch.setenv("XDG_CACHE_HOME", str(not_writeable_path))

    assert default_xbuildenv_path() == Path.cwd() / dirname


def test_config_with_pyproject_toml(tmp_path, reset_cache, monkeypatch):
    """Test that xbuildenv_path from pyproject.toml is properly used."""
    # Create a temporary pyproject.toml file
    pyproject_dir = tmp_path / "project"
    pyproject_dir.mkdir()
    pyproject_path = pyproject_dir / "pyproject.toml"

    xbuildenv_path = pyproject_dir / "custom-xbuildenv-from-config"

    pyproject_content = f"""
[tool.pyodide.build]
xbuildenv_path = "{xbuildenv_path}"
"""
    pyproject_path.write_text(pyproject_content)

    mock_config_manager = MockConfigManager({"xbuildenv_path": str(xbuildenv_path)})
    monkeypatch.setattr(
        "pyodide_build.config.ConfigManager", lambda: mock_config_manager
    )

    path = default_xbuildenv_path()
    assert path == xbuildenv_path


def test_config_full_precedence(tmp_path, reset_cache, monkeypatch):
    """Test the full precedence order: env var > pyproject.toml > platformdirs."""
    pyproject_dir = tmp_path / "project"
    pyproject_dir.mkdir()

    env_var_path = tmp_path / "env-var-path"
    pyproject_path_value = pyproject_dir / "pyproject-path"

    mock_config_manager = MockConfigManager(
        {"xbuildenv_path": str(pyproject_path_value)}
    )
    monkeypatch.setattr(
        "pyodide_build.config.ConfigManager", lambda: mock_config_manager
    )

    # 1. test using pyodide config when no env var is set
    path = default_xbuildenv_path()
    assert path == pyproject_path_value

    # 2. set environment variable and verify it takes precedence
    monkeypatch.setenv("PYODIDE_XBUILDENV_PATH", str(env_var_path))
    reset_cache()

    path = default_xbuildenv_path()
    assert path == env_var_path
