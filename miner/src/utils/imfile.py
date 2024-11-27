""" Processing of intermediate compilation files.
"""

import re
import subprocess
import os, os.path as osp
from itertools import starmap
from easymp import addlogging

from utils.utils import *
from utils.parsers import parser
from config import SOURCE_FUNCTION_EXCLUDE_DIRS


@addlogging
def clang_format(function):
    res = subprocess.run(
        ["clang-format"], input=function.encode("utf-8"), capture_output=True
    )
    if res.returncode != 0:
        logger.warning("clang-format failed.")
        return function
    function_fmt = res.stdout.decode("utf-8")
    return function_fmt


def process_source_file(fpath):
    """Extract functions from C/C++ source file

    The file name is expected to be changed from .i/.ii to .c/.cpp and the
    .i/.ii information lines (i. e. lines starting with #) are expected to be
    preceded with //.
    """
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().split("\n")

    # Create a mapping preprocessed file line number -> source file line number
    # From https://gcc.gnu.org/onlinedocs/gcc-4.1.2/cpp/Preprocessor-Output.html
    # Preprocessed file comment structure:
    #   linenum filename flags
    # flags:
    # `1'
    #     This indicates the start of a new file.
    # `2'
    #     This indicates returning to a file (after having included another file).
    # `3'
    #     This indicates that the following text comes from a system header file, so certain warnings should be suppressed.
    # `4'
    #     This indicates that the following text should be treated as being wrapped in an implicit extern "C" block.
    comments = starmap(lambda lineno, line: (lineno, line), enumerate(lines, start=1))
    comments = filter(
        lambda lineno_line: re.match('^//# [0-9]+ "', lineno_line[1]) != None, comments
    )
    comments = starmap(
        lambda lineno, line: (lineno, line + " 1")
        if line.endswith('"')
        else (lineno, line),
        comments,
    )
    comments = {
        lineno: re.search('^//# ([0-9]+) "(.+)" ([0-9]+).*', line).groups(0)
        for lineno, line in comments
    }
    linenums = sorted([lineno for lineno in comments])

    # Use tree-sitter parser to parse C/C++ preprocessed file
    functions = parser.iter_functions_file(fpath)

    def pp_to_real(pp_lineno):
        # We count lines from zero, but the pp format lines are counted
        # starting from one, hence the '+ 1'
        pp_lineno += 1
        comment_linenums_before_function = list(
            filter(lambda lineno: lineno < pp_lineno, linenums)
        )
        if len(comment_linenums_before_function) == 0:
            return None
        comment_lineno = max(comment_linenums_before_function)
        closest_lineno, fname, flags = comments[comment_lineno]
        real_lineno = int(closest_lineno) + (pp_lineno - comment_lineno - 1)
        return fname, flags, real_lineno

    # Extract the function from the source file
    def extract(function):
        pp_start_lineno = function["start"]
        pp_end_lineno = function["end"]
        pp_start_col = function["start_col"]
        pp_end_col = function["end_col"]
        fname_start, flags_start, lineno_start = pp_to_real(pp_start_lineno)
        fname_end, flags_end, lineno_end = pp_to_real(pp_end_lineno)
        if lineno_start == None or lineno_end == None or fname_start != fname_end:
            return hashdict()
        source = "\n".join(
            [
                lines[pp_start_lineno][pp_start_col:],
                *[
                    line
                    for line in lines[pp_start_lineno + 1 : pp_end_lineno - 1]
                    if re.match('^//# [0-9]+ "', line) == None
                ],
                lines[min(pp_end_lineno - 1, len(lines) - 1)][:pp_end_col],
            ]
        )

        function = hashdict(
            origin=hashdict(
                fpath=fname_start,
                name=function["name"],
                start=lineno_start,
                end=lineno_end,
                flags=int(flags_start),
            ),
            source=source,
        )
        return function

    functions = map(extract, functions)
    functions = filter(lambda function: function != {}, functions)
    functions = filter(lambda function: function["origin"]["flags"] != 3, functions)
    functions = filter(
        lambda function: not any(
            map(
                lambda exclude_dir: function["origin"]["fpath"].startswith(exclude_dir),
                SOURCE_FUNCTION_EXCLUDE_DIRS,
            )
        ),
        functions,
    )
    functions = filter(lambda function: is_definition(function["source"]), functions)
    return functions


def post_preprocessor_file_get_functions(fpath):
    # TODO Since we changed from joern to treesitter for first parsing,
    # this might not be necessary anymore
    # Relevent files are referenced.
    # 1) We're setting a file extension
    # 2) We're prefixing the preprocessor comments (# ..) with // so
    #    that the treesitter doesn't get confused
    fpath_new = re.sub(".ii$", ".cpp", fpath)
    fpath_new = re.sub(".i$", ".c", fpath_new)
    os.rename(fpath, fpath_new)
    fwrite(fpath_new, re.sub("^#", "//#", fread(fpath_new), flags=re.MULTILINE))

    # Use treesitter to parse the files and extract functions
    return list(process_source_file(fpath_new))
