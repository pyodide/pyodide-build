import os
import sys
from collections.abc import Sequence
from importlib import metadata as importlib_metadata
from pathlib import Path

from docutils import nodes, statemachine
from sphinx.util.docutils import SphinxDirective

project = "pyodide-build"
copyright = "2019-2026, Pyodide contributors"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "myst_parser",
    "sphinx_autodoc_typehints",
    "sphinx_design",
    "sphinx_click",
]

myst_enable_extensions = [
    "colon_fence",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3.13", None),
    "pyodide": ("https://pyodide.org/en/stable/", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".*"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")

html_css_files = [
    "css/pyodide.css",
]

html_theme = "sphinx_book_theme"
html_static_path = ["_static"]

html_theme_options = {
    "logo": {
        "image_light": "_static/img/pyodide-logo-light.svg",
        "image_dark": "_static/img/pyodide-logo-dark.svg",
    },
    "show_toc_level": 2,
    "show_navbar_depth": 2,
    "home_page_in_toc": True,
}


sys.path.append(Path(__file__).parent.parent.as_posix())


try:
    release = importlib_metadata.version("pyodide-build")
except importlib_metadata.PackageNotFoundError:
    print("Could not find package version, please install pyodide-build to build docs")
    release = "0.0.0"

version = release


# -- Auto-generated CLI reference --------------------------------------------


class PyodideCLIReference(SphinxDirective):
    """
    Emit a sphinx-click block for a ``pyodide.cli`` entry point if it belongs
    to pyodide-build, to automatically generate CLI reference documentation.
    """

    # Recipe-related commands are intentionally excluded: they are not relevant
    # to most users building out-of-tree packages.
    _EXCLUDE = {"build-recipes", "build-recipes-no-deps", "skeleton"}

    def run(self) -> Sequence[nodes.Node]:
        entry_points = sorted(
            (
                entry_point
                for entry_point in importlib_metadata.entry_points(group="pyodide.cli")
                if entry_point.dist is not None
                and entry_point.dist.name == "pyodide-build"
                and entry_point.name not in self._EXCLUDE
            ),
            key=lambda ep: ep.name,
        )

        rst: list[str] = []
        for ep in entry_points:
            obj = ep.load()
            rst.append(f".. click:: {ep.value}")
            rst.append(f"   :prog: pyodide {ep.name}")
            if hasattr(
                obj, "commands"
            ):  # If it's a click group? Then let's recurse into subcommands
                rst.append("   :nested: full")
            rst.append("")

        result = statemachine.ViewList(rst, source="<pyodide-cli-reference>")
        node: nodes.Node = nodes.section()
        self.state.nested_parse(result, self.content_offset, node)  # type: ignore[arg-type]
        return node.children


def setup(app):
    app.add_directive("pyodide-cli-reference", PyodideCLIReference)
