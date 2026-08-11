# pkgconfig is not part of [build-system] requires in pyproject.toml: it can
# only be importable here if the extra build requirements declared in
# requirements/build_extras of the recipe were installed into the isolated
# build environment.
import pkgconfig
from setuptools import setup

print("build_extras_example: found pkgconfig at", pkgconfig.__file__)

setup()
