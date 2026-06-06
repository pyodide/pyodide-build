from typing import Literal

from pyodide_build.out_of_tree import build


def test_non_platformed_build(dummy_xbuildenv, tmp_path):
    """Check that we don't accidentally attach Pyodide platform to non
    platformed wheels.
    """

    (tmp_path / "pyproject.toml").write_text(
        """\
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
    )
    (tmp_path / "fake_pkg.py").write_text("print('hi from fake_pkg!')")
    src = tmp_path
    dst = tmp_path / "dist"
    exports: Literal["pyinit"] = "pyinit"
    config_settings = {}  # type:ignore[var-annotated]
    build.run(src, dst, exports, config_settings)

    wheels = list(dst.glob("*.whl"))
    assert len(wheels) == 1
    assert wheels[0].name == "fake_pkg-1.0-py3-none-any.whl"


def test_get_requires_for_build_not_retried_on_empty_result(
    dummy_xbuildenv, tmp_path, monkeypatch
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

    (tmp_path / "pyproject.toml").write_text(
        """\
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
    )
    (tmp_path / "fake_pkg.py").write_text("")
    build.run(tmp_path, tmp_path / "dist", "pyinit", {})

    assert call_count[0] == 1, (
        f"get_requires_for_build called {call_count[0]} times but expected 1"
    )
