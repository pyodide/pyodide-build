from typing import Literal

import pytest

from pyodide_build.out_of_tree import build

FAKE_PYPROJECT_TOML = """\
[build-system]
build-backend = "hatchling.build"
requires = ["hatchling<1.22"]

[project]
requires-python = ">=3.10"
name = "fake-pkg"
version = "1.0"

[tool.hatch.build.targets.wheel]
packages = ["fake_pkg"]
"""


@pytest.fixture
def fake_pkg(tmp_path):
    (tmp_path / "pyproject.toml").write_text(FAKE_PYPROJECT_TOML)
    (tmp_path / "fake_pkg.py").write_text("print('hi from fake_pkg!')")
    return tmp_path


def test_non_platformed_build(dummy_xbuildenv, fake_pkg):
    """Check that we don't accidentally attach Pyodide platform to non
    platformed wheels.
    """
    dst = fake_pkg / "dist"
    exports: Literal["pyinit"] = "pyinit"
    config_settings = {}  # type:ignore[var-annotated]
    build.run(fake_pkg, dst, exports, config_settings)

    wheels = list(dst.glob("*.whl"))
    assert len(wheels) == 1
    assert wheels[0].name == "fake_pkg-1.0-py3-none-any.whl"


@pytest.mark.parametrize("verbosity", [0, 1, 2])
def test_build_verbosity_output(dummy_xbuildenv, fake_pkg, capfd, verbosity):
    """
    This test checks that the stderr output at each verbosity level is correct.
    1. Building at any verbosity level from 0 to 2 must succeed in producing a wheel,
       and show the expected pypa/build step messages (like "Building wheel...") on stderr.
    2.a. At verbosity level 1 or higher, the backend subprocess command lines (i.e., the
       PEP 517 pyproject_hook invocations) and the installer commands should appear and be
       printed as a "> cmd" prefix to stderr.
    2.b. The output from the installer should appear as "< output" lines.
    3. At build verbosity level 2 or higher, the installer command should include the "-v" flag
    that pypa/build
       passes along to the installer. See:
       - _UvBackend: https://github.com/pypa/build/blob/615d04cfc52ac3c1592a463f0afe484fee1cc368/src/build/env.py#L418-L419
       - _PipBackend: https://github.com/pypa/build/blob/dcfa865c7150426e01eccc494dc22a55849ecad2/src/build/env.py#L352-L353
    4. At verbosity 0, nothing should happen, except for the step messages from point 1.
    """
    dst = fake_pkg / "dist"
    build.run(fake_pkg, dst, "pyinit", {}, verbosity=verbosity)
    captured = capfd.readouterr()
    err = captured.err
    stderr_lines = err.splitlines()

    wheels = list(dst.glob("*.whl"))
    assert len(wheels) == 1, "build must produce a wheel at every verbosity level"

    # Both step messages must appear at every verbosity level.
    assert "Getting build dependencies for wheel" in err, (
        f"Expected 'Getting build dependencies for wheel' at verbosity={verbosity}"
    )
    assert "Building wheel" in err, (
        f"Expected 'Building wheel' step message at verbosity={verbosity}"
    )

    cmd_lines = [line for line in stderr_lines if line.startswith("> ")]
    out_lines = [line for line in stderr_lines if line.startswith("< ")]

    if verbosity >= 1:
        # Both PEP 517 hooks must appear
        assert any("get_requires_for_build_wheel" in line for line in cmd_lines)
        assert any("build_wheel" in line for line in cmd_lines)
        # Installer command must appear
        assert any("pip" in line or "uv" in line for line in cmd_lines)
        # Output from the installer must appear
        assert out_lines
    # At zero verbosity, nothing should appear except the step messages (which we check above).
    else:
        assert not cmd_lines
        assert not out_lines

    if verbosity >= 2:
        assert any(
            ("-v" in line) and ("pip" in line or "uv" in line) for line in cmd_lines
        )


def test_get_requires_for_build_not_retried_on_empty_result(
    dummy_xbuildenv, fake_pkg, monkeypatch
):
    """Regression test for https://github.com/pyodide/pyodide-build/pull/364"""
    from build import ProjectBuilder

    orig = ProjectBuilder.get_requires_for_build
    call_count = [0]

    def get_count_for_pep517_requires(self, distribution, config_settings=None):
        call_count[0] += 1
        return orig(self, distribution, config_settings)

    monkeypatch.setattr(
        ProjectBuilder, "get_requires_for_build", get_count_for_pep517_requires
    )

    build.run(fake_pkg, fake_pkg / "dist", "pyinit", {})

    assert call_count[0] == 1, (
        f"get_requires_for_build called {call_count[0]} times but expected 1"
    )
