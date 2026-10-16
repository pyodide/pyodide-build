import os
import re
import subprocess
from pathlib import Path
from textwrap import dedent


def fix_f2c_input(f2c_input: Path) -> None:
    if f2c_input.name.endswith("_flapack-f2pywrappers.f"):
        content = f2c_input.read_text()
        content = content.replace("character cmach", "integer cmach")
        content = content.replace("character norm", "integer norm")
        f2c_input.write_text(content)
        return

    if f2c_input.name in [
        "_lapack_subroutine_wrappers.f",
        "_blas_subroutine_wrappers.f",
    ]:
        content = f2c_input.read_text()
        content = content.replace("character", "integer")
        content = content.replace(
            "ret = chla_transtype(", "call chla_transtype(ret, 1,"
        )
        f2c_input.write_text(content)


def fix_f2c_output(f2c_output: Path) -> None:
    """
    This function is called on the name of each C output file. It fixes up the C
    output in various ways to compensate for the lack of f2c support for Fortran
    90 and Fortran 95.
    """
    if f2c_output.name == "_lapack_subroutine_wrappers.c":
        content = f2c_output.read_text()
        content = content.replace("integer chla_transtype__", "void chla_transtype__")
        f2c_output.write_text(content)
        return

    if f2c_output.name.endswith("eupd.c"):
        content = f2c_output.read_text()
        content = re.sub(
            r"ftnlen\s*(howmny_len|bmat_len),?", "", content, flags=re.MULTILINE
        )
        f2c_output.write_text(content)
        return

    if f2c_output.name.endswith("lansvd.c"):
        content = f2c_output.read_text()
        content += dedent(
            """
            #include <time.h>

            int second_(real *t) {
                *t = clock()/1000;
                return 0;
            }
            """
        )
        f2c_output.write_text(content)
        return


def replay_f2c(args: list[str], dryrun: bool = False) -> list[str] | None:
    """Apply f2c to compilation arguments

    Parameters
    ----------
    args
       input compiler arguments
    dryrun
       if False run f2c on detected fortran files

    Returns
    -------
    new_args
       output compiler arguments


    Examples
    --------

    >>> replay_f2c(['gfortran', 'test.f'], dryrun=True)
    ['gcc', 'test.c']
    """
    f2c_path = os.environ.get("F2C_PATH", "f2c")

    new_args = ["gcc"]
    found_source = False
    for arg in args[1:]:
        if not arg.endswith((".f", ".F")):
            new_args.append(arg)
            continue
        found_source = True
        filepath = Path(arg).resolve()
        new_args.append(arg[:-2] + ".c")
        if dryrun:
            continue
        fix_f2c_input(Path(arg))
        if arg.endswith(".F"):
            # .F files apparently expect to be run through the C
            # preprocessor (they have #ifdef's in them)
            # Use gfortran frontend, as gcc frontend might not be
            # present on osx
            # The file-system might be not case-sensitive,
            # so take care to handle this by renaming.
            # For preprocessing and further operation the
            # expected file-name and extension needs to be preserved.
            subprocess.check_call(
                [
                    "gfortran",
                    "-E",
                    "-C",
                    "-P",
                    filepath,
                    "-o",
                    filepath.with_suffix(".f77"),
                ]
            )
            filepath = filepath.with_suffix(".f77")
        # -R flag is important, it means that Fortran functions that
        # return real e.g. sdot will be transformed into C functions
        # that return float. For historic reasons, by default f2c
        # transform them into functions that return a double. Using -R
        # allows to match what OpenBLAS has done when they f2ced their
        # Fortran files, see
        # https://github.com/xianyi/OpenBLAS/pull/3539#issuecomment-1493897254
        # for more details
        with (
            open(filepath) as input_pipe,
            open(filepath.with_suffix(".c"), "w") as output_pipe,
        ):
            subprocess.check_call(
                [f2c_path, "-R"],
                stdin=input_pipe,
                stdout=output_pipe,
                cwd=filepath.parent,
            )
        fix_f2c_output(Path(arg[:-2] + ".c"))

    new_args_str = " ".join(args)
    if ".so" in new_args_str and "libgfortran.so" not in new_args_str:
        found_source = True

    if not found_source:
        return None
    return new_args
