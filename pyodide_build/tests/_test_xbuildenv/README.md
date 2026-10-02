`xbuildenv-test-<python version>.tar.gz` is a minimal, stripped-down version of the actual Pyodide cross-build environment used for testing.

This archive needs to be updated when the main Python version used for testing changes.

It is based on actual `xbuildenv-x.y.z.tar.bz2`, but most stuff is stripped out (like binaries, Python headers).
To add a Python version, take a release built for it, which you can find in the [cross-build environments metadata](https://pyodide.github.io/pyodide/api/v2/pyodide-cross-build-environments.json), and run:

```bash
curl -LO https://github.com/pyodide/pyodide/releases/download/314.0.3/xbuildenv-314.0.3.tar.gz
python make_fixture.py xbuildenv-314.0.3.tar.gz xbuildenv-test-3.14.tar.gz
```

Then add that Python version to the `test` job in `.github/workflows/main.yml`.
