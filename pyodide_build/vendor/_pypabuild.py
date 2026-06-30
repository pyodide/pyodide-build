# This file contains private functions taken from pypa/build.
# See license at LICENSE next to this file and as defined in
# pyproject.toml. For built distributions of pyodide-build,
# you may obtain a copy of the license in the
# .dist-info/licenses directory.
import contextlib
import contextvars
import os
import subprocess
import sys
import sysconfig
import traceback
import warnings
from collections.abc import Callable, Iterator
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
def _configure_build_verbosity(
    verbosity: int,
    logger_fn: Callable[..., None],
) -> Iterator[None]:
    """
    Set build._ctx.VERBOSITY and build._ctx.LOGGER for the duration of a build.
    """
    from build import _ctx

    token_verbosity = _ctx.VERBOSITY.set(verbosity)
    token_logger = _ctx.LOGGER.set(logger_fn)
    try:
        yield
    finally:
        _ctx.VERBOSITY.reset(token_verbosity)
        _ctx.LOGGER.reset(token_logger)


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


# Vendored from pypa/build v1.5.0. See source at:
# https://github.com/pypa/build/blob/615d04cfc52ac3c1592a463f0afe484fee1cc368/src/build/env.py#L461-L501
def _find_executable_and_scripts(path: str) -> tuple[str, str, str]:
    """
    Detect the Python executable and script folder of a virtual environment.

    :param path: The location of the virtual environment
    :return: The Python executable, script folder, and purelib folder
    """
    config_vars = (
        sysconfig.get_config_vars().copy()
    )  # globally cached, copy before altering it
    config_vars["base"] = path
    scheme_names = sysconfig.get_scheme_names()
    if "venv" in scheme_names:
        # Python distributors with custom default installation scheme can set a
        # scheme that can't be used to expand the paths in a venv.
        # This can happen if build itself is not installed in a venv.
        # The distributors are encouraged to set a "venv" scheme to be used for this.
        # See https://bugs.python.org/issue45413
        # and https://github.com/pypa/virtualenv/issues/2208
        paths = sysconfig.get_paths(scheme="venv", vars=config_vars)  # pragma: no cover
    elif "posix_local" in scheme_names:
        # The Python that ships on Debian/Ubuntu varies the default scheme to
        # install to /usr/local
        # But it does not (yet) set the "venv" scheme.
        # If we're the Debian "posix_local" scheme is available, but "venv"
        # is not, we use "posix_prefix" instead which is venv-compatible there.
        paths = sysconfig.get_paths(scheme="posix_prefix", vars=config_vars)
    elif "osx_framework_library" in scheme_names:
        # The Python that ships with the macOS developer tools varies the
        # default scheme depending on whether the ``sys.prefix`` is part of a framework.
        # But it does not (yet) set the "venv" scheme.
        # If the Apple-custom "osx_framework_library" scheme is available but "venv"
        # is not, we use "posix_prefix" instead which is venv-compatible there.
        paths = sysconfig.get_paths(scheme="posix_prefix", vars=config_vars)
    else:
        paths = sysconfig.get_paths(vars=config_vars)

    executable = os.path.join(
        paths["scripts"], "python.exe" if os.name == "nt" else "python"
    )
    if not os.path.exists(executable):
        msg = f"Virtual environment creation failed, executable {executable} missing"
        raise RuntimeError(msg)

    return executable, paths["scripts"], paths["purelib"]
