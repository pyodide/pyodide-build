from pyodide_build import pypabuild, pywasmcross
from pyodide_build.constants import BASE_IGNORED_REQUIREMENTS
from pathlib import Path
import shutil

class MockIsolatedEnv:
    def __init__(self, temp_path):
        self.path = temp_path
        self.installed = set()

    def install(self, reqs):
        for req in reqs:
            self.installed.add(req)


def test_remove_avoided_requirements():
    assert pypabuild.remove_avoided_requirements(
        {"foo", "bar", "baz"},
        {"foo", "bar", "qux"},
    ) == {"baz"}


def test_install_reqs(tmp_path, dummy_xbuildenv):
    env = MockIsolatedEnv(tmp_path)

    reqs = {"foo", "bar", "baz"}

    pypabuild.install_reqs({}, env, reqs)  # type: ignore[arg-type]
    for req in reqs:
        assert req in env.installed

    pypabuild.install_reqs({}, env, set(BASE_IGNORED_REQUIREMENTS))  # type: ignore[arg-type]
    for req in BASE_IGNORED_REQUIREMENTS:
        assert req not in env.installed


def test_make_command_wrapper_symlinks(tmp_path, dummy_xbuildenv):
    symlink_dir = tmp_path
    env = pypabuild.make_command_wrapper_symlinks(symlink_dir)

    wrapper = symlink_dir / "pywasmcross.py"
    assert wrapper.exists()
    assert not wrapper.is_symlink()
    assert wrapper.stat().st_mode & 0o755 == 0o755

    for key, path in env.items():
        symlink_path = symlink_dir / path

        assert symlink_path.exists()
        assert symlink_path.is_symlink()
        assert symlink_path.name in pywasmcross.SYMLINKS
        assert key in pypabuild.SYMLINK_ENV_VARS.values()


def test_make_command_wrapper_symlinks_f2c_wrapper(
    tmp_path, dummy_xbuildenv, reset_env_vars, reset_cache
):
    import os

    dummy_f2c_wrapper = tmp_path / "_dummy_f2c_fixes.py"
    dummy_f2c_wrapper.write_text("print('Hello, world!')")

    os.environ["_F2C_FIXES_WRAPPER"] = str(dummy_f2c_wrapper)

    symlink_dir = tmp_path
    pypabuild.make_command_wrapper_symlinks(symlink_dir)

    wrapper = symlink_dir / "_f2c_fixes.py"
    assert wrapper.exists()
    assert wrapper.read_text() == dummy_f2c_wrapper.read_text()


def test_get_build_env(tmp_path, dummy_xbuildenv):
    build_env_ctx = pypabuild.get_build_env(
        env={"PATH": ""},
        pkgname="",
        cflags="",
        cxxflags="",
        ldflags="",
        target_install_dir=str(tmp_path),
        exports="pyinit",
        build_dir=tmp_path,
    )

    with build_env_ctx as env:
        # TODO: also test values
        assert "CC" in env
        assert "CXX" in env
        assert "AR" in env
        assert "PATH" in env
        assert "PYTHONPATH" in env
        assert "PYWASMCROSS_ARGS" in env
        assert "_PYTHON_HOST_PLATFORM" in env
        assert "_PYTHON_SYSCONFIGDATA_NAME" in env

        wasmcross_args = env["PYWASMCROSS_ARGS"]
        assert "cflags" in wasmcross_args
        assert "cxxflags" in wasmcross_args
        assert "ldflags" in wasmcross_args
        assert "exports" in wasmcross_args
def test_symlink_unisolated_packages_triggers_lazy_install(
    tmp_path, dummy_xbuildenv, monkeypatch, reset_env_vars, reset_cache
):
    called = {"count": 0}

    def _ensure(self):
        called["count"] += 1

    monkeypatch.setattr(
        "pyodide_build.xbuildenv.CrossBuildEnvManager.ensure_cross_build_packages_installed",
        _ensure,
    )

    from pyodide_build import pypabuild
    from pyodide_build.build_env import get_hostsitepackages

    host_site_packages = Path(get_hostsitepackages())
    shutil.rmtree(host_site_packages, ignore_errors=True)
    host_site_packages.mkdir(parents=True, exist_ok=True)

    class DummyEnv:
        path = str(tmp_path / "venv")

    pypabuild.symlink_unisolated_packages(DummyEnv())
    assert called["count"] == 1

