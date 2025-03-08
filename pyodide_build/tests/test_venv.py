import shutil
import subprocess

import pytest

from pyodide_build.out_of_tree import venv


@pytest.fixture(scope="session")
def base_test_dir(tmp_path_factory):
    """Create a session-wide directory that persists for all tests."""
    base_dir = tmp_path_factory.getbasetemp() / "pyodide_test_base"
    base_dir.mkdir(exist_ok=True)
    yield base_dir
    # Don't clean up the base directory at the end so the xbuildenv can
    # be reused even between pytest runs if preferred


@pytest.fixture
def persistent_xbuildenv(base_test_dir):
    """Create a clean venv directory for each test while preserving the xbuildenv."""
    # Use a fixed venv path that will be reused between tests
    venv_path = base_test_dir / "test_venv"

    if venv_path.exists():
        for item in venv_path.iterdir():
            if not str(item.name).startswith(".pyodide-xbuildenv"):
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
    else:
        venv_path.mkdir(parents=True)

    yield venv_path


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
        assert (
            expected_arg in captured_args
        ), f"Expected {expected_arg} in call args: {captured_args}"


def test_supported_virtualenv_options():
    """Test that all (currently) supported options are in SUPPORTED_VIRTUALENV_OPTIONS"""
    supported_options = venv.SUPPORTED_VIRTUALENV_OPTIONS
    expected_options = [
        "--clear",
        "--no-clear",
        "--no-vcs-ignore",
        "--symlinks",
        # "--copies",
        # "--always-copy",
        # "--symlink-app-data",
        "--no-download",
        "--never-download",
        "--download",
        "--extra-search-dir",
        "--pip",
        "--setuptools",
        "--wheel",
        "--no-setuptools",
        "--no-wheel",
        "--no-periodic-update",
    ]

    assert set(supported_options) == set(expected_options)


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
def test_venv_creation(persistent_xbuildenv, options, check_function):
    try:
        venv.create_pyodide_venv(persistent_xbuildenv, options)
        assert (persistent_xbuildenv / "pyvenv.cfg").exists()
        assert (persistent_xbuildenv / "bin" / "python").exists()
        assert (persistent_xbuildenv / "bin" / "pyodide").exists()
        assert (persistent_xbuildenv / "pip.conf").exists()
        assert check_function(persistent_xbuildenv)

    except Exception as e:
        pytest.fail(f"Failed to create virtual environment: {e}")


@pytest.mark.parametrize(
    "package,version",
    [
        ("pip", "23.0.1"),
        ("setuptools", "67.6.0"),
        ("wheel", "0.40.0"),
    ],
)
def test_installation_of_seed_package_versions(persistent_xbuildenv, package, version):
    """Test installing specific seed package versions."""
    try:
        venv.create_pyodide_venv(persistent_xbuildenv, [f"--{package}", version])
        dist_info_dirs = list(
            persistent_xbuildenv.glob(f"**/{package}-{version}*.dist-info")
        )
        assert len(dist_info_dirs) > 0, f"{package} {version} not found in the venv"

    except Exception as e:
        pytest.fail(
            f"Failed to create virtual environment with {package}={version}: {e}"
        )


@pytest.mark.parametrize(
    "packages",
    [
        ["six"],  # pure
        ["numpy"],  # compiled
        ["six", "numpy"],  # mixed
    ],
    ids=["pure", "compiled", "both-pure-and-compiled"],
)
def test_pip_install(persistent_xbuildenv, packages):
    """Test that our monkeypatched pip can install packages into the venv"""
    try:
        venv.create_pyodide_venv(persistent_xbuildenv, [])
        pip_path = persistent_xbuildenv / "bin" / "pip"
        assert pip_path.exists(), "pip wasn't found in the virtual environment"

        for package in packages:
            result = subprocess.run(
                [str(pip_path), "install", package],
                capture_output=True,
                text=True,
                check=False,
            )
            assert (
                result.returncode == 0
            ), f"Failed to install {package}: {result.stderr}"

            # Verify package is installed by checking dist-info directory
            dist_info_dirs = list(
                persistent_xbuildenv.glob(f"**/{package.replace('-', '_')}-*.dist-info")
            )
            assert len(dist_info_dirs) > 0, f"{package} not found in the venv"

        # Verify that the installed packages can be imported. It's overkill
        # but it's a good sanity check as this is an integration test, and
        # the import isn't the slow part here.
        python_path = persistent_xbuildenv / "bin" / "python"
        for package in packages:
            import_name = package.replace("-", "_")
            result = subprocess.run(
                [
                    str(python_path),
                    "-c",
                    f"import {import_name}; print({import_name}.__version__)",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert (
                result.returncode == 0
            ), f"Failed to import {package}: {result.stderr}"
            assert result.stdout.strip(), f"No version found for {package}"

    except Exception as e:
        pytest.fail(f"Failed to test pip functionality: {e}")
