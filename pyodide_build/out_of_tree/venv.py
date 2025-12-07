import shutil
import sys
import textwrap
from pathlib import Path
from typing import Any

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


def create_pip_conf(venv_root: Path) -> None:
    """Create pip.conf file in venv root

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

    # Prevent attempts to install binary wheels from source.
    # Maybe some day we can convince pip to invoke `pyodide build` as the build
    # front end for wheels...
    (venv_root / "pip.conf").write_text(
        dedent(
            f"""
            [install]
            only-binary=:all:
            {repo}
            """
        )
    )


def get_pip_monkeypatch(venv_bin: Path) -> str:
    """Monkey patch pip's environment to show info about Pyodide's environment.

    The code returned is injected at the beginning of the pip script.
    """
    result = run_command(
        [
            venv_bin / "python",
            "-c",
            dedent(
                """
                import os, sys, sysconfig, platform
                print([
                    os.name,
                    sys.platform,
                    platform.system(),
                    sys.implementation._multiarch,
                    sysconfig.get_platform()
                ])
                """
            ),
        ],
        err_msg="ERROR: failed to invoke Pyodide",
    )
    platform_data = result.stdout
    sysconfigdata_dir = Path(get_build_flag("TARGETINSTALLDIR")) / "sysconfigdata"
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
        """
        from pip._vendor.distlib import scripts
        EXECUTABLE_SUFFIX = "-host-link"
        def get_executable():
            if not sys.executable.endswith(EXECUTABLE_SUFFIX):
                raise RuntimeError(f'Internal Pyodide error: expected sys.executable="{sys.executable}" to end with "{EXECUTABLE_SUFFIX}"')
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
        os.name = os_name
        sys.platform = sys_platform
        sys.platlibdir = "lib"
        sys.implementation._multiarch = multiarch
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
        """
        from pathlib import Path

        file_path = Path(__file__)


        def pip_is_okay():
            try:
                return file_path.readlink() == file_path.with_name("pip_patched")
            except OSError as e:
                if e.strerror != "Invalid argument":
                    raise
            return False


        def maybe_repair_after_pip_update():
            if pip_is_okay():
                return

            venv_bin = file_path.parent
            pip_patched = venv_bin / "pip_patched"
            for pip in venv_bin.glob("pip*"):
                if pip == pip_patched:
                    continue
                pip.unlink(missing_ok=True)
                pip.symlink_to(venv_bin / "pip_patched")


        import atexit

        atexit.register(maybe_repair_after_pip_update)
        """
    )


def create_pip_script(venv_bin):
    """Create pip and write it into the virtualenv bin folder."""
    # pip needs to run in the host Python not in Pyodide, so we'll use the host
    # Python in the shebang. Use whichever Python was used to invoke
    # pyodide venv.
    host_python_path = venv_bin / f"python{get_pyversion()}-host"
    host_python_path_no_version = venv_bin / "python-host"
    pip_path = venv_bin / "pip_patched"
    python_host_link = venv_bin / "python-host-link"

    # To support the "--clear" and "--no-clear" args, we need to remove
    # the existing symlinks before creating new ones.
    host_python_path.unlink(missing_ok=True)
    host_python_path_no_version.unlink(missing_ok=True)
    python_host_link.unlink(missing_ok=True)
    for pip in venv_bin.glob("pip*"):
        if pip == pip_path:
            continue
        pip.unlink(missing_ok=True)
        pip.symlink_to(pip_path)

    # Weird hack to work around:
    # https://github.com/astral-sh/python-build-standalone/issues/380
    # If we resolve the symlink all the way, the python-host interpreter works
    # but won't install into our pyodide venv. If we don't resolve the symlink,
    # sys.prefix is calculated incorrectly. To ensure that we get the right
    # sys.prefix, we explicitly set it with the PYTHONHOME environment variable
    # and then call the symlink.
    python_host_link.symlink_to(sys.executable)
    pythonhome = Path(sys._base_executable).parents[1]
    host_python_path.write_text(
        dedent(
            f"""\
            #!/bin/sh
            exec env PYTHONHOME={pythonhome} {python_host_link} "$@"
            """
        )
    )
    host_python_path.chmod(0o777)
    host_python_path_no_version.symlink_to(host_python_path)

    pip_path.write_text(
        # Other than the shebang and the monkey patch, this is exactly what
        # normal pip looks like.
        f"#!/usr/bin/env -S {host_python_path} -s\n"
        + get_pip_monkeypatch(venv_bin)
        + dedent(
            """
            import re
            import sys
            from pip._internal.cli.main import main
            if __name__ == '__main__':
                sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])
                sys.exit(main())
            """
        )
    )
    pip_path.chmod(0o777)


def create_pyodide_script(venv_bin: Path) -> None:
    """Write pyodide cli script into the virtualenv bin folder"""
    import os

    # Temporarily restore us to the environment that 'pyodide venv' was
    # invoked in
    PATH = os.environ["PATH"]
    PYODIDE_ROOT = os.environ["PYODIDE_ROOT"]

    original_pyodide_cli = shutil.which("pyodide")
    if original_pyodide_cli is None:
        raise RuntimeError("ERROR: pyodide cli not found")

    pyodide_path = venv_bin / "pyodide"
    pyodide_path.write_text(
        dedent(
            f"""
            #!/usr/bin/env bash
            PATH="{PATH}:$PATH" PYODIDE_ROOT='{PYODIDE_ROOT}' exec {original_pyodide_cli} "$@"
            """
        )
    )
    pyodide_path.chmod(0o777)


def install_stdlib(venv_bin: Path) -> None:
    """Install micropip and all unvendored stdlib modules"""
    # Micropip we could install with pip hypothetically, but because we use
    # `--extra-index-url` it would install the pypi version which we don't want.

    # Other stuff we need to load with loadPackage
    to_load = ["micropip"]
    run_command(
        [
            venv_bin / "python",
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


def create_pyodide_venv(dest: Path, virtualenv_args: list[str] | None = None) -> None:
    """Create a Pyodide virtualenv and store it into dest"""
    logger.info("Creating Pyodide virtualenv at %s", dest)
    from virtualenv import session_via_cli

    python_exe_name = "python.bat" if IS_WIN else "python"
    interp_path = pyodide_dist_dir() / python_exe_name

    if not interp_path.exists():
        raise RuntimeError(f"Pyodide python interpreter not found at {interp_path}")

    cli_args = ["--python", str(interp_path)]

    if virtualenv_args:
        for arg in virtualenv_args:
            if arg.startswith("--"):
                # Check if the argument (or its prefix form) is supported.
                arg_name = arg.split("=")[0] if "=" in arg else arg
                if arg_name not in SUPPORTED_VIRTUALENV_OPTIONS:
                    msg = f"Unsupported virtualenv option: {arg_name}"
                    logger.warning(msg)

        cli_args.extend(virtualenv_args)

    session = session_via_cli(cli_args + [str(dest)])
    check_host_python_version(session)

    try:
        session.run()
        venv_root = Path(session.creator.dest).absolute()
        venv_bin = venv_root / "bin"

        logger.info("... Configuring virtualenv")
        create_pip_conf(venv_root)
        create_pip_script(venv_bin)
        create_pyodide_script(venv_bin)
        logger.info("... Installing standard library")
        install_stdlib(venv_bin)
    except (Exception, KeyboardInterrupt, SystemExit):
        shutil.rmtree(session.creator.dest)
        raise

    logger.success("Successfully created Pyodide virtual environment!")
