import hashlib
import zipfile
from pathlib import Path
from typing import Any

import pytest
from pyodide_lock.spec import PackageSpec

from pyodide_build import build_env
from pyodide_build.build_env import BuildArgs
from pyodide_build.recipe import graph_builder

RECIPE_DIR = Path(__file__).parent / "_test_recipes"
BUILD_DIR = RECIPE_DIR


def test_generate_dependency_graph():
    # beautifulsoup4 has a circular dependency on soupsieve
    pkg_map = graph_builder.generate_dependency_graph(RECIPE_DIR, {"beautifulsoup4"})
    assert pkg_map["beautifulsoup4"].run_dependencies == ["soupsieve"]
    assert pkg_map["beautifulsoup4"].host_dependencies == []
    assert pkg_map["beautifulsoup4"].host_dependents == set()


@pytest.mark.parametrize(
    "requested, disabled, out",
    [
        ({"scipy"}, set(), {"scipy", "numpy", "CLAPACK"}),
        ({"scipy"}, {"numpy"}, set()),
        ({"scipy", "CLAPACK"}, {"numpy"}, {"CLAPACK"}),
        ({"scikit-learn"}, {"numpy"}, set()),
        ({"scikit-learn", "scipy"}, {"joblib"}, {"scipy", "numpy", "CLAPACK"}),
        ({"scikit-learn", "no-numpy-dependents"}, set(), set()),
        ({"scikit-learn", "numpy", "no-numpy-dependents"}, set(), {"numpy"}),
    ],
)
def test_generate_dependency_graph2(requested, disabled, out):
    pkg_map = graph_builder.generate_dependency_graph(RECIPE_DIR, requested, disabled)
    assert set(pkg_map.keys()) == out


def test_generate_dependency_graph_disabled():
    pkg_map = graph_builder.generate_dependency_graph(
        RECIPE_DIR, {"pkg_test_disabled_child"}
    )
    assert set(pkg_map.keys()) == set()

    pkg_map = graph_builder.generate_dependency_graph(RECIPE_DIR, {"pkg_test_disabled"})
    assert set(pkg_map.keys()) == set()


def test_generate_lockfile(tmp_path, dummy_xbuildenv):
    pkg_map = graph_builder.generate_dependency_graph(
        RECIPE_DIR, {"pkg_1", "pkg_2", "libtest", "libtest_shared"}
    )
    hashes = {}
    for pkg in pkg_map.values():
        if not pkg.file_name:
            match pkg.package_type:
                case "package":
                    pkg.file_name = pkg.name + f"-{pkg.version}-py3-none-any.whl"
                case _:
                    pkg.file_name = pkg.name + ".zip"
        # Write dummy package file for SHA-256 hash verification
        with zipfile.ZipFile(tmp_path / pkg.file_name, "w") as whlzip:
            whlzip.writestr(pkg.file_name, data=pkg.file_name)

        with open(tmp_path / pkg.file_name, "rb") as f:
            hashes[pkg.name] = hashlib.sha256(f.read()).hexdigest()

    package_data = graph_builder.generate_lockfile(tmp_path, pkg_map)
    assert package_data.info.arch == "wasm32"
    assert package_data.info.platform.startswith("emscripten")
    assert package_data.info.version == build_env.get_build_flag("PYODIDE_VERSION")

    assert set(package_data.packages) == {
        "pkg-1",
        "pkg-1-1",
        "pkg-2",
        "pkg-3",
        "pkg-3-1",
        "libtest-shared",
    }
    assert package_data.packages["pkg-1"] == PackageSpec(
        name="pkg_1",
        version="1.0.0",
        file_name="pkg_1-1.0.0-py3-none-any.whl",
        depends=["pkg_1_1", "pkg_3", "libtest_shared"],
        imports=["pkg_1"],
        package_type="package",
        install_dir="site",
        sha256=hashes["pkg_1"],
    )

    assert package_data.packages["libtest-shared"].package_type == "shared_library"

    sharedlib_imports = package_data.packages["libtest-shared"].imports
    assert not sharedlib_imports, (
        "shared libraries should not have any imports, but got " f"{sharedlib_imports}"
    )


@pytest.mark.parametrize("n_jobs", [1, 4])
def test_build_dependencies(n_jobs, monkeypatch):
    build_list = []

    def mock_build(self, args: Any, build_dir: Path) -> None:
        build_list.append(self.name)

    monkeypatch.setattr(graph_builder.BasePackage, "build", mock_build)

    pkg_map = graph_builder.generate_dependency_graph(RECIPE_DIR, {"pkg_1", "pkg_2"})

    graph_builder.build_from_graph(
        pkg_map, BuildArgs(), BUILD_DIR, n_jobs=n_jobs, force_rebuild=True
    )

    assert set(build_list) == {
        "pkg_1",
        "pkg_1_1",
        "pkg_2",
        "pkg_3",
        "pkg_3_1",
        "libtest_shared",
    }
    assert build_list.index("pkg_1_1") < build_list.index("pkg_1")
    assert build_list.index("pkg_3") < build_list.index("pkg_1")
    assert build_list.index("pkg_3_1") < build_list.index("pkg_3")


@pytest.mark.parametrize("n_jobs", [1, 4])
def test_build_error(n_jobs, monkeypatch):
    """Try building all the dependency graph, without the actual build operations"""

    def mock_build(self, args: Any, build_dir: Path) -> None:
        raise ValueError("Failed build")

    monkeypatch.setattr(graph_builder.BasePackage, "build", mock_build)

    pkg_map = graph_builder.generate_dependency_graph(RECIPE_DIR, {"pkg_1"})

    with pytest.raises(ValueError, match="Failed build"):
        graph_builder.build_from_graph(
            pkg_map, BuildArgs(), BUILD_DIR, n_jobs=n_jobs, force_rebuild=True
        )


def test_requirements_executable(monkeypatch):
    import shutil

    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda exe: None)

        with pytest.raises(RuntimeError, match="missing in the host system"):
            graph_builder.generate_dependency_graph(RECIPE_DIR, {"pkg_test_executable"})

    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda exe: "/bin")

        graph_builder.generate_dependency_graph(RECIPE_DIR, {"pkg_test_executable"})
