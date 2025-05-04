import os
import platform
import shutil
import subprocess
from textwrap import dedent

import pytest

from pyodide_build.out_of_tree import venv
from pyodide_build.xbuildenv import CrossBuildEnvManager


@pytest.fixture(scope="session")
def base_test_dir(tmp_path_factory):
    """Create a session-wide directory that persists for all tests."""
    base_dir = tmp_path_factory.getbasetemp() / "pyodide_test_base"
    base_dir.mkdir(exist_ok=True)

    venv_path = base_dir / "test_venv"
    venv_path.mkdir(exist_ok=True)

    cwd = os.getcwd()
    os.chdir(str(base_dir))

    xbuildenv_test_name = ".pyodide-xbuildenv-for-testing"

    manager = CrossBuildEnvManager(xbuildenv_test_name)
    manager.install(
        url="https://github.com/pyodide/pyodide/releases/download/0.27.3/xbuildenv-0.27.3.tar.bz2"
    )

    os.chdir(cwd)

    # Clean the venv before yielding, but preserve the xbuildenv
    # as we can reuse it between the tests
    if venv_path.exists():
        for item in venv_path.iterdir():
            if not str(item.name).startswith(xbuildenv_test_name):
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
    yield base_dir
    shutil.rmtree(base_dir)


@pytest.mark.parametrize(
    "options,expected_calls",
    [
        ([], []),
        (["--clear"], ["--clear"]),
        (["--no-vcs-ignore"], ["--no-vcs-ignore"]),
        (["--pip", "23.0.1"], ["--pip", "23.0.1"]),
        (["--no-setuptools"], ["--no-setuptools"]),
        (["--no-wheel"], ["--no-wheel"]),
        (["--no-periodic-update"], ["--no-periodic-update"]),
        # TODO: enable when they are supported
        # (["--symlink-app-data"], ["--symlink-app-data"]),
        # (["--copies"], ["--copies"]),
    ],
)
def test_venv_cli_args(monkeypatch, options, expected_calls, tmp_path):
    """Test that CLI options are correctly passed to virtualenv."""
    captured_args = None
    temp_venv_path = tmp_path / "test_venv"

    def mock_session_via_cli(args):
        nonlocal captured_args
        captured_args = args

        class MockSession:
            def __init__(self):
                self.creator = type("MockCreator", (), {"dest": str(temp_venv_path)})

            def run(self):
                # create the directory to avoid cleanup issues
                temp_venv_path.mkdir(exist_ok=True)

        return MockSession()

    temp_venv_path.mkdir(exist_ok=True)

    # Mock most of the functions called by create_pyodide_venv
    # as we just need to check the arguments passed to it
    monkeypatch.setattr("virtualenv.session_via_cli", mock_session_via_cli)
    monkeypatch.setattr(
        "pyodide_build.out_of_tree.venv.check_host_python_version", lambda session: None
    )
    monkeypatch.setattr(
        "pyodide_build.out_of_tree.venv.create_pip_conf", lambda venv_root: None
    )
    monkeypatch.setattr(
        "pyodide_build.out_of_tree.venv.create_pip_script", lambda venv_bin: None
    )
    monkeypatch.setattr(
        "pyodide_build.out_of_tree.venv.create_pyodide_script", lambda venv_bin: None
    )
    monkeypatch.setattr(
        "pyodide_build.out_of_tree.venv.install_stdlib", lambda venv_bin: None
    )
    monkeypatch.setattr(
        "pyodide_build.out_of_tree.venv.pyodide_dist_dir",
        lambda: temp_venv_path / "dist",
    )

    # necessary directories for valid venv
    (temp_venv_path / "dist").mkdir(exist_ok=True)
    (temp_venv_path / "bin").mkdir(exist_ok=True)

    venv.create_pyodide_venv(temp_venv_path, options)

    for expected_arg in expected_calls:
        assert expected_arg in captured_args, (
            f"Expected {expected_arg} in call args: {captured_args}"
        )


def test_supported_virtualenv_options():
    """Test that all (currently) supported options are in SUPPORTED_VIRTUALENV_OPTIONS"""
    supported_options = venv.SUPPORTED_VIRTUALENV_OPTIONS
    expected_options = [
        "--clear",
        "--no-clear",
        "--no-vcs-ignore",
        # "--copies",
        # "--always-copy",
        # "--symlink-app-data",
        "--no-download",
        "--never-download",
        "--download",
        "--extra-search-dir",
        "--pip",
        "--setuptools",
        "--no-setuptools",
        "--no-wheel",
        "--no-periodic-update",
    ]

    assert set(supported_options) == set(expected_options)


@pytest.mark.integration
@pytest.mark.parametrize(
    "options,check_function",
    [
        (
            [],
            lambda path: (path / "bin" / "python").exists()
            and (path / "bin" / "pip").exists(),
        ),
        (["--clear"], lambda path: (path / "bin" / "python").exists()),
        (["--no-vcs-ignore"], lambda path: (path / "bin" / "python").exists()),
        (
            ["--no-setuptools"],
            lambda path: not list(path.glob("**/setuptools-*.dist-info")),
        ),
        (["--no-wheel"], lambda path: not list(path.glob("**/wheel-*.dist-info"))),
    ],
    ids=["default", "clear", "no-vcs-ignore", "no-setuptools", "no-wheel"],
)
def test_venv_creation(base_test_dir, options, check_function):
    venv_path = base_test_dir / "test_venv"
    venv.create_pyodide_venv(venv_path, options)
    assert (venv_path / "pyvenv.cfg").exists()
    assert (venv_path / "bin" / "python").exists()
    assert (venv_path / "bin" / "pyodide").exists()
    assert (venv_path / "pip.conf").exists()
    assert check_function(venv_path)


@pytest.mark.integration
@pytest.mark.parametrize(
    "package,version",
    [
        ("pip", "23.0.1"),
        ("setuptools", "67.6.0"),
        ("wheel", "0.40.0"),
    ],
)
def test_installation_of_seed_package_versions(base_test_dir, package, version):
    """Test installing specific seed package versions."""
    venv_path = base_test_dir / "test_venv"
    venv.create_pyodide_venv(venv_path, [f"--{package}", version])
    dist_info_dirs = list(venv_path.glob(f"**/{package}-{version}*.dist-info"))
    assert len(dist_info_dirs) > 0, f"{package} {version} not found in the venv"


@pytest.mark.integration
@pytest.mark.parametrize(
    "packages",
    [
        ["six"],  # pure
        ["numpy"],  # compiled
        ["six", "numpy"],  # mixed
    ],
    ids=["pure", "compiled", "both-pure-and-compiled"],
)
def test_pip_install(base_test_dir, packages):
    """Test that our monkeypatched pip can install packages into the venv"""
    venv_path = base_test_dir / "test_venv"

    venv.create_pyodide_venv(venv_path, [])
    venv_pip_path = venv_path / "bin" / "pip"
    assert venv_pip_path.exists(), "pip wasn't found in the virtual environment"

    for package in packages:
        result = subprocess.run(
            [
                str(venv_pip_path),
                "install",
                package,
                "-v",
                "--disable-pip-version-check",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Failed to install {package}: {result.stderr}"

        # Verify package is installed by checking dist-info directory
        dist_info_dirs = list(
            venv_path.glob(f"**/{package.replace('-', '_')}-*.dist-info")
        )
        assert len(dist_info_dirs) > 0, f"{package} not found in the venv"


@pytest.mark.integration
def test_pip_downgrade(base_test_dir):
    """Test that our monkeypatched pip can upgrade/downgrade itself"""
    venv_path = base_test_dir / "test_venv"

    venv.create_pyodide_venv(venv_path, [])
    venv_pip_path = venv_path / "bin" / "pip"
    assert venv_pip_path.exists(), "pip wasn't found in the virtual environment"

    result = subprocess.run(
        [
            str(venv_pip_path),
            "install",
            "--upgrade",
            "pip==24.0",
            "-v",
            "--disable-pip-version-check",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Failed to downgrade pip: {result.stderr}"

    result = subprocess.run(
        [str(venv_pip_path), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("pip 24.0")
    assert venv_pip_path.readlink() == venv_pip_path.with_name("pip_patched")


@pytest.mark.integration
def test_pytest_invoke(base_test_dir):
    if platform.system() == "Darwin":
        pytest.skip("TODO: Why doesn't this work on Mac OS?")
    venv_path = base_test_dir / "test_venv"
    venv.create_pyodide_venv(venv_path, [])
    pip = venv_path / "bin" / "pip"
    subprocess.run(
        [
            pip,
            "install",
            "pytest",
        ],
        check=True,
    )
    venv_pytest = venv_path / "bin" / "pytest"

    (base_test_dir / "test_a.py").write_text(
        dedent(
            """\
            from pyodide.code import run_js

            def test_run_js():
                assert run_js("(x) => x + 1")(7) == 8
            """
        )
    )
    subprocess.run(
        [venv_pytest, base_test_dir / "test_a.py"],
        check=True,
        env=os.environ | {"_PYODIDE_EXTRA_MOUNTS": str(base_test_dir)},
    )
