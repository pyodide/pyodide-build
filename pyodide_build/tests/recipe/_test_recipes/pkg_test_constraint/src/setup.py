from importlib.metadata import version
from pathlib import Path

from setuptools import setup

for pkg in ["setuptools", "pytest"]:
    Path(f"../{pkg}.version").write_text(version(pkg))

setup()
