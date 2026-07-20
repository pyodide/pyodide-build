import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from packaging import version

from pyodide_build.recipe import skeleton
from pyodide_build.recipe.skeleton import (
    MetadataDict,
    MkpkgFailedException,
    URLDict,
    _find_dist,
    _make_predictable_url,
    update_package,
)
from pyodide_build.recipe.spec import MetaConfig

# Following tests make real network calls to the PyPI JSON API.
# Since the response is fully cached, and small, it is very fast and is
# unlikely to fail.


@pytest.mark.parametrize("source_fmt", ["wheel", "sdist"])
def test_mkpkg(tmpdir, capsys, source_fmt):
    import re

    base_dir = Path(str(tmpdir))

    skeleton.make_package(base_dir, "idna", None, source_fmt)
    assert os.listdir(base_dir) == ["idna"]
    meta_path = base_dir / "idna" / "meta.yaml"
    assert meta_path.exists()
    captured = capsys.readouterr()
    assert "Output written to" in captured.out

    # this test checks for outputs across multiple paths. so, we
    # find the paths in the output, ignoring ANSI color codes and
    # handling line breaks + normalised paths (only for this test).
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    cleaned_output = ansi_escape.sub("", captured.out)

    cleaned_output = cleaned_output.replace("\n", "")
    path_str = str(meta_path)

    path_parts = path_str.split(os.sep)
    for part in path_parts[-3:]:
        assert part in cleaned_output


def test_lookup_gh_username(monkeypatch):
    @dataclass
    class MockResult:
        returncode: int
        stdout: str
        stderr: str

    mock_result = None

    def mock_run(*args, **kwargs):
        return mock_result

    monkeypatch.setattr(subprocess, "run", mock_run)

    mock_result = MockResult(
        0,
        dedent("""\
            github.com
              ✓ Logged in to github.com account some_gh_username (/home/uname/.config/gh/hosts.yml)
              - Active account: true
              - Git operations protocol: ssh
              - Token: gho_************************************
              - Token scopes: 'admin:public_key', 'gist', 'read:org', 'repo'
        """),
        "",
    )
    assert skeleton.lookup_gh_username() == "some_gh_username"
    mock_result = MockResult(
        1,
        "",
        "You are not logged into any GitHub hosts. To log in, run: gh auth login\n",
    )
    with pytest.raises(
        skeleton.MkpkgFailedException,
        match="You are not logged into any GitHub hosts. To log in, run: gh auth login",
    ):
        skeleton.lookup_gh_username()

    def mock_run(*args, **kwargs):
        raise FileNotFoundError("No such file or directory: 'gh'")

    monkeypatch.setattr(subprocess, "run", mock_run)
    with pytest.raises(
        skeleton.MkpkgFailedException,
        match="gh cli is not installed",
    ):
        skeleton.lookup_gh_username()


@pytest.mark.parametrize("old_dist_type", ["wheel", "sdist"])
@pytest.mark.parametrize("new_dist_type", ["wheel", "sdist", "same"])
def test_mkpkg_update(tmpdir, old_dist_type, new_dist_type):
    base_dir = Path(str(tmpdir))

    old_ext = ".tar.gz" if old_dist_type == "sdist" else ".whl"
    old_url = "https://<some>/idna-2.0" + old_ext
    db_init = MetaConfig.from_dict(
        {
            "package": {"name": "idna", "version": "2.0"},
            "source": {
                "sha256": "b307872f855b18632ce0c21c5e45be78c0ea7ae4c15c828c20788b26921eb3f6",
                "url": old_url,
            },
            "test": {"imports": ["idna"]},
        }
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


def test_pin(tmpdir):
    base_dir = Path(str(tmpdir))

    pinned = dedent(
        """\
        package:
          name: jedi
          version: 0.19.1
          # Here is some information
          pinned: true
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
    unpinned_lines = pinned.splitlines()
    del unpinned_lines[3:5]
    unpinned = "\n".join(unpinned_lines)

    package_dir = base_dir / "jedi"
    package_dir.mkdir(parents=True)
    meta_path = package_dir / "meta.yaml"
    meta_path.write_text(unpinned)
    skeleton.pin_package(base_dir, "jedi", "Here is some information")
    assert meta_path.read_text().strip() == pinned


def test_mkpkg_update_pinned(tmpdir):
    base_dir = Path(str(tmpdir))

    db_init = MetaConfig.from_dict(
        {
            "package": {"name": "idna", "version": "2.0", "pinned": True},
            "source": {
                "sha256": "b307872f855b18632ce0c21c5e45be78c0ea7ae4c15c828c20788b26921eb3f6",
                "url": "https://<some>/idna-2.0.whl",
            },
            "test": {"imports": ["idna"]},
        }
    )

    package_dir = base_dir / "idna"
    package_dir.mkdir(parents=True)
    meta_path = package_dir / "meta.yaml"
    db_init.to_yaml(meta_path)
    with pytest.raises(skeleton.MkpkgSkipped, match="pinned"):
        skeleton.update_package(base_dir, "idna")
    skeleton.update_package(base_dir, "idna", update_pinned=True)


# The following tests check for the behaviour of predictably generating URLs for dists,
# e.g., wheels and sdists, based on the package name, version, and source type.
# The tests are based on the implementation of the _make_predictable_url function.


@pytest.mark.parametrize(
    "package,version,source_type,filename,expected_url",
    [
        # test sdist case
        (
            "numpy",
            "2.0.0",
            "sdist",
            "numpy-2.0.0.tar.gz",
            "https://files.pythonhosted.org/packages/source/n/numpy/numpy-2.0.0.tar.gz",
        ),
        # test wheel
        (
            "sympy",
            "1.13.3",
            "wheel",
            "sympy-1.13.3-py3-none-any.whl",
            "https://files.pythonhosted.org/packages/py3/s/sympy/sympy-1.13.3-py3-none-any.whl",
        ),
        # test wheel with a build tag/number
        (
            "example",
            "1.0.0",
            "wheel",
            "example-1.0.0-1-py3-none-any.whl",
            "https://files.pythonhosted.org/packages/py3/e/example/example-1.0.0-1-py3-none-any.whl",
        ),
        # test package with a dash in the name (real filename has dash, not underscore)
        (
            "scikit-learn",
            "1.6.1",
            "sdist",
            "scikit-learn-1.6.1.tar.gz",
            "https://files.pythonhosted.org/packages/source/s/scikit_learn/scikit-learn-1.6.1.tar.gz",
        ),
        # test universal wheel with py2.py3 tags
        (
            "distlib",
            "0.3.9",
            "wheel",
            "distlib-0.3.9-py2.py3-none-any.whl",
            "https://files.pythonhosted.org/packages/py2.py3/d/distlib/distlib-0.3.9-py2.py3-none-any.whl",
        ),
    ],
    ids=[
        "numpy-sdist",
        "sympy-wheel",
        "example-wheel-build",
        "scikit-learn-sdist",
        "distlib-universal-wheel",
    ],
)
def test_make_predictable_url(package, version, source_type, filename, expected_url):
    """Test that predictable URLs are generated correctly for various package formats."""
    result = _make_predictable_url(package, version, source_type, filename)
    assert result == expected_url


def test_make_predictable_url_invalid_wheel():
    """Test that function raises an InvalidWheelFilename for invalid wheel format."""
    from packaging.utils import InvalidWheelFilename

    with pytest.raises(InvalidWheelFilename):
        _make_predictable_url(
            "invalid", "1.0.0", "wheel", "invalid-1.0.0-invalid-format.whl"
        )


@pytest.mark.parametrize(
    "source_type,package,version,filename,original_url,predictable_url",
    [
        # sdist case
        (
            "sdist",
            "numpy",
            "2.0.0",
            "numpy-2.0.0.tar.gz",
            "https://files.pythonhosted.org/packages/05/35/fb1ada118002df3fe91b5c3b28bc0d90f879b881a5d8f68b1f9b79c44bfe/numpy-2.0.0.tar.gz",
            "https://files.pythonhosted.org/packages/source/n/numpy/numpy-2.0.0.tar.gz",
        ),
        # wheel case
        (
            "wheel",
            "sympy",
            "1.13.3",
            "sympy-1.13.3-py3-none-any.whl",
            "https://files.pythonhosted.org/packages/99/ff/c87e0622b1dadea79d2fb0b25ade9ed98954c9033722eb707053d310d4f3/sympy-1.13.3-py3-none-any.whl",
            "https://files.pythonhosted.org/packages/py3/s/sympy/sympy-1.13.3-py3-none-any.whl",
        ),
    ],
)
def test_find_dist_uses_predictable_url(
    monkeypatch, source_type, package, version, filename, original_url, predictable_url
):
    """Test that _find_dist correctly uses the predictable URL."""

    mock_metadata = MetadataDict(
        info={"name": package, "version": version},
        urls=[],
        releases={},
        last_serial=0,
        vulnerabilities=[],
    )

    packagetype = "sdist" if source_type == "sdist" else "bdist_wheel"

    mock_entry = URLDict(
        comment_text="",
        digests={"sha256": "fakehash123"},
        downloads=0,
        filename=filename,
        has_sig=False,
        md5_digest="",
        packagetype=packagetype,
        python_version="",
        requires_python="",
        size=0,
        upload_time="",
        upload_time_iso_8601="",
        url=original_url,
        yanked=False,
        yanked_reason=None,
    )

    if source_type == "sdist":
        monkeypatch.setattr(
            "pyodide_build.recipe.skeleton._find_sdist", lambda _: mock_entry
        )
        result = _find_dist(mock_metadata, ["sdist"])
    else:
        monkeypatch.setattr(
            "pyodide_build.recipe.skeleton._find_wheel", lambda _: mock_entry
        )
        result = _find_dist(mock_metadata, ["wheel"])

    assert result["url"] == predictable_url
    assert result["filename"] == filename


def test_find_dist_falls_back_to_original_url(monkeypatch):
    mock_metadata = MetadataDict(
        info={"name": "strange-pkg", "version": "1.0.0"},
        urls=[],
        releases={},
        last_serial=0,
        vulnerabilities=[],
    )

    original_url = (
        "https://files.pythonhosted.org/packages/ab/cd/strange-pkg-1.0.0-invalid.whl"
    )
    mock_entry = URLDict(
        filename="strange-pkg-1.0.0-invalid.whl",
        url=original_url,
        packagetype="bdist_wheel",
        digests={"sha256": "fakehash123"},
        has_sig=False,
        comment_text="",
        downloads=0,
        md5_digest="",
        python_version="",
        requires_python="",
        size=0,
        upload_time="",
        upload_time_iso_8601="",
        yanked=False,
        yanked_reason=None,
    )

    monkeypatch.setattr(
        "pyodide_build.recipe.skeleton._find_wheel", lambda _: mock_entry
    )
    monkeypatch.setattr(
        "pyodide_build.recipe.skeleton._make_predictable_url", lambda *args: None
    )

    result = _find_dist(mock_metadata, ["wheel"])

    assert result["url"] == original_url


# ---------------------------------------------------------------------------
# Bug 1 tests: update_package format-fallback control flow
# ---------------------------------------------------------------------------


def _make_mock_metadata(
    name: str,
    version_str: str,
    has_sdist: bool = True,
    has_wheel: bool = True,
) -> MetadataDict:
    """Build minimal PyPI metadata with the requested distribution types."""
    urls: list[Any] = []
    if has_sdist:
        urls.append(
            URLDict(
                comment_text="",
                digests={"sha256": f"sdist-sha256-{version_str}"},
                downloads=0,
                filename=f"{name}-{version_str}.tar.gz",
                has_sig=False,
                md5_digest="",
                packagetype="sdist",
                python_version="source",
                requires_python="",
                size=0,
                upload_time="",
                upload_time_iso_8601="",
                url=f"https://files.pythonhosted.org/packages/source/f/{name}/{name}-{version_str}.tar.gz",
                yanked=False,
                yanked_reason=None,
            )
        )
    if has_wheel:
        urls.append(
            URLDict(
                comment_text="",
                digests={"sha256": f"wheel-sha256-{version_str}"},
                downloads=0,
                filename=f"{name}-{version_str}-py3-none-any.whl",
                has_sig=False,
                md5_digest="",
                packagetype="bdist_wheel",
                python_version="py3",
                requires_python="",
                size=0,
                upload_time="",
                upload_time_iso_8601="",
                url=f"https://files.pythonhosted.org/packages/py3/f/{name}/{name}-{version_str}-py3-none-any.whl",
                yanked=False,
                yanked_reason=None,
            )
        )
    return MetadataDict(
        info={
            "name": name,
            "version": version_str,
            "home_page": "",
            "summary": "",
            "license": "",
            "package_url": f"https://pypi.org/project/{name}/",
        },
        last_serial=0,
        releases={},
        urls=urls,
        vulnerabilities=[],
    )


def _write_recipe(base_dir: Path, name: str, ver: str, url: str, sha256: str) -> Path:
    """Write a minimal meta.yaml for the given package."""
    db = MetaConfig(
        package={"name": name, "version": ver},
        source={"sha256": sha256, "url": url},
        test={"imports": [name]},
    )
    pkg_dir = base_dir / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    meta_path = pkg_dir / "meta.yaml"
    db.to_yaml(meta_path)
    return meta_path


def test_update_package_sdist_falls_back_to_wheel(tmp_path, monkeypatch):
    """When the new release has no sdist, update_package should fall back to wheel."""
    name = "fakepkg"
    old_ver = "1.0.0"
    new_ver = "2.0.0"

    # Existing recipe uses sdist
    meta_path = _write_recipe(
        tmp_path,
        name,
        old_ver,
        f"https://example.com/{name}-{old_ver}.tar.gz",
        "old-sdist-sha256",
    )

    # New release only has a wheel, not an sdist
    new_metadata = _make_mock_metadata(name, new_ver, has_sdist=False, has_wheel=True)
    monkeypatch.setattr(
        "pyodide_build.recipe.skeleton._get_metadata", lambda *_: new_metadata
    )
    # Skip the prettier call to avoid needing npx
    monkeypatch.setattr("pyodide_build.recipe.skeleton.run_prettier", lambda *_: None)

    # Should NOT raise even though there's no sdist for the new version
    update_package(tmp_path, name)

    db = MetaConfig.from_yaml(meta_path)
    assert db.package.version == new_ver
    # Should have fallen back to wheel
    assert db.source.url is not None
    assert db.source.url.endswith(".whl")


def test_update_package_wheel_falls_back_to_sdist(tmp_path, monkeypatch):
    """When the new release has no wheel, update_package should fall back to sdist."""
    name = "fakepkg"
    old_ver = "1.0.0"
    new_ver = "2.0.0"

    # Existing recipe uses wheel
    meta_path = _write_recipe(
        tmp_path,
        name,
        old_ver,
        f"https://example.com/{name}-{old_ver}-py3-none-any.whl",
        "old-wheel-sha256",
    )

    # New release only has an sdist, not a wheel
    new_metadata = _make_mock_metadata(name, new_ver, has_sdist=True, has_wheel=False)
    monkeypatch.setattr(
        "pyodide_build.recipe.skeleton._get_metadata", lambda *_: new_metadata
    )
    monkeypatch.setattr("pyodide_build.recipe.skeleton.run_prettier", lambda *_: None)

    update_package(tmp_path, name)

    db = MetaConfig.from_yaml(meta_path)
    assert db.package.version == new_ver
    # Should have fallen back to sdist
    assert db.source.url is not None
    assert db.source.url.endswith(".tar.gz")


def test_update_package_explicit_source_fmt_is_strict(tmp_path, monkeypatch):
    """When source_fmt is explicitly given, it must be respected with no fallback."""
    name = "fakepkg"
    old_ver = "1.0.0"
    new_ver = "2.0.0"

    # Existing recipe uses sdist
    _write_recipe(
        tmp_path,
        name,
        old_ver,
        f"https://example.com/{name}-{old_ver}.tar.gz",
        "old-sdist-sha256",
    )

    # New release only has a wheel, not an sdist
    new_metadata = _make_mock_metadata(name, new_ver, has_sdist=False, has_wheel=True)
    monkeypatch.setattr(
        "pyodide_build.recipe.skeleton._get_metadata", lambda *_: new_metadata
    )
    monkeypatch.setattr("pyodide_build.recipe.skeleton.run_prettier", lambda *_: None)

    # Explicitly requesting "sdist" must raise, not fall back to wheel
    with pytest.raises(MkpkgFailedException, match="sdist"):
        update_package(tmp_path, name, source_fmt="sdist")


# ---------------------------------------------------------------------------
# Bug 2 tests: _make_predictable_url uses actual filename for sdists
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "package,ver,filename,expected_url",
    [
        # Standard .tar.gz — filename must be preserved as-is
        (
            "numpy",
            "2.0.0",
            "numpy-2.0.0.tar.gz",
            "https://files.pythonhosted.org/packages/source/n/numpy/numpy-2.0.0.tar.gz",
        ),
        # .zip sdist — must NOT be silently rewritten to .tar.gz
        (
            "myzip",
            "1.0.0",
            "myzip-1.0.0.zip",
            "https://files.pythonhosted.org/packages/source/m/myzip/myzip-1.0.0.zip",
        ),
        # Non-normalized name (dots instead of underscores, as in ruamel.yaml)
        (
            "ruamel.yaml",
            "0.18.6",
            "ruamel.yaml-0.18.6.tar.gz",
            "https://files.pythonhosted.org/packages/source/r/ruamel_yaml/ruamel.yaml-0.18.6.tar.gz",
        ),
    ],
    ids=["standard-tar-gz", "zip-sdist", "non-normalized-name"],
)
def test_make_predictable_url_sdist_uses_real_filename(
    package, ver, filename, expected_url
):
    """Predictable URL for sdists must be built from the actual filename."""
    result = _make_predictable_url(package, ver, "sdist", filename)
    assert result == expected_url


def test_find_dist_sdist_zip_url_correct(monkeypatch):
    """_find_dist must produce a correct URL when the sdist is a .zip file."""
    package = "myzip"
    ver = "1.0.0"
    filename = "myzip-1.0.0.zip"
    original_url = f"https://files.pythonhosted.org/packages/ab/cd/{filename}"

    mock_metadata = MetadataDict(
        info={"name": package, "version": ver, "package_url": ""},
        urls=[],
        releases={},
        last_serial=0,
        vulnerabilities=[],
    )
    mock_entry = URLDict(
        comment_text="",
        digests={"sha256": "fakehash"},
        downloads=0,
        filename=filename,
        has_sig=False,
        md5_digest="",
        packagetype="sdist",
        python_version="source",
        requires_python="",
        size=0,
        upload_time="",
        upload_time_iso_8601="",
        url=original_url,
        yanked=False,
        yanked_reason=None,
    )

    monkeypatch.setattr(
        "pyodide_build.recipe.skeleton._find_sdist", lambda _: mock_entry
    )

    result = _find_dist(mock_metadata, ["sdist"])

    # URL must end with .zip, not .tar.gz
    assert result["url"].endswith(".zip"), result["url"]
    assert result["url"] == (
        "https://files.pythonhosted.org/packages/source/m/myzip/myzip-1.0.0.zip"
    )
