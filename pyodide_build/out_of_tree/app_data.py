"""
Virtualenv has a concept of "app data" which is basically a cache of a virtual environment.
It is used to speed up the creation of new virtual environments by reusing the cached data.

In Pyodide, we "abuse" this app data mechanism to generate virtualenv correctly for different platforms, mostly for Windows.

- Why do we need this?

virtualenv calculates Python executable paths and other parameters by running the interpreter inside the virtualenv creation process.
However, since Pyodide's Python interpreter tries to be Unix-compatible, running it in Windows environment results in wrong paths.
To work around this, we pre-generate the app data for Windows, and patch it so that virtualenv "bypasses" the interpreter execution step and uses the pre-generated data.
This allows us to create virtualenvs with correct paths on Windows.

- How can I find the format of the app data?

Create a virtualenv with `VIRTUALENV_OVERRIDE_APP_DATA` env variable set:

```
VIRTUALENV_OVERRIDE_APP_DATA=<temp_dir> virtualenv venv
```

This will create a directory `<temp_dir>` containing the app data JSON file, which you can inspect to understand the format.
"""
from typing import Any
from contextlib import contextmanager
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

from virtualenv import session_via_cli
from virtualenv.app_data import AppDataDiskFolder


def build_host_app_data(app_data_dir: str | Path) -> dict[str, Any]:
    """
    Create the app data for the platform by invoking virtualenv with VIRTUALENV_OVERRIDE_APP_DATA,
    then return the generated app data JSON file.

    Parameters
    ----------
    app_data_dir : str | Path
        The directory where the app data will be stored.
    """
    with TemporaryDirectory() as temp_dir:
        env = {"VIRTUALENV_OVERRIDE_APP_DATA": str(app_data_dir)}
        session_via_cli([temp_dir], env=env)

        py_info_dir = Path(app_data_dir) / "py_info" / "2"
        py_info_file = next(py_info_dir.glob("*.json")) # there should be only one JSON file that just created

        data = py_info_file.read_text(encoding="utf-8")

    return json.loads(data)


def overwrite_host_app_data(
    app_data: dict[str, Any],
    target_python_executable: str,
) -> dict[str, Any]:
    """
    Overwrite the host app data to create the target app data for the specified platform.

    Parameters
    ----------
    app_data : dict[str, Any]
        The host app data.
    target_python_executable : str
        The path to the target Python executable.
    """
    patched_app_data = app_data.copy()
    patched_app_data["path"] = target_python_executable
    patched_app_data["st_mtime"] = Path(target_python_executable).stat().st_mtime
    patched_app_data["content"].update({
        "executable": target_python_executable,
        "original_executable": target_python_executable,
    })
    return patched_app_data


@contextmanager
def create_app_data_dir(
    target_python_executable: str,
):
    """
    Context manager that creates a temporary app data directory for the specified Pyodide interpreter.
    """

    with TemporaryDirectory() as app_data_dir:
        host_app_data = build_host_app_data(app_data_dir)
        patched_app_data = overwrite_host_app_data(
            host_app_data,
            target_python_executable,
        )
        print("Saving patched app data to", app_data_dir)  # --- IGNORE ---
        AppDataDiskFolder(app_data_dir).py_info(target_python_executable).write(patched_app_data)
        print("key is: ", AppDataDiskFolder(app_data_dir).py_info(target_python_executable).key)
        yield app_data_dir