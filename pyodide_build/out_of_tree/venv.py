import shutil
import sys
import textwrap
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import os

from pyodide_build.build_env import get_build_flag, get_pyodide_root, in_xbuildenv
from pyodide_build.common import IS_WIN, run_command
from pyodide_build.logger import logger

# A subset of supported virtualenv options that make sense in Pyodide's context.
# Our aim will not be to support all of them, and some of them will never be in
# the list, for example, --no-pip and so on. We provide these on a best-effort
# basis as they should work and are easy to test.
SUPPORTED_VIRTUALENV_OPTIONS = [
    "--clear",
    "--no-clear",
    "--no-vcs-ignore",
    # "--copies", "--always-copy", FIXME: node fails to invoke Pyodide
    # "--symlink-app-data", FIXME: node fails to invoke Pyodide
    "--no-download",
    "--never-download",
    "--download",
    "--extra-search-dir",
    "--pip",
    "--setuptools",
    "--no-setuptools",
    "--no-periodic-update",
]


def dedent(s: str) -> str:
    return textwrap.dedent(s).strip() + "\n"


def get_pyversion() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def check_host_python_version(session: Any) -> None:
    pyodide_version = session.interpreter.version.partition(" ")[0].split(".")[:2]
    sys_version = [str(sys.version_info.major), str(sys.version_info.minor)]
    if pyodide_version == sys_version:
        return
    pyodide_version_fmt = ".".join(pyodide_version)
    sys_version_fmt = ".".join(sys_version)
    logger.stderr(
        f"Expected host Python version to be {pyodide_version_fmt} but got version {sys_version_fmt}"
    )
    sys.exit(1)


def pyodide_dist_dir() -> Path:
    return get_pyodide_root() / "dist"


class PyodideVenv(ABC):
    """Base class for creating Pyodide virtual environments.

    This class contains common functionality shared across all platforms.
    Platform-specific implementations should inherit from this class.
    """

    def __init__(self, dest: Path, virtualenv_args: list[str] | None = None) -> None:
        self.dest = dest
        self.virtualenv_args = virtualenv_args or []
        self._venv_root: Path | None = None
        self._venv_bin: Path | None = None

    @property
    def venv_root(self) -> Path | None:
        """Get the path to the virtualenv's root directory."""
        if self._venv_root is None:
            raise RuntimeError("venv_root is not set")

        return self._venv_root

    @property
    def venv_bin(self) -> Path | None:
        """Get the path to the virtualenv's bin directory."""
        if self._venv_bin is None:
            raise RuntimeError("venv_bin is not set")

        return self._venv_bin

    @property
    def exe_suffix(self) -> str:
        """Return the executable suffix for the platform."""
        return ""

    @property
    def python_exe_name(self) -> str:
        """Return the Python executable name for the platform."""
        return "python" + self.exe_suffix

    @property
    @abstractmethod
    def bin_dir_name(self) -> str:
        """Return the bin directory name for the platform."""
        pass

    @property
    def pyodide_exe_name(self) -> str:
        """Return the Pyodide executable name for the platform."""
        return "pyodide" + self.exe_suffix

    @property
    def host_python_name(self) -> str:
        """Get the host python executable name."""
        return f"python{get_pyversion()}-host" + self.exe_suffix

    @property
    def host_python_name_noversion(self) -> str:
        """Get the host python executable name without version."""
        return "python-host" + self.exe_suffix

    @property
    @abstractmethod
    def host_python_symlink_suffix(self) -> str:
        """Get the host python symlink suffix."""
        pass

    @property
    def venv_sitepackages_path(self) -> Path:
        """
        Path to the site-packages directory in the virtualenv, where packages are installed.

        Note that in host environment, Windows uses 'Lib\\site-packages' while Unix uses 'lib/pythonX.Y/site-packages'.
        However, Pyodide environment is Unix-like, so we always use the Unix-style path here so that packages are located correctly
        inside the Pyodide virtual environment
        """
        return self.venv_root / "lib" / f"python{get_pyversion()}" / "site-packages"

    @property
    def interpreter_path(self) -> Path:
        """Get the path to the original Pyodide Python interpreter."""
        return pyodide_dist_dir() / self.python_exe_name

    @property
    def interpreter_symlink_path(self) -> Path:
        """Get the path to the Pyodide Python interpreter symlink."""
        return self.venv_bin / self.python_exe_name

    @property
    def pyodide_cli_path(self) -> Path:
        """Get the path to the pyodide CLI script in the virtualenv."""
        return self.venv_bin / self.pyodide_exe_name

    @property
    def host_python_path(self) -> Path:
        """Get the path to the host python executable in the virtualenv."""
        return self.venv_bin / self.host_python_name

    @property
    def host_python_path_noversion(self) -> Path:
        """Get the path to the host python executable without version in the virtualenv."""
        return self.venv_bin / self.host_python_name_noversion

    @property
    def host_python_symlink_path(self) -> Path:
        """Get the path to the host python symlink in the virtualenv."""
        return self.venv_bin / f"python{self.host_python_symlink_suffix}"

    @property
    def pip_conf_path(self) -> Path:
        """Get the path to the pip.conf file in the virtualenv."""
        return self.venv_root / "pip.conf"

    @property
    def pip_patched_path(self) -> Path:
        """Get the path to the pip_patched script in the virtualenv."""
        return self.venv_bin / "pip_patched"

    @property
    def pip_wrapper_path(self) -> Path:
        """Get the path to the pip wrapper script in the virtualenv."""
        return self.venv_bin / "_pip-wrapper.py"

    @property
    @abstractmethod
    def host_python_wrapper(self) -> str:
        """Get the content of the host python wrapper script.
        This script allows invoking the host python with the correct PYTHONHOME.
        """
        pass

    @property
    @abstractmethod
    def host_pip_wrapper(self) -> str:
        """Get the content of the host pip wrapper script."""
        pass

    def validate_interpreter(self) -> None:
        """Validate that the Pyodide interpreter exists."""
        if not self.interpreter_path.exists():
            raise RuntimeError(
                f"Pyodide python interpreter not found at {self.interpreter_path}"
            )

    def get_cli_args(self) -> list[str]:
        """Build the CLI arguments for virtualenv."""
        cli_args = ["--python", str(self.interpreter_path)]

        if self.virtualenv_args:
            for arg in self.virtualenv_args:
                if arg.startswith("--"):
                    arg_name = arg.split("=")[0] if "=" in arg else arg
                    if arg_name not in SUPPORTED_VIRTUALENV_OPTIONS:
                        msg = f"Unsupported virtualenv option: {arg_name}"
                        logger.warning(msg)

            cli_args.extend(self.virtualenv_args)

        return cli_args

    def _create_pip_conf(self) -> None:
        """Create pip.conf file in venv root.

        This file adds a few options that will always be used by pip install.
        """
        if in_xbuildenv():
            # In the xbuildenv, we don't have the packages locally. We will include
            # in the xbuildenv a PEP 503 index for the vendored Pyodide packages
            # https://peps.python.org/pep-0503/
            repo = f"extra-index-url=file:{get_pyodide_root() / 'package_index'}"
        else:
            # In the Pyodide development environment, the Pyodide dist directory
            # should contain the needed wheels. find-links
            repo = f"find-links={pyodide_dist_dir()}"

        platform = f"pyodide_{get_build_flag("PYODIDE_ABI_VERSION")}_wasm32"
        # Prevent attempts to install binary wheels from source.
        # Maybe some day we can convince pip to invoke `pyodide build` as the build
        # front end for wheels...
        self.pip_conf_path.write_text(
            dedent(
                f"""
                [global]
                only-binary=:all:
                platform={platform}
                target={self.venv_sitepackages_path}
                {repo}
                """
            )
        )

    def _install_stdlib(self) -> None:
        """Install micropip and all unvendored stdlib modules."""
        logger.info("... Installing standard library")

        # Micropip we could install with pip hypothetically, but because we use
        # `--extra-index-url` it would install the pypi version which we don't want.

        # Other stuff we need to load with loadPackage
        to_load = ["micropip"]
        run_command(
            [
                self.interpreter_symlink_path,
                "-c",
                dedent(
                    f"""
                    from pyodide_js import loadPackage
                    from pyodide_js._api import lockfile_packages
                    from pyodide_js._api import lockfile_unvendored_stdlibs_and_test
                    shared_libs = [pkgname for (pkgname,pkg) in lockfile_packages.object_entries() if getattr(pkg, "package_type", None) == "shared_library"]

                    to_load = [*lockfile_unvendored_stdlibs_and_test, *shared_libs, *{to_load!r}]
                    loadPackage(to_load);
                    """
                ),
            ],
            err_msg="ERROR: failed to install unvendored stdlib modules",
        )

    def _get_pip_monkeypatch(self) -> str:
        """Monkey patch pip's environment to show info about Pyodide's environment.

        The code returned is injected at the beginning of the pip script.
        """
        result = run_command(
            [
                self.interpreter_symlink_path,
                "-c",
                dedent(
                    """
                    import os, sys, sysconfig, platform;
                    print([
                        os.name,
                        sys.platform,
                        platform.system(),
                        sys.implementation._multiarch,
                        sysconfig.get_platform()
                    ])
                    """.replace("\n", "")  # Windows doesn't seems to like newlines here...
                ),
            ],
            err_msg="ERROR: failed to invoke Pyodide",
        )
        platform_data = result.stdout
        sysconfigdata_dir = Path(get_build_flag("TARGETINSTALLDIR")) / "sysconfigdata"
        pip_patched_name = self.pip_patched_path.name
        exe_suffix = self.exe_suffix
        return dedent(
            """\
            import os
            import platform
            import sys
            """
            # when pip installs an executable it uses sys.executable to create the
            # shebang for the installed executable. The shebang for pip points to
            # python-host but we want the shebang of the executable that we install
            # to point to Pyodide python. We monkeypatch distlib.scripts.get_executable
            # to return the value with the host suffix removed.
            f"""
            from pip._vendor.distlib import scripts
            EXECUTABLE_SUFFIX = "{self.host_python_symlink_suffix}"
            def get_executable():
                if not sys.executable.endswith(EXECUTABLE_SUFFIX):
                    raise RuntimeError(f'Internal Pyodide error: expected sys.executable="{{sys.executable}}" to end with "{{EXECUTABLE_SUFFIX}}"')
                return sys.executable.removesuffix(EXECUTABLE_SUFFIX)

            scripts.get_executable = get_executable

            from pip._vendor.packaging import tags
            orig_platform_tags = tags.platform_tags
            """
            # TODO: Remove the following monkeypatch when we merge and pull in
            # https://github.com/pypa/packaging/pull/804
            """
            def _emscripten_platforms():
                pyodide_abi_version = sysconfig.get_config_var("PYODIDE_ABI_VERSION")
                if pyodide_abi_version:
                    yield f"pyodide_{pyodide_abi_version}_wasm32"
                yield from tags._generic_platforms()

            def platform_tags():
                if platform.system() == "Emscripten":
                    yield from _emscripten_platforms()
                    return
                return orig_platform_tags()

            tags.platform_tags = platform_tags
            """
            f"""
            os_name, sys_platform, platform_system, multiarch, host_platform = {platform_data}
            sys.platlibdir = "lib"
            sys.implementation._multiarch = multiarch
            sys.abiflags = getattr(sys, "abiflags", "")  # ensure abiflags exists even in Windows
            platform.system = lambda: platform_system
            platform.machine = lambda: "wasm32"
            os.environ["_PYTHON_HOST_PLATFORM"] = host_platform
            os.environ["_PYTHON_SYSCONFIGDATA_NAME"] = f'_sysconfigdata_{{sys.abiflags}}_{{sys.platform}}_{{sys.implementation._multiarch}}'
            sys.path.append("{sysconfigdata_dir}")
            import sysconfig
            sysconfig._init_config_vars()
            del os.environ["_PYTHON_SYSCONFIGDATA_NAME"]
            """
            # Handle pip updates.
            #
            # The pip executable should be a symlink to pip_patched. If it is not a
            # link, or it is a symlink to something else, pip has been updated. We
            # have to restore the correct value of pip. Iterate through all of the
            # pip variants in the folder and remove them and replace with a symlink
            # to pip_patched.
            f"""
            from pathlib import Path

            file_path = Path(__file__).parent / f"pip{exe_suffix}"


            def pip_is_okay():
                try:
                    return file_path.readlink() == file_path.with_name("{pip_patched_name}")
                except OSError as e:
                    if e.strerror != "Invalid argument":
                        raise
                return False


            def maybe_repair_after_pip_update():
                if pip_is_okay():
                    return

                venv_bin = file_path.parent
                pip_patched = venv_bin / "{pip_patched_name}"
                for pip in venv_bin.glob("pip*"):
                    if pip == pip_patched:
                        continue
                    pip.unlink(missing_ok=True)
                    patched_pip_exe = pip.with_suffix("{exe_suffix}")
                    if patched_pip_exe != pip_patched:
                        patched_pip_exe.unlink(missing_ok=True)
                        patched_pip_exe.symlink_to(pip_patched)


            import atexit

            atexit.register(maybe_repair_after_pip_update)
            """
        )

    def _create_pip_script(self) -> None:
        """Create pip and write it into the virtualenv bin folder."""
        # pip needs to run in the host Python not in Pyodide, so we'll use the host
        # Python in the shebang. Use whichever Python was used to invoke
        # pyodide venv.

        # To support the "--clear" and "--no-clear" args, we need to remove
        # the existing symlinks before creating new ones.
        self.host_python_path.unlink(missing_ok=True)
        self.host_python_path_noversion.unlink(missing_ok=True)
        self.host_python_symlink_path.unlink(missing_ok=True)

        # Replace all pip* scripts in the venv bin folder with symlinks to
        # our patched pip script.
        for pip in self.venv_bin.glob("pip*"):
            if pip == self.pip_patched_path:
                continue
            pip.unlink(missing_ok=True)

            patched_pip_exe = pip.with_suffix(self.exe_suffix)
            if patched_pip_exe != self.pip_patched_path:
                patched_pip_exe.unlink(missing_ok=True)
                patched_pip_exe.symlink_to(self.pip_patched_path)

        # Weird hack to work around:
        # https://github.com/astral-sh/python-build-standalone/issues/380
        # If we resolve the symlink all the way, the python-host interpreter works
        # but won't install into our pyodide venv. If we don't resolve the symlink,
        # sys.prefix is calculated incorrectly. To ensure that we get the right
        # sys.prefix, we explicitly set it with the PYTHONHOME environment variable
        # and then call the symlink.
        self.host_python_symlink_path.symlink_to(sys.executable)
        self.host_python_path.write_text(self.host_python_wrapper)
        self.host_python_path.chmod(0o777)
        self.host_python_path_noversion.symlink_to(self.host_python_path)

        self.pip_patched_path.write_text(self.host_pip_wrapper)
        self.pip_patched_path.chmod(0o777)

        pip_wrapper_name = self.pip_wrapper_path.name
        self.pip_wrapper_path.write_text(
            (
                self._get_pip_monkeypatch()
                + dedent(
                   f"""
                    import re
                    import sys
                    from pip._internal.cli.main import main
                    if __name__ == '__main__':
                        sys.argv[0] = sys.argv[0].replace('{pip_wrapper_name}', 'pip')
                        sys.exit(main())
                    """
                )
            ).replace('\\', '\\\\')  # Escape backslashes for Windows batch files
        )

    @abstractmethod
    def _create_pyodide_script(self) -> None:
        """Create pyodide CLI script in the virtualenv bin folder.

        This is platform-specific and must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def _create_python_symlink(self) -> None:
        """Create a symlink to the Pyodide Python interpreter."""
        pass

    @abstractmethod
    def _create_session(self) -> "virtualenv.session.Session":
        """Create and return a virtualenv session object."""
        pass

    def configure_virtualenv(self) -> None:
        """Configure the virtualenv after creation."""
        logger.info("... Configuring virtualenv")
        self._create_python_symlink()
        self._create_pip_conf()
        self._create_pip_script()
        self._create_pyodide_script()

    def create(self) -> None:
        """Create the Pyodide virtualenv."""
        logger.info("Creating Pyodide virtualenv at %s", self.dest)
        self.validate_interpreter()
        session = self._create_session()
        check_host_python_version(session)

        try:
            session.run()
            self._venv_root = Path(session.creator.dest).absolute()
            self._venv_bin = self._venv_root / self.bin_dir_name

            self.configure_virtualenv()
            self._install_stdlib()
        except (Exception, KeyboardInterrupt, SystemExit):
            shutil.rmtree(session.creator.dest)
            raise

        logger.success("Successfully created Pyodide virtual environment!")


class UnixPyodideVenv(PyodideVenv):
    """Unix-specific implementation of Pyodide virtual environment creation."""

    @property
    def bin_dir_name(self) -> str:
        """Return the bin directory name for the platform."""
        return "bin"

    @property
    def host_python_symlink_suffix(self) -> str:
        """Get the host python symlink name."""
        return "-host-link"

    @property
    def host_python_wrapper(self) -> str:
        """Get the content of the host python wrapper script.
        This script allows invoking the host python with the correct PYTHONHOME.
        """
        pythonhome = Path(sys._base_executable).parents[1]
        return dedent(
            f"""\
            #!/bin/sh
            exec env PYTHONHOME={pythonhome} {self.host_python_symlink_path} "$@"
            """
        )

    @property
    def host_pip_wrapper(self) -> str:
        # Other than the shebang and the monkey patch, this is exactly what
        # normal pip looks like.
        return (
            f"#!{self.host_python_path} -s\n"
            f"{self.pip_wrapper_path} $@\n"
        )

    def _create_python_symlink(self) -> None:
        """Create a symlink to the Pyodide Python interpreter.

        Noop on Unix as virtualenv already does this for us.
        """
        return

    def _create_session(self) -> "virtualenv.session.Session":
        """Create and return a virtualenv session object."""
        from virtualenv import session_via_cli

        return session_via_cli(self.get_cli_args() + [str(self.dest)])

    def create_pyodide_script(self) -> None:
        """Write pyodide cli script into the virtualenv bin folder."""

        # Temporarily restore us to the environment that 'pyodide venv' was
        # invoked in
        PATH = os.environ["PATH"]
        PYODIDE_ROOT = os.environ["PYODIDE_ROOT"]

        original_pyodide_cli = shutil.which("pyodide")
        if original_pyodide_cli is None:
            raise RuntimeError("ERROR: pyodide cli not found")

        self.pyodide_cli_path.write_text(
            dedent(
                f"""
                #!/usr/bin/env bash
                PATH="{PATH}:$PATH" PYODIDE_ROOT='{PYODIDE_ROOT}' exec {original_pyodide_cli} "$@"
                """
            )
        )
        self.pyodide_cli_path.chmod(0o777)


class WindowsPyodideVenv(PyodideVenv):
    """Windows-specific implementation of Pyodide virtual environment creation."""
    @property
    def exe_suffix(self) -> str:
        """Return the executable suffix for the platform."""
        return ".bat"

    @property
    def bin_dir_name(self) -> str:
        """Return the bin directory name."""
        return "Scripts"

    @property
    def host_python_symlink_suffix(self) -> str:
        """Get the host python symlink name."""
        return "-host-link.exe"

    @property
    def host_python_wrapper(self) -> str:
        """Get the content of the host python wrapper script.

        TODO: In windows, it doesn't seem setting PYTHONHOME is required to make it correctly work.
        """
        return dedent(f"""\
            @echo off
            "{self.host_python_symlink_path}" %*
            """)

    @property
    def pip_conf_path(self) -> Path:
        """Get the path to the pip.conf file in the virtualenv."""
        return self.venv_root / "pip.ini"

    @property
    def host_pip_wrapper(self) -> str:
        return (
            "@echo off\n"
            + f'"{self.host_python_path}" -s '
            + f'"{self.pip_wrapper_path}" %*\n'
        )

    def _create_session(self):
        from virtualenv import session_via_cli

        from .app_data import create_app_data_dir

        cli_args = self.get_cli_args()
        with create_app_data_dir(str(self.interpreter_path)) as app_data_dir:
            cli_args += ["--app-data", app_data_dir]
            session = session_via_cli(cli_args + [str(self.dest)])

        return session

    def _create_python_symlink(self) -> None:
        """Create a symlink to the Pyodide Python interpreter."""

        # the virtualenv does not understand the batch file, so we need to
        # symlink it ourselves
        self.interpreter_symlink_path.unlink(missing_ok=True)
        self.interpreter_symlink_path.symlink_to(self.interpreter_path)

        # Also symlink any other python*.exe files to the interpreter
        other_pythons = self.venv_bin.glob("python*.exe")
        for python_exe in other_pythons:
            python_exe.unlink(missing_ok=True)
            python_bat = python_exe.with_suffix(self.exe_suffix)
            if python_bat != self.interpreter_symlink_path:
                python_bat.unlink(missing_ok=True)
                python_bat.symlink_to(self.interpreter_path)

    def _create_pyodide_script(self) -> None:
        """Write pyodide cli script into the virtualenv bin folder."""
        PATH = os.environ["PATH"]
        PYODIDE_ROOT = os.environ["PYODIDE_ROOT"]

        original_pyodide_cli = shutil.which("pyodide")
        if original_pyodide_cli is None:
            raise RuntimeError("ERROR: pyodide cli not found")

        self.pyodide_cli_path.write_text(
            dedent(
                f"""
                @echo off
                set PATH={PATH};%PATH%
                set PYODIDE_ROOT={PYODIDE_ROOT}
                "{original_pyodide_cli}" %*
                """
            )
        )


def create_pyodide_venv(dest: Path, virtualenv_args: list[str] | None = None) -> None:
    """Create a Pyodide virtualenv and store it into dest"""
    builder = WindowsPyodideVenv if IS_WIN else UnixPyodideVenv
    venv = builder(dest, virtualenv_args)
    venv.create()
