`xbuildenv-test.tar.gz` is a minimal, stripped-down version of the actual Pyodide cross-build environment used for testing.

This archive needs to be updated when the main Python version used for testing changes.

It is based on actual `xbuildenv-x.y.z.tar.bz2`, but most stuff is stripped out (like binaries, Python headers).

`pyodide-lock.json` is also modified - it includes only minimal set of packages.
Notably it's intentionally omitting `pycryptodome` since tests rely on it being absent to test the `--build-dependencies` flag.
When updating `xbuildenv-test.tar.gz` keep only the packages that were included in the previous version.
Use the `filter_tar.py` script to help with this - it will filter `pyodide-lock.json` to keep only packages from the old version.
