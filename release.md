# `pyodide-build` release workflow

This document provides maintenance and release instructions for `pyodide-build`, adapted
from the [Maintainer information page from the Pyodide project](https://pyodide.org/en/stable/development/maintainers.html).

> [!NOTE]
> `pyodide-build` is also used as a submodule in-tree within the Pyodide repository, and it is usually acceptable to
update the submodule to point to a newer commit in most cases and a release isn't always required unless it's needed
to address bugs or add features for out-of-tree builds.
>
> See the [Updating `pyodide-build`](https://pyodide.org/en/stable/development/maintainers.html#updating-pyodide-build) section for more information.

# Release instructions

- First, create a "Release planning" tracking issue that can list information such as:
    - the timeline of the release
    - the scope of the release and the pull requests to be included, ideally by attaching a milestone to them or creating one through the GitHub Issues UI if it doesn't exist
    - any other relevant resources

- Once a consensus is reached on the release plan, create a new milestone in the GitHub Issues UI. This milestone should have the same name as the release version (e.g., `v0.23.0`) and should be marked as "open". The milestone should also be assigned to the release planning issue.

- Create a tag with the version number (e.g., `v0.X.Y`) while on the `main` branch, and create and publish a GitHub release with the tag and attach a link to the CHANGELOG. Other release notes can be generated with the "Generate release notes" button, which will add a list of all PRs that were merged with the tag. The release notes can be reviewed and edited as necessary at the time of creating the release or edited after it is created.

- If backward-incompatible changes are introduced:
    - the release notes should be updated to include a "Breaking changes" section, if not already present through the CHANGELOG.
    - we also test against a minimum version of Pyodide xbuildenvs in the integration tests in `main.yml`. If a new minimum version
    is required, then update it in the [`tools/update_cross_build_releases.py`](https://github.com/pyodide/pyodide/blob/74bd69b5afa00074580f16a72eae3d7ce5a0817a/tools/update_cross_build_releases.py#L23-L25) file so that cross-build environments metadata for newer versions of Pyodide will contain the correct minimum and maximum versions of `pyodide-build` they can be used with.
