import os

import pytest

from pyodide_build import build_env, common
from pyodide_build.config import BUILD_KEY_TO_VAR
from pyodide_build.xbuildenv import CrossBuildEnvManager


class TestInTree:
    def test_search_pyodide_root(self, tmp_path, reset_env_vars, reset_cache):
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[tool._pyodide]")
        assert build_env.search_pyodide_root(tmp_path) == tmp_path
        assert build_env.search_pyodide_root(tmp_path / "subdir") == tmp_path
        assert build_env.search_pyodide_root(tmp_path / "subdir" / "subdir") == tmp_path

        pyproject_file.unlink()
        assert build_env.search_pyodide_root(tmp_path) is None


class TestOutOfTree(TestInTree):
    # Note: other tests are inherited from TestInTree

    def test_init_environment(self, dummy_xbuildenv, reset_env_vars, reset_cache):
        assert "PYODIDE_ROOT" not in os.environ

        build_env.init_environment()
        manager = CrossBuildEnvManager(dummy_xbuildenv / common.xbuildenv_dirname())

        assert "PYODIDE_ROOT" in os.environ
        assert os.environ["PYODIDE_ROOT"] == str(manager.pyodide_root)

    def test_init_environment_pyodide_root_already_set(
        self, reset_env_vars, reset_cache
    ):
        assert "PYODIDE_ROOT" not in os.environ
        os.environ["PYODIDE_ROOT"] = "/set_by_user"

        build_env.init_environment()

        assert os.environ["PYODIDE_ROOT"] == "/set_by_user"

    def test_get_pyodide_root(self, dummy_xbuildenv, reset_env_vars, reset_cache):
        assert "PYODIDE_ROOT" not in os.environ

        pyodide_root = build_env.get_pyodide_root()
        manager = CrossBuildEnvManager(dummy_xbuildenv / common.xbuildenv_dirname())
        assert pyodide_root == manager.pyodide_root

    def test_get_pyodide_root_pyodide_root_already_set(
        self, reset_env_vars, reset_cache
    ):
        assert "PYODIDE_ROOT" not in os.environ
        os.environ["PYODIDE_ROOT"] = "/set_by_user"

        assert str(build_env.get_pyodide_root()) == "/set_by_user"

    def test_in_xbuildenv(self, dummy_xbuildenv, reset_env_vars, reset_cache):
        assert build_env.in_xbuildenv()

    def test_get_build_environment_vars(
        self, dummy_xbuildenv, reset_env_vars, reset_cache
    ):
        manager = CrossBuildEnvManager(dummy_xbuildenv / common.xbuildenv_dirname())
        build_vars = build_env.get_build_environment_vars(manager.pyodide_root)

        # extra variables that does not come from config files.
        extra_vars = {"PYODIDE", "PYODIDE_PACKAGE_ABI", "PYTHONPATH"}

        all_keys = set(BUILD_KEY_TO_VAR.values()) | extra_vars
        for var in build_vars:
            assert var in all_keys, f"Unknown {var}"

        # Additionally we set these variables
        for var in extra_vars:
            assert var in build_vars, f"Missing {var}"

    def test_get_build_flag(self, dummy_xbuildenv, reset_env_vars, reset_cache):
        manager = CrossBuildEnvManager(dummy_xbuildenv / common.xbuildenv_dirname())
        for key, val in build_env.get_build_environment_vars(
            pyodide_root=manager.pyodide_root
        ).items():
            assert build_env.get_build_flag(key) == val

        with pytest.raises(ValueError):
            build_env.get_build_flag("UNKNOWN_VAR")

    def test_get_build_environment_vars_host_env(
        self, monkeypatch, dummy_xbuildenv, reset_env_vars, reset_cache
    ):
        # host environment variables should have precedence over
        # variables defined in Makefile.envs

        manager = CrossBuildEnvManager(dummy_xbuildenv / common.xbuildenv_dirname())
        pyodide_root = manager.pyodide_root

        e = build_env.get_build_environment_vars(pyodide_root)
        assert e["PYODIDE"] == "1"

        monkeypatch.setenv("PIP_CONSTRAINT", "/tmp/constraint.txt")

        build_env.get_build_environment_vars.cache_clear()

        e_host = build_env.get_build_environment_vars(pyodide_root)
        assert e_host.get("PIP_CONSTRAINT") == "/tmp/constraint.txt"
        assert e_host.get("PIP_CONSTRAINT") != e.get("PIP_CONSTRAINT")

        build_env.get_build_environment_vars.cache_clear()

        monkeypatch.delenv("PIP_CONSTRAINT")
        monkeypatch.setenv("RANDOM_ENV", "1234")

        build_env.get_build_environment_vars.cache_clear()
        e = build_env.get_build_environment_vars(pyodide_root)
        assert "PIP_CONSTRAINT" in e
        assert "RANDOM_ENV" not in e


def test_wheel_paths(dummy_xbuildenv):
    from pathlib import Path

    old_version = "cp38"
    PYMAJOR = int(build_env.get_build_flag("PYMAJOR"))
    PYMINOR = int(build_env.get_build_flag("PYMINOR"))
    PLATFORM = build_env.platform()
    current_version = f"cp{PYMAJOR}{PYMINOR}"
    future_version = f"cp{PYMAJOR}{PYMINOR + 1}"
    strings = []

    for interp in [
        old_version,
        current_version,
        future_version,
        "py3",
        "py2",
        "py2.py3",
    ]:
        for abi in [interp, "abi3", "none"]:
            for arch in [PLATFORM, "linux_x86_64", "any"]:
                strings.append(f"wrapt-1.13.3-{interp}-{abi}-{arch}.whl")

    paths = [Path(x) for x in strings]
    assert sorted(
        [
            x.stem.split("-", 2)[-1]
            for x in common._find_matching_wheels(paths, build_env.pyodide_tags())
        ]
    ) == sorted(
        [
            f"{current_version}-{current_version}-{PLATFORM}",
            f"{current_version}-abi3-{PLATFORM}",
            f"{current_version}-none-{PLATFORM}",
            f"{old_version}-abi3-{PLATFORM}",
            f"py3-none-{PLATFORM}",
            f"py2.py3-none-{PLATFORM}",
            "py3-none-any",
            "py2.py3-none-any",
            f"{current_version}-none-any",
        ]
    )


def test_ensure_emscripten_auto_installs_when_missing(dummy_xbuildenv, monkeypatch):
    needed_version = build_env.emscripten_version()
    install_called = False
    activate_called = False
    call_count = [0]

    def mock_get_emscripten_version_info():
        call_count[0] += 1
        if call_count[0] == 1:
            raise FileNotFoundError()
        return f"emcc (Emscripten) {needed_version} (abc123)\nclang version 15.0.0"

    def mock_install_emscripten(self, version=None):
        nonlocal install_called
        install_called = True
        return dummy_xbuildenv / "emsdk"

    def mock_activate_emscripten_env(emsdk_dir):
        nonlocal activate_called
        activate_called = True
        return {"EMSDK": str(emsdk_dir), "PATH": f"{emsdk_dir}/bin"}

    monkeypatch.setattr(
        build_env, "get_emscripten_version_info", mock_get_emscripten_version_info
    )
    monkeypatch.setattr(
        CrossBuildEnvManager, "install_emscripten", mock_install_emscripten
    )
    monkeypatch.setattr(
        build_env, "activate_emscripten_env", mock_activate_emscripten_env
    )

    build_env.ensure_emscripten()

    assert install_called
    assert activate_called
    assert "EMSDK" in os.environ


def test_ensure_emscripten_skipped_with_env_var(dummy_xbuildenv, monkeypatch):
    needed_version = build_env.emscripten_version()
    install_called = False

    def mock_get_emscripten_version_info():
        raise FileNotFoundError()

    def mock_install_emscripten(self, version=None):
        nonlocal install_called
        install_called = True
        return dummy_xbuildenv / "emsdk"

    monkeypatch.setattr(
        build_env, "get_emscripten_version_info", mock_get_emscripten_version_info
    )
    monkeypatch.setattr(
        CrossBuildEnvManager, "install_emscripten", mock_install_emscripten
    )
    monkeypatch.setenv("PYODIDE_SKIP_EMSCRIPTEN_INSTALL", "1")

    with pytest.raises(
        RuntimeError,
        match=f"No Emscripten compiler found. Need Emscripten version {needed_version}",
    ):
        build_env.ensure_emscripten()

    assert not install_called


def test_ensure_emscripten_skipped_with_flag(dummy_xbuildenv, monkeypatch):
    needed_version = build_env.emscripten_version()
    install_called = False

    def mock_get_emscripten_version_info():
        raise FileNotFoundError()

    def mock_install_emscripten(self, version=None):
        nonlocal install_called
        install_called = True
        return dummy_xbuildenv / "emsdk"

    monkeypatch.setattr(
        build_env, "get_emscripten_version_info", mock_get_emscripten_version_info
    )
    monkeypatch.setattr(
        CrossBuildEnvManager, "install_emscripten", mock_install_emscripten
    )

    with pytest.raises(
        RuntimeError,
        match=f"No Emscripten compiler found. Need Emscripten version {needed_version}",
    ):
        build_env.ensure_emscripten(skip_install=True)

    assert not install_called


def test_ensure_emscripten_already_installed(dummy_xbuildenv, monkeypatch):
    needed_version = build_env.emscripten_version()
    install_called = False

    def mock_get_emscripten_version_info():
        return f"emcc (Emscripten) {needed_version} (abc123)\nclang version 15.0.0"

    def mock_install_emscripten(self, version=None):
        nonlocal install_called
        install_called = True
        return dummy_xbuildenv / "emsdk"

    monkeypatch.setattr(
        build_env, "get_emscripten_version_info", mock_get_emscripten_version_info
    )
    monkeypatch.setattr(
        CrossBuildEnvManager, "install_emscripten", mock_install_emscripten
    )

    build_env.ensure_emscripten()

    assert not install_called


def test_ensure_emscripten_version_mismatch(dummy_xbuildenv, monkeypatch):
    needed_version = build_env.emscripten_version()
    wrong_version = "3.1.0"
    install_called = False

    def mock_get_emscripten_version_info():
        return f"emcc (Emscripten) {wrong_version} (abc123)\nclang version 15.0.0"

    def mock_install_emscripten(self, version=None):
        nonlocal install_called
        install_called = True
        return dummy_xbuildenv / "emsdk"

    monkeypatch.setattr(
        build_env, "get_emscripten_version_info", mock_get_emscripten_version_info
    )
    monkeypatch.setattr(
        CrossBuildEnvManager, "install_emscripten", mock_install_emscripten
    )

    with pytest.raises(
        RuntimeError,
        match=f"Incorrect Emscripten version {wrong_version}. Need Emscripten version {needed_version}",
    ):
        build_env.ensure_emscripten()

    assert not install_called
