import json
import os
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any

from pyodide_build.build_env import (
    get_build_environment_vars,
    get_pyodide_root,
)
from pyodide_build.common import exit_with_stdio
from pyodide_build.logger import logger


class BashRunnerWithSharedEnvironment:
    """Run multiple bash scripts with persistent environment.

    Environment is stored to "env" member between runs. This can be updated
    directly to adjust the environment, or read to get variables.
    """

    def __init__(self, env: dict[str, str] | None = None) -> None:
        if env is None:
            env = dict(os.environ)

        self.env: dict[str, str] = env

    def __enter__(self) -> "BashRunnerWithSharedEnvironment":
        return self

    def run_unchecked(self, cmd: str, **opts: Any) -> subprocess.CompletedProcess[str]:
        # Use a fresh pipe for every invocation. The child process inherits the
        # write end and dumps the resulting environment to it. We close the
        # parent's copy of the write end *before* reading so that ``readline``
        # observes EOF if the script exited the shell early (e.g. ``exit 0``)
        # without ever running the env-dump command. Otherwise the parent would
        # block forever, since it would still hold the write end open and never
        # see EOF. See https://github.com/pyodide/pyodide-build/issues/376.
        fd_read, fd_write = os.pipe()
        write_env_pycode = ";".join(
            [
                "import os",
                "import json",
                f'os.write({fd_write}, json.dumps(dict(os.environ)).encode() + b"\\n")',
            ]
        )
        write_env_shell_cmd = f"{sys.executable} -c '{write_env_pycode}'"
        full_cmd = f"{cmd}\n{write_env_shell_cmd}"
        with os.fdopen(fd_write) as writer, os.fdopen(fd_read, "r") as reader:
            result = subprocess.run(
                ["bash", "-ce", full_cmd],
                check=False,
                pass_fds=[fd_write],
                env=self.env,
                encoding="utf8",
                **opts,
            )
            # Close the parent's copy of the write end before reading so we
            # can observe EOF when the child never wrote the env dump.
            writer.close()
            if result.returncode == 0:
                env_dump = reader.readline()
                if env_dump:
                    self.env = json.loads(env_dump)
                else:
                    # The script exited the shell itself (e.g. ``exit 0``)
                    # before the env-dump command ran, so there is no
                    # updated environment to capture. Keep the current env.
                    logger.debug(
                        "Script exited the shell before dumping its "
                        "environment; keeping the previous environment."
                    )
        return result

    def run(
        self,
        cmd: str | None,
        *,
        script_name: str,
        cwd: Path | str | None = None,
        **opts: Any,
    ) -> subprocess.CompletedProcess[str] | None:
        """Run a bash script. Any keyword arguments are passed on to subprocess.run."""
        if not cmd:
            return None
        if cwd is None:
            cwd = Path.cwd()
        cwd = Path(cwd).absolute()
        logger.info("Running %s in %s", script_name, str(cwd))
        opts["cwd"] = cwd
        result = self.run_unchecked(cmd, **opts)
        if result.returncode != 0:
            logger.error("ERROR: %s failed", script_name)
            logger.error(textwrap.indent(cmd, "    "))
            exit_with_stdio(result)
        return result

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # Pipes are created and closed per ``run_unchecked`` call, so there is
        # nothing to clean up here.
        return None


@contextmanager
def get_bash_runner(
    extra_envs: dict[str, str],
) -> Iterator[BashRunnerWithSharedEnvironment]:
    pyodide_root = get_pyodide_root()
    # ``get_build_environment_vars`` is ``@functools.cache``d and returns the
    # cached dict, so copy it before mutating to avoid leaking per-package
    # variables (PKGDIR, PKG_VERSION, DISTDIR, ...) into the cached value, which
    # would otherwise be seen by subsequent package builds in the same process.
    env = dict(get_build_environment_vars(pyodide_root))
    env.update(extra_envs)

    with BashRunnerWithSharedEnvironment(env=env) as b:
        # Working in-tree, add emscripten toolchain into PATH and set ccache
        if Path(pyodide_root, "pyodide_env.sh").exists():
            b.run(
                f"source {pyodide_root}/pyodide_env.sh",
                script_name="source pyodide_env",
                stderr=subprocess.DEVNULL,
            )

        yield b
