import fnmatch
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from packaging.utils import parse_wheel_filename

from pyodide_build.common import (
    chdir,
    modify_wheel,
)


def unvendor_tests_in_wheel(
    wheel: Path, retain_patterns: list[str] | None = None
) -> Path | None:
    """
    Unvendor tests from a wheel file.

    This function finds the tests in the wheel file, and extracts them to a separate
    tar file. The tar file is placed in the same directory as the wheel file, with the -tests.tar suffix.

    Parameters
    ----------
    wheel
        The path to the wheel file.

    retain_patterns
        A list of patterns to retain in the tests. If a pattern is found in the tests, it will be retained.

    Returns
    -------
    The path to the tar file containing the tests. If no tests were found, returns None.
    """
    retain_patterns = retain_patterns or []

    name = parse_wheel_filename(wheel.name)[0]
    file_format = "tar"
    basename = f"{name}-tests"
    fullname = f"{basename}.{file_format}"
    destination = wheel.parent / fullname

    with TemporaryDirectory() as _tmpdir:
        tmpdir = Path(_tmpdir)
        test_dir = tmpdir / "tests"
        with modify_wheel(wheel, verbose=False) as wheel_extract_dir:
            nmoved = unvendor_tests(
                wheel_extract_dir,
                test_dir,
                retain_patterns,
            )
            if not nmoved:
                return None

            with chdir(tmpdir):
                generated_file = shutil.make_archive(basename, file_format, test_dir)
                shutil.move(tmpdir / generated_file, destination)

    return destination


def unvendor_tests(
    install_prefix: Path, test_install_prefix: Path, retain_test_patterns: list[str]
) -> int:
    """Unvendor test files and folders

    This function recursively walks through install_prefix and moves anything
    that looks like a test folder under test_install_prefix.


    Parameters
    ----------
    install_prefix
        the folder where the package was installed
    test_install_prefix
        the folder where to move the tests. If it doesn't exist, it will be
        created.

    Returns
    -------
    n_moved
        number of files or folders moved
    """
    n_moved = 0
    out_files = []
    shutil.rmtree(test_install_prefix, ignore_errors=True)
    for root, _dirs, files in os.walk(install_prefix):
        root_rel = Path(root).relative_to(install_prefix)
        if root_rel.name == "__pycache__" or root_rel.name.endswith(".egg_info"):
            continue
        if root_rel.name in {"test", "tests"}:
            # This is a test folder
            (test_install_prefix / root_rel).parent.mkdir(exist_ok=True, parents=True)
            shutil.move(install_prefix / root_rel, test_install_prefix / root_rel)
            n_moved += 1
            continue
        out_files.append(root)
        for fpath in files:
            if (
                fnmatch.fnmatchcase(fpath, "test_*.py")
                or fnmatch.fnmatchcase(fpath, "*_test.py")
                or fpath == "conftest.py"
            ):
                if any(fnmatch.fnmatchcase(fpath, pat) for pat in retain_test_patterns):
                    continue
                (test_install_prefix / root_rel).mkdir(exist_ok=True, parents=True)
                shutil.move(
                    install_prefix / root_rel / fpath,
                    test_install_prefix / root_rel / fpath,
                )
                n_moved += 1

    return n_moved
