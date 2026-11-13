import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pyodide_build._python_pkgconfig import ensure_python_pkgconfig_files

SYSCONFIG_NAME = "_sysconfigdata__emscripten_wasm32-emscripten"

PYODIDE_PYTHON_3_14_PC = """\
# See: man pkg-config
prefix=${pcfiledir}/../..
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include

Name: Python
Description: Build a C extension for Python
Requires:
Version: 3.14
Libs.private: -ldl  -lpthread
Libs: -L${libdir}
Cflags: -I${includedir}/python3.14
"""

PYODIDE_PYTHON_3_14_EMBED_PC = """\
# See: man pkg-config
prefix=${pcfiledir}/../..
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include

Name: Python
Description: Embed Python into an application
Requires:
Version: 3.14
Libs.private: -ldl  -lpthread
Libs: -L${libdir} -lpython3.14
Cflags: -I${includedir}/python3.14
"""


def make_target_install_dir(
    tmp_path: Path,
    *,
    version: str = "3.14",
    abiflags: str = "",
    sysconfigdata: str | None = None,
) -> Path:
    """
    Lay out the parts of a target Python installation that a cross-build
    environment ships, with a sysconfigdata module in the format Pyodide uses.
    """
    target_install_dir = tmp_path / "cpython" / "installs" / f"python-{version}.2"
    (target_install_dir / "include" / f"python{version}{abiflags}").mkdir(parents=True)

    if sysconfigdata is None:
        libpc = f"{{PYODIDE_ROOT}}/cpython/installs/python-{version}.2/lib/pkgconfig"
        sysconfigdata = (
            "# system configuration generated and used by the sysconfig module\n"
            "import os\n"
            'PYODIDE_ROOT = os.environ.get("PYODIDE_ROOT", "/root/repo")\n'
            f"build_time_vars = {{'ABIFLAGS': {abiflags!r}, 'LIBPC': f'{libpc}', "
            f"'LIBPYTHON': '', 'LIBS': '-ldl  -lpthread', 'VERSION': {version!r}}}\n"
        )

    sysconfigdata_dir = target_install_dir / "sysconfigdata"
    sysconfigdata_dir.mkdir()
    (sysconfigdata_dir / f"{SYSCONFIG_NAME}.py").write_text(sysconfigdata)

    return target_install_dir


def pkgconfig_files(target_install_dir: Path) -> dict[str, str]:
    pkgconfig_dir = target_install_dir / "lib" / "pkgconfig"
    if not pkgconfig_dir.exists():
        return {}
    return {path.name: path.read_text() for path in pkgconfig_dir.iterdir()}


def test_files_match_pyodide_build(tmp_path):
    target_install_dir = make_target_install_dir(tmp_path)

    pkgconfig_dir = ensure_python_pkgconfig_files(target_install_dir, SYSCONFIG_NAME)

    assert pkgconfig_dir == target_install_dir / "lib" / "pkgconfig"
    assert pkgconfig_files(target_install_dir) == {
        "python-3.14.pc": PYODIDE_PYTHON_3_14_PC,
        "python-3.14-embed.pc": PYODIDE_PYTHON_3_14_EMBED_PC,
        "python3.pc": PYODIDE_PYTHON_3_14_PC,
        "python3-embed.pc": PYODIDE_PYTHON_3_14_EMBED_PC,
    }


@pytest.mark.parametrize("version", ["3.12", "3.13", "3.15"])
def test_other_python_versions(tmp_path, version):
    target_install_dir = make_target_install_dir(tmp_path, version=version)

    ensure_python_pkgconfig_files(target_install_dir, SYSCONFIG_NAME)

    assert pkgconfig_files(target_install_dir) == {
        f"python-{version}.pc": PYODIDE_PYTHON_3_14_PC.replace("3.14", version),
        f"python-{version}-embed.pc": PYODIDE_PYTHON_3_14_EMBED_PC.replace(
            "3.14", version
        ),
        "python3.pc": PYODIDE_PYTHON_3_14_PC.replace("3.14", version),
        "python3-embed.pc": PYODIDE_PYTHON_3_14_EMBED_PC.replace("3.14", version),
    }


def test_abiflags(tmp_path):
    target_install_dir = make_target_install_dir(tmp_path, abiflags="d")

    ensure_python_pkgconfig_files(target_install_dir, SYSCONFIG_NAME)

    files = pkgconfig_files(target_install_dir)
    assert set(files) == {
        "python-3.14d.pc",
        "python-3.14d-embed.pc",
        "python-3.14.pc",
        "python-3.14-embed.pc",
        "python3.pc",
        "python3-embed.pc",
    }
    assert files["python-3.14.pc"] == files["python3.pc"] == files["python-3.14d.pc"]
    assert "Version: 3.14\n" in files["python-3.14d.pc"]
    assert "Cflags: -I${includedir}/python3.14d\n" in files["python-3.14d.pc"]
    assert "Libs: -L${libdir} -lpython3.14d\n" in files["python-3.14d-embed.pc"]


def test_shipped_files_are_left_alone(tmp_path):
    target_install_dir = make_target_install_dir(tmp_path)
    pkgconfig_dir = target_install_dir / "lib" / "pkgconfig"
    pkgconfig_dir.mkdir(parents=True)
    (pkgconfig_dir / "python-3.14.pc").write_text("shipped\n")

    assert (
        ensure_python_pkgconfig_files(target_install_dir, SYSCONFIG_NAME)
        == pkgconfig_dir
    )
    assert pkgconfig_files(target_install_dir) == {"python-3.14.pc": "shipped\n"}


def test_second_call_changes_nothing(tmp_path):
    target_install_dir = make_target_install_dir(tmp_path)
    pkgconfig_dir = ensure_python_pkgconfig_files(target_install_dir, SYSCONFIG_NAME)
    mtimes = {path.name: path.stat().st_mtime_ns for path in pkgconfig_dir.iterdir()}

    assert (
        ensure_python_pkgconfig_files(target_install_dir, SYSCONFIG_NAME)
        == pkgconfig_dir
    )
    assert {
        path.name: path.stat().st_mtime_ns for path in pkgconfig_dir.iterdir()
    } == mtimes


@pytest.mark.parametrize(
    "sysconfigdata",
    [
        "build_time_vars = {",
        "build_time_vars = {'ABIFLAGS': '', 'LIBPYTHON': '', 'VERSION': '3.14'}\n",
        "build_time_vars = {'ABIFLAGS': '', 'LIBPYTHON': '', 'LIBS': 0, 'VERSION': '3.14'}\n",
        "",
    ],
    ids=["syntax error", "missing variable", "not a string", "empty"],
)
def test_unusable_sysconfigdata(tmp_path, sysconfigdata):
    target_install_dir = make_target_install_dir(tmp_path, sysconfigdata=sysconfigdata)

    assert ensure_python_pkgconfig_files(target_install_dir, SYSCONFIG_NAME) is None
    assert not (target_install_dir / "lib").exists()


def test_missing_sysconfigdata(tmp_path):
    target_install_dir = make_target_install_dir(tmp_path)

    assert ensure_python_pkgconfig_files(target_install_dir, "_sysconfigdata") is None
    assert not (target_install_dir / "lib").exists()


def test_missing_include_dir(tmp_path):
    target_install_dir = make_target_install_dir(tmp_path)
    shutil.rmtree(target_install_dir / "include")

    assert ensure_python_pkgconfig_files(target_install_dir, SYSCONFIG_NAME) is None
    assert not (target_install_dir / "lib").exists()


@pytest.mark.skipif(
    sys.platform == "win32" or getattr(os, "geteuid", lambda: 1)() == 0,
    reason="needs a directory that the current user cannot write to",
)
def test_read_only_install_dir(tmp_path):
    target_install_dir = make_target_install_dir(tmp_path)
    target_install_dir.chmod(0o555)

    try:
        assert ensure_python_pkgconfig_files(target_install_dir, SYSCONFIG_NAME) is None
    finally:
        target_install_dir.chmod(0o755)

    assert not (target_install_dir / "lib").exists()


@pytest.mark.skipif(
    shutil.which("pkg-config") is None, reason="pkg-config is not installed"
)
def test_pkg_config_finds_target_python_first(tmp_path):
    target_install_dir = make_target_install_dir(tmp_path)
    pkgconfig_dir = ensure_python_pkgconfig_files(target_install_dir, SYSCONFIG_NAME)

    host_dir = tmp_path / "host"
    host_dir.mkdir()
    (host_dir / "python-3.14.pc").write_text(
        "Name: Python\n"
        "Description: The host Python\n"
        "Version: 3.14\n"
        "Cflags: -I/host/include/python3.14\n"
    )

    def pkg_config(*args: str) -> str:
        return subprocess.run(
            ["pkg-config", *args],
            env=os.environ
            | {
                "PKG_CONFIG_PATH": os.pathsep.join([str(pkgconfig_dir), str(host_dir)]),
                "PKG_CONFIG_LIBDIR": str(tmp_path / "empty"),
            },
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    assert pkg_config("--modversion", "python-3.14") == "3.14"
    assert pkg_config("--modversion", "python3") == "3.14"

    (cflags,) = pkg_config("--cflags", "python-3.14").split()
    assert cflags.startswith("-I")
    assert Path(os.path.normpath(cflags[2:])) == (
        target_install_dir / "include" / "python3.14"
    )

    (libs,) = pkg_config("--libs", "python-3.14").split()
    assert libs.startswith("-L")
    assert Path(os.path.normpath(libs[2:])) == target_install_dir / "lib"

    assert "-lpython3.14" in pkg_config("--libs", "python-3.14-embed").split()
