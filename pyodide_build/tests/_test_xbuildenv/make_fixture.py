"""
Build a test xbuildenv fixture distilled from a Pyodide cross-build environment.

The fixture is an xbuildenv with everything stripped
out to reduce its size, but still enough to run the unit tests.

The xbuildenv metadata is available at https://pyodide.github.io/pyodide/api/v2/pyodide-cross-build-environments.json.

Example usage is as follows:
    curl -LJO https://github.com/pyodide/pyodide/releases/download/314.0.3/xbuildenv-314.0.3.tar.gz
    python make_fixture.py xbuildenv-314.0.3.tar.gz xbuildenv-test-3.14.tar.gz
"""

import argparse
import gzip
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

# Everything that the tests read, anything that we don't list here gets dropped
TO_KEEP = [
    "requirements.txt",
    "pyodide-root/Makefile.envs",
    "pyodide-root/package.json",
    "pyodide-root/dist/pyodide-lock.json",
    "site-packages-extras/numpy/_core/include/numpy/_numpyconfig.h",
    "site-packages-extras/numpy/_core/include/numpy/numpyconfig.h",
    "site-packages-extras/numpy/_core/lib/libnpymath.a",
    "site-packages-extras/numpy/random/lib/libnpyrandom.a",
    "site-packages-extras/scipy/linalg/cython_blas.pxd",
    "site-packages-extras/scipy/linalg/cython_lapack.pxd",
]

KEEP_PACKAGES = [
    "attrs",
    "jinja2",
    "markupsafe",
    "micropip",
    "packaging",
    "pluggy",
    "pytest",
    "regex",
    "setuptools",
    "six",
]

MTIME = 315532800  # 1980-01-01


def python_version_of(xbuildenv: Path) -> str:
    """Read the Python version out of the tree, such as `3.14.2`."""
    installs = sorted((xbuildenv / "pyodide-root/cpython/installs").glob("python-*"))
    if len(installs) != 1:
        sys.exit(f"expected one python install, found {len(installs)}")

    return installs[0].name.removeprefix("python-")


def strip_lockfile(source: Path, dest: Path) -> None:
    lock = json.loads(source.read_text())
    kept = {n: lock["packages"][n] for n in KEEP_PACKAGES if n in lock["packages"]}
    if not kept:
        sys.exit(f"none of the wanted packages are in {source}")

    lock["packages"] = kept
    dest.write_text(json.dumps(lock, indent=2, sort_keys=True))


def build(xbuildenv: Path, out: Path) -> None:
    version = python_version_of(xbuildenv)
    major_minor = ".".join(version.split(".")[:2])
    install_dir = f"pyodide-root/cpython/installs/python-{version}"
    print(f"python {version} -> {out.name}")

    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "xbuildenv"

        for name in TO_KEEP:
            source = xbuildenv / name
            if not source.exists():
                sys.exit(f"{source} is missing. Has the layout changed?")
            dest = staged / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, dest)

        strip_lockfile(
            xbuildenv / "pyodide-root/dist/pyodide-lock.json",
            staged / "pyodide-root/dist/pyodide-lock.json",
        )

        shutil.copy(
            xbuildenv
            / install_dir
            / "sysconfigdata"
            / "_sysconfigdata__emscripten_wasm32-emscripten.py",
            _mkdir(staged / install_dir / "sysconfigdata")
            / "_sysconfigdata__emscripten_wasm32-emscripten.py",
        )

        # Empty, but the include paths in Makefile.envs point at them
        includes = staged / install_dir / "include" / f"python{major_minor}"
        for name in ("", "cpython", "internal"):
            _mkdir(includes / name)

        _write_archive(staged, out)


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_archive(staged: Path, out: Path) -> None:
    def normalize(member: tarfile.TarInfo) -> tarfile.TarInfo:
        member.mtime = MTIME
        member.uid = member.gid = 0
        member.uname = member.gname = "root"
        return member

    # tarfile stamps it with the current time and the output
    # filename so I'm using a zipfile instead
    with open(out, "wb") as raw:
        with gzip.GzipFile(
            filename="", fileobj=raw, mode="wb", mtime=MTIME
        ) as compressed:
            with tarfile.open(
                fileobj=compressed, mode="w", format=tarfile.GNU_FORMAT
            ) as archive:
                for path in sorted(staged.rglob("*")):
                    archive.add(
                        path,
                        arcname=f"xbuildenv/{path.relative_to(staged)}",
                        recursive=False,
                        filter=normalize,
                    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="xbuildenv tarball or unpacked tree")
    parser.add_argument("out", type=Path, help="fixture to write")
    args = parser.parse_args()

    if args.source.is_dir():
        build(args.source, args.out)
        return

    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(args.source) as archive:
            archive.extractall(tmp, filter="data")
        unpacked = [p for p in Path(tmp).iterdir() if p.is_dir()]
        if len(unpacked) != 1:
            sys.exit(f"expected one directory in {args.source}")
        build(unpacked[0], args.out)


if __name__ == "__main__":
    sys.exit(main())
