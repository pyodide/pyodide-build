import shutil
from pathlib import Path

from pyodide_build.recipe import unvendor


def test_unvendor_tests_in_wheel(tmp_path):
    test_wheel_file =  "package_with_bunch_of_test_directories-0.1.0-py3-none-any.whl"
    test_wheel_path_orig = Path(__file__).parent.parent / "_test_wheels" / "wheel" / test_wheel_file
    shutil.copy(test_wheel_path_orig, tmp_path)

    test_wheel_path = tmp_path / test_wheel_file
    test_tar_path = unvendor.unvendor_tests_in_wheel(test_wheel_path, [])

    assert test_tar_path.exists()
    assert test_tar_path.name == "package-with-bunch-of-test-directories-tests.tar"

    # Check the contents of the tar file
    shutil.unpack_archive(test_tar_path, extract_dir=tmp_path / "extracted_tests")
    files = [f.name for f in (tmp_path / "extracted_tests").rglob("*")]

    should_exist = {
        "tests",
        "test",
        "its_a_test.py",
        "test_example.py",
        "conftest.py",
        "test_example2.py",
        "keep_this_test.py",
    }

    for f in should_exist:
        assert f in files


def test_unvendor_tests_in_wheel_retain(tmp_path):
    test_wheel_file =  "package_with_bunch_of_test_directories-0.1.0-py3-none-any.whl"
    test_wheel_path_orig = Path(__file__).parent.parent / "_test_wheels" / "wheel" / test_wheel_file
    shutil.copy(test_wheel_path_orig, tmp_path)

    test_wheel_path = tmp_path / test_wheel_file
    test_tar_path = unvendor.unvendor_tests_in_wheel(test_wheel_path, [
        "*test_example.py",
        "*keep_this_test.py",
    ])

    assert test_tar_path.exists()
    assert test_tar_path.name == "package-with-bunch-of-test-directories-tests.tar"

    # Check the contents of the tar file
    shutil.unpack_archive(test_tar_path, extract_dir=tmp_path / "extracted_tests")
    files = [f.name for f in (tmp_path / "extracted_tests").rglob("*")]

    should_exist = {
        "tests",
        "test",
        "its_a_test.py",
        "conftest.py",
        "test_example2.py",
    }

    for f in should_exist:
        assert f in files

    should_not_exist = {
        "keep_this_test.py",
    }

    for f in should_not_exist:
        assert f not in files


def test_unvendor_tests(tmp_path):
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

    install_prefix = tmp_path / "install"
    test_install_prefix = tmp_path / "install-tests"

    # create the example package
    touch(install_prefix / "ex1" / "base.py")
    touch(install_prefix / "ex1" / "conftest.py")
    touch(install_prefix / "ex1" / "test_base.py")
    touch(install_prefix / "ex1" / "tests" / "data.csv")
    touch(install_prefix / "ex1" / "tests" / "test_a.py")

    n_moved = unvendor.unvendor_tests(install_prefix, test_install_prefix, [])

    assert rlist(install_prefix) == ["ex1/base.py"]
    assert rlist(test_install_prefix) == [
        "ex1/conftest.py",
        "ex1/test_base.py",
        "ex1/tests/data.csv",
        "ex1/tests/test_a.py",
    ]

    # One test folder and two test file
    assert n_moved == 3
