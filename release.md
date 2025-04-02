# `pyodide-build` release workflow

This document provides maintenance and release instructions for `pyodide-build`, adapted
from the [Maintainer information page from the Pyodide project](https://pyodide.org/en/stable/development/maintainers.html).

> [!NOTE]
> `pyodide-build` is used as a git submodule by the Pyodide repository. If a change is only required for in-tree builds,
it is sufficient to update the git submodule. A release is only necessary if the changes are required by out-of-tree builds.
>
> See the [Updating `pyodide-build`](https://pyodide.org/en/stable/development/maintainers.html#updating-pyodide-build) section for more information.

# Release instructions

- Decide on a new version number: we follow the [SemVer](https://semver.org/) versioning scheme; which means that we create major/minor versions for feature releases and micro/patch versions for bug fixes. The package uses [Semantic Versioning](https://semver.org/) for versioning. The version number is defined in the `pyproject.toml` file in the root of the repository.

- If there is a compelling reason to discuss or plan a new release before creating it (what is to be included, timeline, planned scope, etc.), open a new "Release planning" tracking issue with the information and any other relevant resources. Optionally, a new milestone for the release can also be created. This is not strictly necessary, but it can help to keep track of the issues and PRs that are planned to be included.

- Create a tag with the version number (e.g., `v0.X.Y`) while on the `main` branch, and create and publish a GitHub release with the tag and attach a link to the CHANGELOG. Other release notes can be generated with the "Generate release notes" button in the GitHub UI, which will add a list of all PRs that were merged with the tag. The release notes can be reviewed and edited as necessary at the time of creating the release or edited after it is created. The release notes from the previous releases can be used for reference and inspiration.

- If backward-incompatible changes are introduced:
    - the release notes should be updated to include a "Breaking changes" section, if not already present through the CHANGELOG.
    - we also test against a minimum version of Pyodide xbuildenvs in the integration tests in `main.yml`. If a new minimum version
    is required, then update it in the [`tools/update_cross_build_releases.py`](https://github.com/pyodide/pyodide/blob/74bd69b5afa00074580f16a72eae3d7ce5a0817a/tools/update_cross_build_releases.py#L23-L25) file so that cross-build environments metadata for newer versions of Pyodide will contain the correct minimum and maximum versions of `pyodide-build` they can be used with.
