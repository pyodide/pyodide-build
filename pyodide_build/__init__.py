from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pyodide-build")
except PackageNotFoundError:
    __version__ = "1.0.0.dev0"
