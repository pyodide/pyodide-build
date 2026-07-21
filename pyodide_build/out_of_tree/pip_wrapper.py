# This file is copied to the venv build directory and executed there, so it
# must not import any pyodide-build source files.
import json
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    executable_symlink_suffix: str
    exe_suffix: str
    pip_patched_name: str
    pip_wrapper_name: str
    platform_data: tuple[str, str, str, str, str]
    pyodide_platform: str
    sysconfigdata_dir: str


CONFIG = Config(
    **json.loads((Path(__file__).parent / "pyodide_pip_config.json").read_text())
)


# when pip installs an executable it uses sys.executable to create the
# shebang for the installed executable. The shebang for pip points to
# python-host but we want the shebang of the executable that we install
# to point to Pyodide python. We monkeypatch distlib.scripts.get_executable
# to return the value with the host suffix removed.
from pip._vendor.distlib import scripts


def get_executable():
    if not sys.executable.endswith(CONFIG.executable_symlink_suffix):
        raise RuntimeError(
            f'Internal Pyodide error: expected sys.executable="{sys.executable}" to end with "{CONFIG.executable_symlink_suffix}"'
        )
    return sys.executable.removesuffix(CONFIG.executable_symlink_suffix)


scripts.get_executable = get_executable

# Patch packaging.tags.
# Packaging < 26.2 needs to be taught about _emscripten_platforms
# TODO: Can we assume Pip >= 26.1 and delete this?
from pip._vendor.packaging import __version__ as _packaging_version

try:
    _packaging_version_tuple = tuple(int(x) for x in _packaging_version.split("."))
    should_patch = _packaging_version_tuple < (26, 2)
except ValueError:
    should_patch = False


if should_patch:
    from pip._vendor.packaging import tags

    orig_platform_tags = tags.platform_tags

    def platform_tags():
        if platform.system() == "Emscripten":
            yield from _emscripten_platforms()
            return
        return orig_platform_tags()

    tags.platform_tags = platform_tags

# Pip >= 26.1 has an _emscripten_platforms function but it does not
# produce the legacy pyodide_xxx_wasm32 tag.
from collections.abc import Iterator

from pip._vendor.packaging.tags import _generic_platforms


def _emscripten_platforms() -> Iterator[str]:
    pyemscripten_platform_version = sysconfig.get_config_var(
        "PYEMSCRIPTEN_PLATFORM_VERSION"
    ) or sysconfig.get_config_var("PYODIDE_ABI_VERSION")
    if pyemscripten_platform_version:
        yield f"pyodide_{pyemscripten_platform_version}_wasm32"
        yield f"pyemscripten_{pyemscripten_platform_version}_wasm32"
    yield from _generic_platforms()


from pip._vendor.packaging import tags

tags._emscripten_platforms = _emscripten_platforms

# Now patch sys, platform, os.environ, and sysconfig.

os_name, sys_platform, platform_system, multiarch, host_platform = CONFIG.platform_data

os.getuid = os.getuid if hasattr(os, "getuid") else lambda: 0
sys.platlibdir = "lib"
sys.implementation._multiarch = multiarch  # type: ignore[attr-defined]
sys.abiflags = getattr(sys, "abiflags", "")  # ensure abiflags exists even in Windows
platform.system = lambda: platform_system
platform.machine = lambda: "wasm32"
os.environ["_PYTHON_HOST_PLATFORM"] = host_platform
os.environ["_PYTHON_SYSCONFIGDATA_NAME"] = (
    f"_sysconfigdata_{sys.abiflags}_{sys_platform}_{sys.implementation._multiarch}"
)
sys.path.append(CONFIG.sysconfigdata_dir)
import sysconfig

sysconfig._init_config_vars()  # type: ignore[attr-defined]
del os.environ["_PYTHON_SYSCONFIGDATA_NAME"]

# On windows, patching sys.platform or os.name breaks how pip internals work (e.g. Pathlib)
# So instead, we use `--platform` option to inject the correct platform to pip commands.
# However, pip does not allow cross-platform installation unless `--target` flag is given,
# but `--target` behaves differently from normal installation (e.g. it does not support upgrading/downgrading packages very well, etc).
# so we ended up monkey-patching the cli option check function to allow using `--platform` without `--target`.
if os.name == "nt":
    from pip._internal.cli import cmdoptions

    _original_check = cmdoptions.check_dist_restriction

    def _patched_check_dist_restriction(options, check_target=False):
        _original_check(options, check_target=False)  # always skip target check

    cmdoptions.check_dist_restriction = _patched_check_dist_restriction

    if len(sys.argv) > 1 and sys.argv[1] in ("install", "wheel", "download", "lock"):
        if "--platform" not in sys.argv:
            sys.argv.extend(["--platform", CONFIG.pyodide_platform])
        if "--only-binary" not in sys.argv:
            sys.argv.extend(["--only-binary", ":all:"])
else:
    # Newer versions of pip vendor Emscripten-supporting urllib3, so
    # import urllib3 before patching sys.platform to make sure we don't
    # run the Emscripten-compatibility path. It won't work because we
    # are really in a native Python.
    import pip._vendor.urllib3  # noqa: F401

    sys.platform = sys_platform

# Handle pip updates.
#
# The pip executable should be a symlink to pip_patched. If it is not a
# link, or it is a symlink to something else, pip has been updated. We
# have to restore the correct value of pip. Iterate through all of the
# pip variants in the folder and remove them and replace with a symlink
# to pip_patched.
# Avoid using pathlib as it might mess up the path calculation on cross-platform environments.
file_path = os.path.join(os.path.dirname(__file__), f"pip{CONFIG.exe_suffix}")


def pip_is_okay():
    try:
        return os.readlink(file_path) == os.path.join(
            os.path.dirname(file_path), CONFIG.pip_patched_name
        )
    except OSError as e:
        if e.strerror != "Invalid argument":
            raise
    return False


def maybe_repair_after_pip_update():
    if pip_is_okay():
        return

    venv_bin = os.path.dirname(file_path)
    pip_patched = os.path.join(venv_bin, CONFIG.pip_patched_name)
    for pip in os.listdir(venv_bin):
        if not pip.startswith("pip"):
            continue
        if pip == CONFIG.pip_patched_name:
            continue
        pip_path = os.path.join(venv_bin, pip)
        try:
            os.unlink(pip_path)
        except FileNotFoundError:
            pass
        patched_pip_exe = os.path.join(venv_bin, f"pip{CONFIG.exe_suffix}")
        if patched_pip_exe != pip_patched:
            try:
                os.unlink(patched_pip_exe)
            except FileNotFoundError:
                pass
            os.symlink(pip_patched, patched_pip_exe)


import atexit

atexit.register(maybe_repair_after_pip_update)


from pip._internal.cli.main import main

if __name__ == "__main__":
    sys.argv[0] = sys.argv[0].replace(CONFIG.pip_wrapper_name, "pip")
    sys.exit(main())
