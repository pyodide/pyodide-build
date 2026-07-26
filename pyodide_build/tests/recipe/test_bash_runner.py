import subprocess
from pathlib import Path

import pytest

from pyodide_build.recipe import bash_runner


def test_subprocess_with_shared_env_1():
    with bash_runner.BashRunnerWithSharedEnvironment() as p:
        p.env.pop("A", None)

        res = p.run_unchecked("A=6; echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "6\n"
        assert p.env.get("A", None) is None

        p.run_unchecked("export A=2")
        assert p.env["A"] == "2"

        res = p.run_unchecked("echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "2\n"

        res = p.run_unchecked("A=6; echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "6\n"
        assert p.env.get("A", None) == "6"

        p.env["A"] = "7"
        res = p.run_unchecked("echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "7\n"
        assert p.env["A"] == "7"


def _run_with_watchdog(func, timeout=30):
    """Run ``func`` in a thread, failing the test if it does not return in time.

    Used to detect a regression where ``run_unchecked`` would block forever.
    """
    import threading

    result: dict[str, object] = {}

    def target():
        result["value"] = func()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        pytest.fail(f"run_unchecked did not return within {timeout}s (hung)")
    return result.get("value")


def test_run_unchecked_exit_zero_does_not_hang():
    """A script that exits the shell early (e.g. ``exit 0``) must not hang.

    The env-dump command appended after the user script never runs in this
    case, so the parent must detect EOF on the pipe instead of blocking
    forever waiting for an environment dump that never arrives.
    See https://github.com/pyodide/pyodide-build/issues/376.
    """

    def body():
        with bash_runner.BashRunnerWithSharedEnvironment() as p:
            p.env["MARKER"] = "kept"

            res = p.run_unchecked("echo hi; exit 0", stdout=subprocess.PIPE)
            assert res.returncode == 0
            assert res.stdout == "hi\n"
            # The script exited the shell before dumping its env, so the
            # previous environment is preserved and remains usable.
            assert p.env["MARKER"] == "kept"

            # A normal script afterwards still works and updates the env.
            res = p.run_unchecked("export AFTER=1; echo $AFTER", stdout=subprocess.PIPE)
            assert res.returncode == 0
            assert res.stdout == "1\n"
            assert p.env["AFTER"] == "1"
            assert p.env["MARKER"] == "kept"

    _run_with_watchdog(body)


def test_run_unchecked_does_not_leak_fds():
    """Repeated invocations must not leak file descriptors."""
    import resource

    with bash_runner.BashRunnerWithSharedEnvironment() as p:
        for _ in range(200):
            p.run_unchecked("echo hi; exit 0", stdout=subprocess.PIPE)
            p.run_unchecked("export X=1", stdout=subprocess.PIPE)

        soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        # We should be nowhere near the open-file limit after 400 calls if fds
        # are properly closed each time.
        assert len(list(Path("/dev/fd").iterdir())) < soft_limit


def test_subprocess_with_shared_env_cwd(tmp_path: Path) -> None:
    src_dir = tmp_path / "build/package_name"
    src_dir.mkdir(parents=True)
    script = "touch out.txt"
    with bash_runner.BashRunnerWithSharedEnvironment() as shared_env:
        shared_env.run_unchecked(script, cwd=src_dir)
        assert (src_dir / "out.txt").exists()


def test_subprocess_with_shared_env_logging(capfd, tmp_path):
    from pytest import raises

    with bash_runner.BashRunnerWithSharedEnvironment() as p:
        p.run("echo 1000", script_name="a test script")
        cap = capfd.readouterr()
        assert [l.strip() for l in cap.out.splitlines()] == [
            f"Running a test script in {Path.cwd()}",
            "1000",
        ]
        assert cap.err == ""

        dir = tmp_path / "a"
        dir.mkdir()
        p.run("echo 1000", script_name="test script", cwd=dir)
        cap = capfd.readouterr()

        # Clean output and compare to expected lines, and join any
        # potential split lines to handle platform differences we've
        # noticed (across macOS and Linux).
        output_lines = [l.strip() for l in cap.out.splitlines()]
        cleaned_output = "".join(output_lines)

        assert "Running test script in" in cleaned_output
        assert str(dir) in cleaned_output
        assert "1000" in cleaned_output
        assert cap.err == ""

        dir = tmp_path / "b"
        dir.mkdir()
        with raises(SystemExit) as e:
            p.run("exit 7", script_name="test2 script", cwd=dir)
        cap = capfd.readouterr()
        assert e.value.args[0] == 7

        output_lines = [l.strip() for l in cap.out.splitlines()]
        cleaned_output = "".join(output_lines)

        assert "Running test2 script in" in cleaned_output
        assert str(dir) in cleaned_output
        assert "ERROR: test2 script failed" in cap.err


def test_get_bash_runner_does_not_mutate_cached_env(dummy_xbuildenv):
    """``get_build_environment_vars`` is cached and returns the cached dict.

    ``get_bash_runner`` must copy it before injecting per-package variables,
    otherwise those variables leak into the cached value and are seen by
    subsequent package builds in the same process.
    See https://github.com/pyodide/pyodide-build/issues/376.
    """
    from pyodide_build.build_env import (
        get_build_environment_vars,
        get_pyodide_root,
    )

    pyodide_root = get_pyodide_root()
    cached_env = get_build_environment_vars(pyodide_root)
    cached_keys_before = set(cached_env)

    extra = {"PKGDIR": "/tmp/pkg1", "PKG_VERSION": "1.2.3", "LEAKED_MARKER": "1"}
    with bash_runner.get_bash_runner(extra) as runner:
        # The runner sees the injected variables ...
        assert runner.env["PKGDIR"] == "/tmp/pkg1"
        assert runner.env["LEAKED_MARKER"] == "1"

    # ... but the cached dict is untouched.
    assert "LEAKED_MARKER" not in cached_env
    assert set(cached_env) == cached_keys_before
    # And re-fetching returns the same pristine cached dict.
    assert "LEAKED_MARKER" not in get_build_environment_vars(pyodide_root)
