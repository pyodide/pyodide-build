import contextlib
import shutil


def find_uv_bin() -> str | None:
    """
    Return the path to the uv executable, or None if not found.
    Prefers the uv Python package over a PATH lookup.
    Otherwise, return None.
    """
    with contextlib.suppress(ImportError, FileNotFoundError):
        from uv import find_uv_bin as _find_uv_bin

        return _find_uv_bin()

    return shutil.which("uv")


def should_use_uv() -> bool:
    return find_uv_bin() is not None
