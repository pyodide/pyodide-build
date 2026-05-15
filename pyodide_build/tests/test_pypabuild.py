import subprocess

import pytest
from build import BuildBackendException, BuildException, FailedProcessError

from pyodide_build import pypabuild, pywasmcross
from pyodide_build.constants import BASE_IGNORED_REQUIREMENTS
from pyodide_build.vendor._pypabuild import (
    _find_called_process_error,
    _handle_build_error,
    _log_subprocess_output,
)


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
    monkeypatch.setattr(
        "pyodide_build.build_env.get_unisolated_packages",
        lambda: ["numpy"],
    )

    class DummyEnv:
        path = str(tmp_path / "venv")

    pypabuild.symlink_unisolated_packages(DummyEnv(), reqs={"numpy>=1.0"})
    assert called["count"] == 1


def _make_cpe(
    stdout: str | bytes | None = None, stderr: str | bytes | None = None
) -> subprocess.CalledProcessError:
    exc = subprocess.CalledProcessError(1, ["pip", "install", "bad-pkg"])
    exc.stdout = stdout
    exc.stderr = stderr
    return exc


class TestFindCalledProcessError:
    def test_direct_called_process_error(self):
        cpe = _make_cpe()
        assert _find_called_process_error(cpe) is cpe

    def test_wrapped_in_failed_process_error(self):
        cpe = _make_cpe()
        fpe = FailedProcessError(cpe, "install failed")
        assert _find_called_process_error(fpe) is cpe

    def test_wrapped_in_build_backend_exception(self):
        cpe = _make_cpe()
        bbe = BuildBackendException(cpe)
        assert _find_called_process_error(bbe) is cpe

    def test_unrelated_exception(self):
        assert _find_called_process_error(RuntimeError("boom")) is None

    def test_build_exception_without_inner(self):
        assert _find_called_process_error(BuildException("bad")) is None


class TestLogSubprocessOutput:
    def test_logs_str_output(self, capsys):
        cpe = _make_cpe(stdout="pkg not found\n", stderr="ERROR: no match\n")
        _log_subprocess_output(cpe)
        captured = capsys.readouterr().out
        assert "pkg not found" in captured
        assert "ERROR: no match" in captured
        assert "stdout:" in captured
        assert "stderr:" in captured

    def test_logs_bytes_output(self, capsys):
        cpe = _make_cpe(stdout=b"bytes stdout\n", stderr=b"bytes stderr\n")
        _log_subprocess_output(cpe)
        captured = capsys.readouterr().out
        assert "bytes stdout" in captured
        assert "bytes stderr" in captured

    def test_no_output(self, capsys):
        cpe = _make_cpe()
        _log_subprocess_output(cpe)
        captured = capsys.readouterr().out
        assert captured == ""


class TestHandleBuildErrorSubprocessOutput:
    def test_called_process_error_surfaces_output(self, capsys):
        with pytest.raises(SystemExit):
            with _handle_build_error():
                raise _make_cpe(
                    stdout="Collecting bad-pkg\n",
                    stderr="ERROR: No matching distribution found for bad-pkg\n",
                )
        captured = capsys.readouterr()
        assert "Collecting bad-pkg" in captured.out
        assert "No matching distribution found for bad-pkg" in captured.out

    def test_failed_process_error_surfaces_output(self, capsys):
        cpe = _make_cpe(stderr="pip resolution failed\n")
        with pytest.raises(SystemExit):
            with _handle_build_error():
                raise FailedProcessError(cpe, "Failed to install deps")
        captured = capsys.readouterr()
        assert "pip resolution failed" in captured.out

    def test_build_backend_exception_with_cpe_surfaces_output(self, capsys):
        cpe = _make_cpe(stderr="backend install error\n")
        with pytest.raises(SystemExit):
            with _handle_build_error():
                raise BuildBackendException(cpe)
        captured = capsys.readouterr()
        assert "backend install error" in captured.out
