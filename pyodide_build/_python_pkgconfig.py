from pathlib import Path

from pyodide_build.logger import logger

# Misc/python.pc.in and Misc/python-embed.pc.in from CPython.
_PYTHON_PC = """\
# See: man pkg-config
prefix=${pcfiledir}/../..
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include

Name: Python
Description: Build a C extension for Python
Requires:
Version: @VERSION@
Libs.private: -ldl  -lpthread
Libs: -L${libdir}\x20
Cflags: -I${includedir}/python@VERSION@
"""

_PYTHON_EMBED_PC = """\
# See: man pkg-config
prefix=${pcfiledir}/../..
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include

Name: Python
Description: Embed Python into an application
Requires:
Version: @VERSION@
Libs.private: -ldl  -lpthread
Libs: -L${libdir} -lpython@VERSION@
Cflags: -I${includedir}/python@VERSION@
"""


def ensure_python_pkgconfig_files(
    target_install_dir: Path, python_version: str
) -> Path:
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
    python_version
        The major and minor version of the target Python, such as "3.14".

    Returns
    -------
    The directory with the pkg-config files.
    """
    pkgconfig_dir = target_install_dir / "lib" / "pkgconfig"

    if (pkgconfig_dir / f"python-{python_version}.pc").is_file():
        return pkgconfig_dir

    python_pc = _PYTHON_PC.replace("@VERSION@", python_version)
    python_embed_pc = _PYTHON_EMBED_PC.replace("@VERSION@", python_version)

    pkgconfig_dir.mkdir(parents=True, exist_ok=True)
    # python-3.x.pc is written last, because its presence is what marks the
    # files as complete
    for name in ("python3", f"python-{python_version}"):
        (pkgconfig_dir / f"{name}-embed.pc").write_text(
            python_embed_pc, encoding="utf-8", newline="\n"
        )
        (pkgconfig_dir / f"{name}.pc").write_text(
            python_pc, encoding="utf-8", newline="\n"
        )

    logger.info("Wrote the Python pkg-config files to %s", pkgconfig_dir)
    return pkgconfig_dir
