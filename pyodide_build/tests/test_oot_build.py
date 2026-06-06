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
    This test checks for two things:
    1. Building at any verbosity level from 0 to 2 must succeed in producing a wheel,
       and show the expected pypa/build step messages (like "Building wheel...") on stderr.
    2. At verbosity level 1 or higher, the backend subprocess command lines, i.e., the
       pyproject_hook invocations that are printed with a "> " prefix to stderr, should
       appear. At verbosity 0, they should not.
    """
    dst = fake_pkg / "dist"
    build.run(fake_pkg, dst, "pyinit", {}, verbosity=verbosity)
    captured = capfd.readouterr()
    err = captured.err

    wheels = list(dst.glob("*.whl"))
    assert len(wheels) == 1, "build must produce a wheel at every verbosity level"

    assert "Building wheel" in err, (
        f"Expected 'Building wheel' step message at verbosity={verbosity}"
    )

    # The pyproject_hooks invocation is printed with "> " prefix to stderr only
    # when verbosity >= 1 (mirrors pypa/build's "> cmd" formatting).
    if verbosity >= 1:
        assert "> " in err, (
            f"Expected '> cmd' backend call line on stderr at verbosity={verbosity}"
        )
    else:
        # At verbosity=0, no subprocess command lines should appear on stderr
        # (step messages appear, but not the "> cmd" prefix lines)
        assert not any(line.startswith("> ") for line in err.splitlines()), (
            "Did not expect '> cmd' lines on stderr at 0 verbosity"
        )
