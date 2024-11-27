import click
import json
import os, os.path as osp
import functools as ft
import itertools as it
import sys
import re
import tarfile
from tqdm import tqdm
from utils.imfile import process_source_file, clang_format
from utils.utils import *
from utils.modules import *
from utils.filter import filter_it
from fsdict import fsdict
from easymp import addlogging, parallel, execute


def identify_target(source):
    patterns = [
        r"if\s*\(",
        r"switch\s*\(",
        r"for\s*\(",
        r"while\s*\(",
        r"\s*return",
    ]
    lines = source.split("\n")
    for line_no, line in enumerate(lines):
        if any(re.match(pattern, source) for pattern in patterns):
            return line_no
    else:
        return len(lines) // 2


def read_log(fuzzer):
    crash_log = json.loads(fuzzer["out"]["testcase.json"])
    summary = crash_log["summary"]
    frames = crash_log["tracebacks"][0] if summary else []
    return summary, frames


def func_equal(func1, func2):
    fpath1 = func1["fpath"]
    fpath2 = func2["origin"]["fpath"]
    norm_fpath1 = osp.normpath(fpath1)
    norm_fpath2 = osp.normpath(fpath2)
    certainty = 0
    path_eq = False
    function_eq = False

    if norm_fpath1 == norm_fpath2:
        certainty += 1
        path_eq = True
    elif osp.basename(fpath1) == osp.basename(fpath2):
        certainty += 0.5
        path_eq = True
    if func2["origin"]["start"] <= func1["linenum"] <= func2["origin"]["end"]:
        certainty += 1
        function_eq = True

    return path_eq and function_eq, certainty


def annotate(function, traceback):
    if not "annotation" in function:
        function["annotation"] = hashdict()
    annotation = hashdict(
        frameno=-1,
        framenos=hashlist(),
        crashsite=False,
    )

    frames = map(
        lambda frame: (func_equal(frame["function"], function), frame), traceback
    )
    frames = list(filter(lambda frame: frame[0][0], frames))
    if len(frames) >= 1:
        # Choose the frame which matches the function best
        max_certainty = max(frames, key=lambda el: el[0][1])[0][1]
        frames = filter(lambda frame: frame[0][1] == max_certainty, frames)
        frames = list(map(lambda frame: frame[1], frames))
        # If the function occurs in the traceback more than once, take the lowest
        # frame number
        frame = frames[0]
        annotation = hashdict(
            frameno=frame["frameno"],
            framenos=hashlist(frame["frameno"] for frame in frames),
            crashsite=frame["frameno"] == 0,
        )

    function["annotation"] = annotation

    return function


def annotate_functions(functions, traceback):
    # Annotate the functions
    annotate_part = ft.partial(annotate, traceback=traceback)
    functions = set(map(annotate_part, functions))

    return functions


@addlogging
def filter_functions(functions, project_name):
    # Exclude functions which do not originated from the /src/ directory or any
    # of its subdirectories
    functions = filter(
        lambda function: function["origin"]["fpath"].startswith(BUILD_PREFIX), functions
    )

    # Remove functions whose fpath begins with ... and,
    # hence, are not part of the fuzzed project.
    ignore_build_prefixes = (
        IGNORE_BUILD_PREFIXES
        if "llvm" in project_name.lower()
        else IGNORE_BUILD_PREFIXES_RESTRICTIVE
    )
    functions = filter(
        lambda function: not any(
            function["origin"]["fpath"].startswith(prefix)
            for prefix in ignore_build_prefixes
        ),
        functions,
    )
    return set(functions)


@with_tempdir
@addlogging
def extract_source(directory, fuzzer):
    src_fpath = fuzzer["out"].abspath / "preprocessed.tar.gz"
    functions = set()

    if not ("out" in fuzzer and "preprocessed.tar.gz" in fuzzer["out"]):
        return functions

    with tarfile.open(src_fpath, "r:gz") as tar:
        members = list(member for member in tar if member.isreg())

        # Iterate over every preprocessed source file in the archive
        for member in members:
            # Extract file
            fpath = osp.join(directory, member.name)
            tar.extract(member, path=directory)

            # Rename file
            fpath_new = re.sub(".ii$", ".cpp", fpath)
            fpath_new = re.sub(".i$", ".c", fpath_new)
            os.rename(fpath, fpath_new)
            fpath = fpath_new

            # Prefix preprocessed #-lines with // to be parseable by treesitter
            source = fread(fpath)
            match = re.search('^# [0-9]+ ".+" [0-9]+', source, flags=re.MULTILINE)
            if not match:
                # Likely not a valid preprocessed source file
                continue
            source = re.sub("^#", "//#", source, flags=re.MULTILINE)
            fwrite(fpath, source)

            # Get a list of all the functions found in the preprocessed source file
            try:
                new_functions = process_source_file(fpath)
            except Exception:
                logger.warning(
                    f"Could not process {fpath} successfully. Maybe it was not a valid preprocessed source file or did not contain any functions."
                )
                continue
            for function in new_functions:
                functions.add(function)

            # Remove extracted file
            os.remove(fpath)

    return functions


def extract_fuzzer(fuzzer, target, project_name, overwrite):
    meta = fuzzer["meta"]

    if not "stats" in meta:
        meta["stats"] = {}

    if not "traceback" in meta or overwrite:
        # Extract traceback from fuzzing log
        summary, traceback = read_log(fuzzer)
        meta["traceback"] = traceback
    else:
        traceback = meta["traceback"]

    if not "functions" in fuzzer or overwrite:
        # Extract source code functions from .i/.ii files
        functions = extract_source(fuzzer)

        if len(functions) == 0:
            logger.warning(f"Couldn't extract any functions of project {project_name}.")
            return

        # Filter functions
        meta["stats"]["functionsPreFilterCount"] = len(functions)
        functions = filter_functions(functions, project_name)
        meta["stats"]["functionsPostFilterCount"] = len(functions)

        # Annotate functions according to a traceback
        functions = annotate_functions(functions, traceback)
        meta["stats"]["annotatedFunctionsCount"] = len(
            list(
                filter(
                    lambda function: function["annotation"]["frameno"] >= 0, functions
                )
            )
        )
        meta["stats"]["annotatedCrashsite"] = any(
            map(lambda function: function["annotation"]["crashsite"], functions)
        )

        # Save results
        fuzzer["functions"] = functions
        fuzzer["meta"] = meta


@parallel
@addlogging
def extract(crash, overwrite):
    meta = crash["meta"]
    local_id = meta["localId"]
    project_name = meta["project"]
    project = crash["project"]

    if not "reproduced" in meta or not meta["reproduced"]:
        logger.warning(
            f"Cannot extract code for crash {local_id} of project {project_name}. It has not been reproduced by the original fuzzer yet."
        )
        return

    target = meta["target"]
    engine = meta["engine"]
    sanitizer = meta["sanitizer"]
    instrumentation = "inst"
    commit = meta["commit"]
    fuzzer = get_fuzzer(crash, target, engine, sanitizer, instrumentation, commit, {})

    # Only extract the source code of the "original" fuzzer.
    # That is, the one which originally found the crash.
    logger.info(f"Extract source code for crash {local_id} of project {project_name}.")
    extract_info = extract_fuzzer(
        fuzzer,
        target,
        project_name,
        overwrite,
    )

    logger.info(
        f"Extracting source code for crash {local_id} of project {project_name}."
    )


def add_function_to_database(function, project, local_id, function_database):
    origin = function["origin"]
    annotation = function["annotation"]
    source = function["source"]
    source_hash = md5sum(source).hex()
    origin["project"] = project
    origin["crash"] = local_id
    origin["annotation"] = annotation

    if not source_hash in function_database:
        function_database[source_hash] = fsdict()
        function_database[source_hash]["source"] = source.encode("utf-8")
        meta = hashdict(origins=set(), target=identify_target(source))
    else:
        meta = function_database[source_hash]["meta"]

    meta["origins"].add(origin)
    function_database[source_hash]["meta"] = meta

    return source_hash


def add_functions_to_database(project, local_id, functions, function_database):
    add_function_to_database_part = ft.partial(
        add_function_to_database,
        project=project,
        local_id=local_id,
        function_database=function_database,
    )
    function_ids = map(add_function_to_database_part, functions)
    return set(function_ids)


def create_function_database(crashes, function_database, progress):
    if progress:
        crashes = tqdm(crashes, file=sys.stdout)
    for crash in crashes:
        meta = crash["meta"]
        if not "reproduced" in meta or not meta["reproduced"]:
            continue

        project = meta["project"]
        local_id = meta["localId"]
        engine = meta["engine"]
        sanitizer = meta["sanitizer"]
        target = meta["target"]
        commit = meta["commit"]
        instrumentation = "inst"
        fuzzer = get_fuzzer(
            crash, target, engine, sanitizer, instrumentation, commit, {}
        )

        if not "functions" in fuzzer:
            print(f"[!] Warning: No functions for crash {local_id} of project {project}", file=sys.stderr)
            continue
        fuzzer["functionIds"] = add_functions_to_database(
            project, local_id, fuzzer["functions"], function_database
        )


def run(
    database,
    output_database,
    filter_file,
    nprocs,
    progress,
    **kwargs,
):
    database = fsdict(database)
    crashes = list(filter_it(database, filter_file))
    shuffle(crashes)

    # Extract functions for each fuzzer
    extract_part = ft.partial(
        extract,
        **kwargs,
    )
    execute(
        extract_part,
        it=crashes,
        nprocs=nprocs,
        chunksize=max(1, min(len(crashes) // nprocs, 64)),
        progress=progress,
        total=len(crashes),
        progress_file=sys.stdout,
    )

    # Create a function database
    function_database = fsdict(output_database)
    create_function_database(crashes, function_database, progress)


@click.command()
@click.option(
    "--database",
    "-d",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    required=True,
    help="Database directory",
)
@click.option(
    "--output-database",
    "-o",
    type=click.Path(file_okay=False),
    required=True,
    help="Output/ function database.",
)
@click.option(
    "--filter-file",
    "-f",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Filter file",
)
@click.option("--nprocs", type=int, default=1, help="Number of parallel processes")
@click.option("--progress", is_flag=True, help="Print progress bar (stdout)")
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    help="Overwrite already generated stuff (traceback, functions)",
)
def cli(*args, **kwargs):
    run(*args, **kwargs)


if __name__ == "__main__":
    cli()
