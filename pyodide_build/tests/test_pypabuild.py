import os
import subprocess
from collections.abc import Sequence

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


def test_replace_unisolated_packages():
    requires = {"foo", "bar<1.0", "baz==1.0", "qux"}
    unisolated = {
        "foo": "2.0",
        "bar": "0.5",
        "baz": "1.0",
    }

    new_requires, replaced = pypabuild._replace_unisolated_packages(
        requires, unisolated
    )
    assert new_requires == {"foo==2.0", "bar==0.5", "baz==1.0", "qux"}
    assert replaced == {"foo", "bar", "baz"}


def test_replace_unisolated_packages_normalizes_names():
    requires = {"NumPy>=1.20", "Ruamel-YAML"}
    unisolated = {
        "numpy": "2.0.3",
        "ruamel.yaml": "0.18.6",
    }

    new_requires, replaced = pypabuild._replace_unisolated_packages(
        requires, unisolated
    )
    assert new_requires == {"numpy==2.0.3", "ruamel.yaml==0.18.6"}
    assert replaced == {"numpy", "ruamel.yaml"}


def test_replace_unisolated_packages_version_mismatch():
    requires = {"baz==1.0"}
    unisolated = {
        "baz": "1.1",
    }

    with pytest.warns(UserWarning, match=r"cross-build version is baz==1\.1"):
        new_requires, replaced = pypabuild._replace_unisolated_packages(
            requires, unisolated
        )
    assert new_requires == {"baz==1.1"}
    assert replaced == {"baz"}


@pytest.mark.parametrize(
    "reqstr",
    [
        "oldest-supported-numpy",
        "oldest-supported-numpy>=2021.6.17",
        "Oldest-Supported-NumPy",
    ],
)
def test_replace_unisolated_packages_rejects_oldest_supported_numpy(reqstr):
    with pytest.raises(ValueError, match="oldest-supported-numpy is deprecated"):
        pypabuild._replace_unisolated_packages({reqstr}, {"numpy": "2.0.3"})


def test_replace_unisolated_packages_oldest_supported_numpy_marker_not_applicable():
    requires = {"oldest-supported-numpy; python_version<'3.0'"}

    new_requires, replaced = pypabuild._replace_unisolated_packages(requires, {})
    assert new_requires == requires
    assert replaced == set()


def test_install_reqs(tmp_path, dummy_xbuildenv, monkeypatch):
    monkeypatch.setattr(pypabuild, "_install_cross_build_files", lambda *a, **kw: None)
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


def test_install_reqs_triggers_lazy_install(tmp_path, monkeypatch):
    called = {"count": 0, "packages": None}

    class DummyManager:
        def ensure_cross_build_packages_installed(self, packages):
            called["count"] += 1
            called["packages"] = set(packages)

    monkeypatch.setattr(pypabuild, "in_xbuildenv", lambda: True)
    monkeypatch.setattr(pypabuild, "get_current_xbuildenv_manager", DummyManager)
    monkeypatch.setattr(
        pypabuild,
        "get_unisolated_packages",
        lambda: {"numpy": "1.0", "scipy": "2.0"},
    )
    monkeypatch.setattr(pypabuild, "_install_cross_build_files", lambda *a, **kw: None)

    env = MockIsolatedEnv(tmp_path)
    pypabuild.install_reqs({}, env, {"numpy>=1.0"})

    assert called["count"] == 1
    # Only the cross-build packages that are actually build dependencies get
    # installed; scipy is not requested so it is left alone.
    assert called["packages"] == {"numpy"}


def test_install_reqs_skips_lazy_install_when_not_unisolated(tmp_path, monkeypatch):
    called = {"count": 0}

    class DummyManager:
        def ensure_cross_build_packages_installed(self, packages):
            called["count"] += 1

    monkeypatch.setattr(pypabuild, "in_xbuildenv", lambda: True)
    monkeypatch.setattr(pypabuild, "get_current_xbuildenv_manager", DummyManager)
    monkeypatch.setattr(pypabuild, "get_unisolated_packages", lambda: {"numpy": "1.0"})
    monkeypatch.setattr(pypabuild, "_install_cross_build_files", lambda *a, **kw: None)

    env = MockIsolatedEnv(tmp_path)
    pypabuild.install_reqs({}, env, {"foo>=1.0"})

    assert called["count"] == 0


def test_install_cross_build_files(tmp_path, monkeypatch):
    purelib = tmp_path / "venv" / "lib" / "site-packages"
    purelib.mkdir(parents=True)

    extras = tmp_path / "site-packages-extras"
    numpy_header = extras / "numpy" / "_core" / "include" / "numpy" / "ndarrayobject.h"
    numpy_header.parent.mkdir(parents=True)
    numpy_header.write_text("// header")
    scipy_pxd = extras / "scipy" / "linalg" / "cython_blas.pxd"
    scipy_pxd.parent.mkdir(parents=True)
    scipy_pxd.write_text("# pxd")

    monkeypatch.setattr(
        pypabuild,
        "_find_executable_and_scripts",
        lambda venv_path: ("python", "scripts", str(purelib)),
    )
    monkeypatch.setattr(
        pypabuild, "get_cross_build_files_dir", lambda name: extras / name
    )

    pypabuild._install_cross_build_files(str(tmp_path / "venv"), {"numpy", "scipy"})

    assert (
        purelib / "numpy" / "_core" / "include" / "numpy" / "ndarrayobject.h"
    ).read_text() == "// header"
    assert (purelib / "scipy" / "linalg" / "cython_blas.pxd").read_text() == "# pxd"


def test_install_cross_build_files_skips_packages_without_cross_build_files(
    tmp_path, monkeypatch
):
    purelib = tmp_path / "venv" / "lib" / "site-packages"
    purelib.mkdir(parents=True)

    monkeypatch.setattr(
        pypabuild,
        "_find_executable_and_scripts",
        lambda venv_path: ("python", "scripts", str(purelib)),
    )
    monkeypatch.setattr(
        pypabuild,
        "get_cross_build_files_dir",
        lambda name: tmp_path / "does-not-exist" / name,
    )

    pypabuild._install_cross_build_files(str(tmp_path / "venv"), {"some-package"})

    assert list(purelib.iterdir()) == []


def test_install_cross_build_files_skips_when_no_unisolated_packages(
    tmp_path, monkeypatch
):
    def _unexpected_call(*args, **kwargs):
        raise AssertionError("should not be called when there are no unisolated reqs")

    monkeypatch.setattr(pypabuild, "_find_executable_and_scripts", _unexpected_call)
    monkeypatch.setattr(pypabuild, "get_cross_build_files_dir", _unexpected_call)

    pypabuild._install_cross_build_files(str(tmp_path / "venv"), set())


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


@pytest.mark.parametrize("verbosity", [0, 1, 2])
def test_build_sets_ctx_verbosity(tmp_path, dummy_xbuildenv, monkeypatch, verbosity):
    """pypabuild.build() must set build._ctx.VERBOSITY before calling the builder."""
    from build import _ctx as _build_ctx

    observed: list[int] = []

    def _fake_isolated(
        build_env,
        srcdir,
        outdir,
        distribution,
        config_settings,
        verbosity=0,
        extra_build_requires=(),
    ):
        observed.append(_build_ctx.VERBOSITY.get())
        return os.path.join(outdir, "pkg-1.0-py3-none-any.whl")

    monkeypatch.setattr(pypabuild, "_build_in_isolated_env", _fake_isolated)

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
        pypabuild.build(tmp_path, tmp_path / "dist", env, {}, verbosity=verbosity)

    assert observed == [verbosity]


def test_build_forwards_extra_build_requires(tmp_path, dummy_xbuildenv, monkeypatch):
    """pypabuild.build() must pass extra_build_requires through to the isolated env."""
    observed: list[Sequence[str]] = []

    def _fake_isolated(
        build_env,
        srcdir,
        outdir,
        distribution,
        config_settings,
        verbosity=0,
        extra_build_requires=(),
    ):
        observed.append(extra_build_requires)
        return os.path.join(outdir, "pkg-1.0-py3-none-any.whl")

    monkeypatch.setattr(pypabuild, "_build_in_isolated_env", _fake_isolated)

    pypabuild.build(
        tmp_path,
        tmp_path / "dist",
        {"PATH": ""},
        {},
        extra_build_requires=["cython", "pkgconfig"],
    )

    assert observed == [["cython", "pkgconfig"]]


def _patch_isolated_build(monkeypatch, tmp_path):
    """Stub out everything _build_in_isolated_env needs except install_reqs.

    Returns the MockIsolatedEnv that the stubbed _DefaultIsolatedEnv yields.
    """
    env = MockIsolatedEnv(str(tmp_path / "isolated"))

    class DummyIsolatedEnv:
        def __init__(self, installer):
            pass

        def __enter__(self):
            return env

        def __exit__(self, *args):
            return None

    class DummyProjectBuilder:
        build_system_requires = {"setuptools"}

        @classmethod
        def from_isolated_env(cls, isolated_env, srcdir, runner=None):
            return cls()

        def get_requires_for_build(self, distribution, config_settings=None):
            return {"wheel"}

        def build(self, distribution, outdir, config_settings):
            return os.path.join(outdir, "pkg-1.0-py3-none-any.whl")

    monkeypatch.setattr(pypabuild, "_DefaultIsolatedEnv", DummyIsolatedEnv)
    monkeypatch.setattr(pypabuild, "ProjectBuilder", DummyProjectBuilder)
    monkeypatch.setattr(
        pypabuild, "_copy_sysconfigdata_to_isolated_env", lambda env: None
    )
    monkeypatch.setattr(pypabuild, "_get_unisolated_pkgconfig_dirs", lambda path: [])
    return env


def test_build_in_isolated_env_installs_extra_build_requires(
    tmp_path, monkeypatch, reset_env_vars
):
    """extra_build_requires must be installed along with the build system requires."""
    installed: list[set[str]] = []

    _patch_isolated_build(monkeypatch, tmp_path)
    monkeypatch.setattr(
        pypabuild,
        "install_reqs",
        lambda build_env, env, reqs: installed.append(set(reqs)),
    )

    wheel = pypabuild._build_in_isolated_env(
        {"PATH": ""},
        tmp_path,
        str(tmp_path / "dist"),
        "wheel",
        {},
        extra_build_requires=["cython", "pkgconfig"],
    )

    assert wheel.endswith("pkg-1.0-py3-none-any.whl")
    # The extra build requires are installed with the build system requires,
    # and again with the dynamic requirements reported by the backend
    assert installed == [
        {"setuptools", "cython", "pkgconfig"},
        {"wheel", "cython", "pkgconfig"},
    ]


def test_build_in_isolated_env_extra_build_requires_with_markers(
    tmp_path, dummy_xbuildenv, monkeypatch, reset_env_vars, reset_cache
):
    """extra_build_requires may carry PEP 508 markers.

    Requirements with markers must survive requirement rewriting, except that:
     - a marked requirement matching an unisolated package is still pinned to
       the cross-build version,
     - a marked requirement that is ignored is still dropped when its marker
       applies.
    """
    env = _patch_isolated_build(monkeypatch, tmp_path)
    monkeypatch.setattr(pypabuild, "in_xbuildenv", lambda: False)
    monkeypatch.setattr(
        pypabuild, "get_unisolated_packages", lambda: {"numpy": "2.0.3"}
    )
    monkeypatch.setattr(pypabuild, "_install_cross_build_files", lambda *a, **kw: None)

    pypabuild._build_in_isolated_env(
        {"PATH": ""},
        tmp_path,
        str(tmp_path / "dist"),
        "wheel",
        {},
        extra_build_requires=[
            'cython; python_version >= "3.0"',
            'pkgconfig; python_version < "3.0"',
            'numpy>=1.20; python_version >= "3.0"',
            'patchelf; python_version >= "3.0"',
            'patchelf; python_version < "3.0"',
        ],
    )

    assert env.installed == {
        "setuptools",
        "wheel",
        # applicable and non-applicable markers are both passed through
        'cython; python_version >= "3.0"',
        'pkgconfig; python_version < "3.0"',
        # unisolated package pinned to the cross-build version
        "numpy==2.0.3",
        # ignored requirement dropped only when its marker applies
        'patchelf; python_version < "3.0"',
    }
