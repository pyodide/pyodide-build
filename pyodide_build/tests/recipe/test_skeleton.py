import os
from pathlib import Path
from textwrap import dedent

import pytest
from packaging import version

from pyodide_build.recipe import skeleton
from pyodide_build.recipe.spec import MetaConfig

# Following tests make real network calls to the PyPI JSON API.
# Since the response is fully cached, and small, it is very fast and is
# unlikely to fail.


@pytest.mark.parametrize("source_fmt", ["wheel", "sdist"])
def test_mkpkg(tmpdir, capsys, source_fmt):
    base_dir = Path(str(tmpdir))

    skeleton.make_package(base_dir, "idna", None, source_fmt)
    assert os.listdir(base_dir) == ["idna"]
    meta_path = base_dir / "idna" / "meta.yaml"
    assert meta_path.exists()
    captured = capsys.readouterr()
    assert "Output written to" in captured.out
    assert str(meta_path) in captured.out

    db = MetaConfig.from_yaml(meta_path)

    assert db.package.name == "idna"
    assert db.source.url is not None
    if source_fmt == "wheel":
        assert db.source.url.endswith(".whl")
    else:
        assert db.source.url.endswith(".tar.gz")


@pytest.mark.parametrize("old_dist_type", ["wheel", "sdist"])
@pytest.mark.parametrize("new_dist_type", ["wheel", "sdist", "same"])
def test_mkpkg_update(tmpdir, old_dist_type, new_dist_type):
    base_dir = Path(str(tmpdir))

    old_ext = ".tar.gz" if old_dist_type == "sdist" else ".whl"
    old_url = "https://<some>/idna-2.0" + old_ext
    db_init = MetaConfig(
        package={"name": "idna", "version": "2.0"},
        source={
            "sha256": "b307872f855b18632ce0c21c5e45be78c0ea7ae4c15c828c20788b26921eb3f6",
            "url": old_url,
        },
        test={"imports": ["idna"]},
    )

    package_dir = base_dir / "idna"
    package_dir.mkdir(parents=True)
    meta_path = package_dir / "meta.yaml"
    db_init.to_yaml(meta_path)
    source_fmt = new_dist_type
    if new_dist_type == "same":
        source_fmt = None
    skeleton.update_package(base_dir, "idna", source_fmt=source_fmt)

    db = MetaConfig.from_yaml(meta_path)
    assert version.parse(db.package.version) > version.parse(db_init.package.version)
    assert db.source.url is not None
    if new_dist_type == "wheel":
        assert db.source.url.endswith(".whl")
    elif new_dist_type == "sdist":
        assert db.source.url.endswith(".tar.gz")
    else:
        assert db.source.url.endswith(old_ext)


def test_enable_disable(tmpdir):
    base_dir = Path(str(tmpdir))

    disabled = dedent(
        """\
        package:
          name: jedi
          version: 0.19.1
          # Here is some information
          _disabled: true
          top-level:
            - jedi
        source:
          sha256: shasum
          url: aurlhere
        requirements:
          run:
            - parso
        about:
          home: https://github.com/davidhalter/jedi
          PyPI: https://pypi.org/project/jedi
          summary: An autocompletion tool for Python that can be used for text editors.
          license: MIT
        """
    ).strip()
    enabled_lines = disabled.splitlines()
    del enabled_lines[3:5]
    enabled = "\n".join(enabled_lines)

    package_dir = base_dir / "jedi"
    package_dir.mkdir(parents=True)
    meta_path = package_dir / "meta.yaml"
    meta_path.write_text(disabled)
    skeleton.enable_package(base_dir, "jedi")
    assert meta_path.read_text().strip() == enabled
    skeleton.disable_package(base_dir, "jedi", "Here is some information")
    assert meta_path.read_text().strip() == disabled


def test_mkpkg_update_pinned(tmpdir):
    base_dir = Path(str(tmpdir))

    db_init = MetaConfig(
        package={"name": "idna", "version": "2.0", "pinned": True},
        source={
            "sha256": "b307872f855b18632ce0c21c5e45be78c0ea7ae4c15c828c20788b26921eb3f6",
            "url": "https://<some>/idna-2.0.whl",
        },
        test={"imports": ["idna"]},
    )

    package_dir = base_dir / "idna"
    package_dir.mkdir(parents=True)
    meta_path = package_dir / "meta.yaml"
    db_init.to_yaml(meta_path)
    with pytest.raises(skeleton.MkpkgSkipped, match="pinned"):
        skeleton.update_package(base_dir, "idna")
    skeleton.update_package(base_dir, "idna", update_pinned=True)
