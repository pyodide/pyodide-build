This directory contains assets to run integration tests for pyodide-build.

Tests in this directory are not run by default in CI. To run these tests, add `[integration]` in the commit message.

## Running the integration tests locally

There are two types of integration tests:

- Recipe tests (in this directory)
- Tests marked with integration marker in the root directory

To run the recipe integration tests locally, use the `make` command in this directory.

```bash
make test-recipe
```

This runs a subset of the tests. The other tests are run from the root directory
via the following command:

```bash
pytest -m integration
```
