import functools
import os
import shutil


@functools.cache
def find_uv_bin() -> str | None:
    """
    Check if the uv executable is available.

    If the uv executable is available, return the path to the executable.
    Otherwise, return None.
    """
    try:
        import uv

        return uv.find_uv_bin()
    except (ModuleNotFoundError, FileNotFoundError):
        return shutil.which("uv")

    return None


def should_use_uv() -> bool:
    # UV environ is set to the uv executable path when the script is called with the uv executable.
    uv_environ = os.environ.get("UV")
    # double check by comparing the uv executable path with the one found by the uv package.
    return uv_environ and uv_environ == find_uv_bin()
