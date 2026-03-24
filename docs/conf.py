import os
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path

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
]

myst_enable_extensions = [
    "colon_fence",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3.13", None),
    "pyodide": ("https://pyodide.org/en/stable/", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".*", "DOCUMENTATION_PLAN.md"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")

html_css_files = [
    "css/pyodide.css",
]

html_theme = "sphinx_book_theme"
html_logo = "_static/img/pyodide-logo.png"
html_static_path = ["_static"]

html_theme_options = {
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
