import ast
import os
from pathlib import Path

from pyodide_build.logger import logger

# Misc/python.pc.in and Misc/python-embed.pc.in from CPython. They are the
# same from Python 3.12 to 3.15.
_PYTHON_PC_IN = """\
# See: man pkg-config
prefix=@prefix@
exec_prefix=@exec_prefix@
libdir=@libdir@
includedir=@includedir@

Name: Python
Description: Build a C extension for Python
Requires:
Version: @VERSION@
Libs.private: @LIBS@
Libs: -L${libdir} @LIBPYTHON@
Cflags: -I${includedir}/python@VERSION@@ABIFLAGS@
"""

_PYTHON_EMBED_PC_IN = """\
# See: man pkg-config
prefix=@prefix@
exec_prefix=@exec_prefix@
libdir=@libdir@
includedir=@includedir@

Name: Python
Description: Embed Python into an application
Requires:
Version: @VERSION@
Libs.private: @LIBS@
Libs: -L${libdir} -lpython@VERSION@@ABIFLAGS@
Cflags: -I${includedir}/python@VERSION@@ABIFLAGS@
"""

_SYSCONFIG_VARS = ("VERSION", "ABIFLAGS", "LIBS", "LIBPYTHON")


def _read_sysconfig_vars(sysconfigdata: Path) -> dict[str, str] | None:
    """
    Read the variables that the pkg-config files need from a sysconfigdata
    module, without importing it. Returns None if any of them is missing.
    """
    try:
        tree = ast.parse(sysconfigdata.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None

    for node in tree.body:
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "build_time_vars"
            for target in node.targets
        ):
            continue

        found = {}
        for key, value in zip(node.value.keys, node.value.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and key.value in _SYSCONFIG_VARS
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                found[key.value] = value.value

        if len(found) == len(_SYSCONFIG_VARS):
            return found

    return None


def _render(template: str, sysconfig_vars: dict[str, str]) -> str:
    substitutions = {
        # Relative to the .pc file, so that the cross-build environment can be
        # moved. The other three are what configure fills in by default.
        "@prefix@": "${pcfiledir}/../..",
        "@exec_prefix@": "${prefix}",
        "@libdir@": "${exec_prefix}/lib",
        "@includedir@": "${prefix}/include",
        **{f"@{name}@": value for name, value in sysconfig_vars.items()},
    }
    for token, value in substitutions.items():
        template = template.replace(token, value)
    return template


def _write_if_missing(path: Path, content: str) -> None:
    if path.exists():
        return

    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def ensure_python_pkgconfig_files(
    target_install_dir: Path, sysconfig_name: str
) -> Path | None:
    """
    Make sure that the target Python of a cross-build environment has its
    pkg-config files, and return the directory that holds them.

    The sysconfigdata of the target Python points `LIBPC` at
    `<target_install_dir>/lib/pkgconfig`, but cross-build environments only
    ship `python-3.x.pc` there since pyodide/pyodide#6556. For the older ones,
    this writes the same files that the Pyodide build generates now. It never
    touches a cross-build environment that ships its own.

    Parameters
    ----------
    target_install_dir
        The path to the target Python installation.
    sysconfig_name
        The name of the sysconfigdata module of the target Python.

    Returns
    -------
    The directory with the pkg-config files, or None if they are missing and
    could not be written.
    """
    pkgconfig_dir = target_install_dir / "lib" / "pkgconfig"

    sysconfig_vars = _read_sysconfig_vars(
        target_install_dir / "sysconfigdata" / f"{sysconfig_name}.py"
    )
    if sysconfig_vars is None:
        return None

    version = sysconfig_vars["VERSION"]
    abiflags = sysconfig_vars["ABIFLAGS"]
    ldversion = f"{version}{abiflags}"

    if (pkgconfig_dir / f"python-{ldversion}.pc").is_file():
        return pkgconfig_dir

    if not (target_install_dir / "include" / f"python{ldversion}").is_dir():
        return None

    python_pc = _render(_PYTHON_PC_IN, sysconfig_vars)
    python_embed_pc = _render(_PYTHON_EMBED_PC_IN, sysconfig_vars)

    names = ["python3"]
    if abiflags:
        names.append(f"python-{version}")
    # Written last, because its presence is what marks the files as complete
    names.append(f"python-{ldversion}")

    try:
        pkgconfig_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            _write_if_missing(pkgconfig_dir / f"{name}-embed.pc", python_embed_pc)
            _write_if_missing(pkgconfig_dir / f"{name}.pc", python_pc)
    except OSError as e:
        logger.warning(
            "Could not write the Python pkg-config files to %s: %s", pkgconfig_dir, e
        )
        return None

    logger.info("Wrote the Python pkg-config files to %s", pkgconfig_dir)
    return pkgconfig_dir
