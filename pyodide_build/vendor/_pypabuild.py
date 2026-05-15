# This file contains private functions taken from pypa/build.

# Copyright © 2019 Filipe Laíns <filipe.lains@gmail.com>

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice (including the next
# paragraph) shall be included in all copies or substantial portions of the
# Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
import contextlib
import contextvars
import os
import subprocess
import sys
import traceback
import warnings
from collections.abc import Iterator
from typing import NoReturn, TextIO

from build import (
    BuildBackendException,
    BuildException,
    FailedProcessError,
)
from build.env import DefaultIsolatedEnv

_COLORS = {
    "red": "\33[91m",
    "green": "\33[92m",
    "yellow": "\33[93m",
    "bold": "\33[1m",
    "dim": "\33[2m",
    "underline": "\33[4m",
    "reset": "\33[0m",
}
_NO_COLORS = dict.fromkeys(_COLORS, "")

_styles = contextvars.ContextVar("_styles", default=_COLORS)


def _init_colors() -> None:
    if "NO_COLOR" in os.environ:
        if "FORCE_COLOR" in os.environ:
            warnings.warn(
                "Both NO_COLOR and FORCE_COLOR environment variables are set, disabling color",
                stacklevel=2,
            )
        _styles.set(_NO_COLORS)
    elif "FORCE_COLOR" in os.environ or sys.stdout.isatty():
        return
    _styles.set(_NO_COLORS)


def _cprint(fmt: str = "", msg: str = "", file: TextIO | None = None) -> None:
    print(fmt.format(msg, **_styles.get()), file=file, flush=True)


def _error(msg: str, code: int = 1) -> NoReturn:  # pragma: no cover
    """
    Print an error message and exit. Will color the output when writing to a TTY.

    :param msg: Error message
    :param code: Error code
    """
    _cprint("{red}ERROR{reset} {}", msg, file=sys.stderr)
    raise SystemExit(code)


class _DefaultIsolatedEnv(DefaultIsolatedEnv):
    @property
    def scripts_dir(self) -> str:
        return self._env_backend.scripts_dir


def _log_subprocess_output(error: subprocess.CalledProcessError) -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(error, stream_name, None)
        if stream:
            decoded = stream.decode() if isinstance(stream, bytes) else stream
            _cprint("{bold}{red}" + stream_name + ":{reset}\n{dim}{}{reset}", decoded)


def _find_called_process_error(
    exc: Exception,
) -> subprocess.CalledProcessError | None:
    if isinstance(exc, subprocess.CalledProcessError):
        return exc
    inner = getattr(exc, "exception", None)
    if isinstance(inner, subprocess.CalledProcessError):
        return inner
    return None


@contextlib.contextmanager
def _handle_build_error() -> Iterator[None]:
    try:
        yield
    except Exception as e:
        if isinstance(e, BuildBackendException) and not isinstance(
            e.exception, subprocess.CalledProcessError
        ):
            if e.exc_info:
                tb_lines = traceback.format_exception(
                    e.exc_info[0],
                    e.exc_info[1],
                    e.exc_info[2],
                    limit=-1,
                )
                tb = "".join(tb_lines)
            else:
                tb = traceback.format_exc(-1)  # type: ignore[unreachable]
            _cprint("\n{dim}{}{reset}\n", tb.strip("\n"))
        elif not isinstance(e, (BuildException, FailedProcessError)):
            tb = traceback.format_exc().strip("\n")
            _cprint("\n{dim}{}{reset}\n", tb)

        cpe = _find_called_process_error(e)
        if cpe is not None:
            _log_subprocess_output(cpe)

        _error(str(e))
