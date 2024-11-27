""" This module revoles around creation of a CSV detailing information such as
sanitizer, engine, recall@k for varios localization methods, etc. for each
reproduced crash.
"""

import click
import sys
import re
import pandas as pd
import numpy as np
import functools as ft
from sklearn.metrics import recall_score, precision_score
from tqdm import tqdm
from bisect import insort
from fsdict import fsdict
from utils.utils import *
from utils.filter import filter_it
from utils.modules import *
from config import TRIVIAL_FUNCTIONS


@addlogging
def get_functions_ids(crash):
    if not "meta" in crash:
        return
    meta = crash["meta"]
    local_id = meta["localId"]
    project_name = meta["project"]

    if not ("reproduced" in meta and meta["reproduced"]):
        logger.warning(
            f"Could not extract metrics data for '{local_id}' of '{project_name}'. Was not reproduced successfully before."
        )
        return

    target = meta["target"]
    commit = meta["commit"]
    engine = meta["engine"]
    sanitizer = meta["sanitizer"]
    instrumentation = True
    fuzzer_options = (
        target,
        engine,
        sanitizer,
        instrumentation,
        commit,
    )
    if not fuzzer_exists(crash, *fuzzer_options):
        logger.warning(
            f"Could not extract metrics data for '{local_id}' of '{project_name}'. Fuzzer does not exist."
        )
        return
    fuzzer = get_fuzzer(crash, *fuzzer_options)

    if not "functionIds" in fuzzer:
        logger.warning(
            f"Could not extract metrics data for '{local_id}' of '{project_name}'. No function IDs."
        )
        return
    function_ids = fuzzer["functionIds"]

    return function_ids


def get_functions_seperated_and_sorted(functions, function_ids):
    metric_sep_functions = {}
    for function_id in function_ids:
        if not function_id in functions:
            continue
        function = functions[function_id]["meta"]
        metrics = function["metrics"]

        for metric, score in metrics.items():
            score = float(score)
            if not metric in metric_sep_functions:
                metric_sep_functions[metric] = [(score, function_id, function)]
                continue
            insort(
                metric_sep_functions[metric],
                (score, function_id, function),
                key=lambda el: el[0],
            )

    # Reverse the lists
    for metric in metric_sep_functions:
        metric_sep_functions[metric] = metric_sep_functions[metric][::-1]

    return metric_sep_functions


def evaluate_metric(sorted_functions, local_id, max_cutoff):
    trivial_functions = [function.lower() for function in TRIVIAL_FUNCTIONS]
    names = [""] * max_cutoff
    hits = [False] * max_cutoff
    frame_nos = [-1] * max_cutoff
    function_ids = [""] * max_cutoff

    # Initialize the ground truth array
    for i, (_, _, function) in enumerate(sorted_functions[:max_cutoff]):
        for origin in function["origins"]:
            if origin["crash"] == local_id:
                names[i] = origin["name"]
                function_ids[i] = str(hash(origin))
                if (
                    origin["annotation"]["frameno"] > -1
                    and origin["name"].lower() not in trivial_functions
                ):
                    hits[i] = True
                    frame_nos[i] = origin["annotation"]["frameno"]

    return hits, frame_nos, names, function_ids


@addlogging
def run(
    database, functions, output, maxcutoff, filter_file, nprocs, progress, **kwargs
):
    database = fsdict(database)
    functions = fsdict(functions)
    crashes = list(filter_it(database, filter_file))

    columns = (
        "project_name",
        "local_id",
        "timestamp",
        "sanitizer",
        "engine",
        "crash_class",
        "metric",
        "topn",
        "hit",
        "frame_no",
        "name",
        "traceback_length",
        "num_functions",
    )
    rows = []

    for crash in tqdm(crashes):
        meta = crash["meta"]
        local_id = meta["localId"]
        project_name = meta["project"]
        timestamp = meta["timestamp"]

        function_ids = get_functions_ids(crash)
        if function_ids == None or len(function_ids) == 0:
            logger.warning(
                f"Cancel extractinfg metric data for '{local_id}' of '{project_name}'. No functions."
            )
            continue
        metric_sep_functions = get_functions_seperated_and_sorted(
            functions, function_ids
        )
        if len(metric_sep_functions) == 0:
            logger.warning(
                f"Cancel extracting metric data for '{local_id}' of '{project_name}'. No functions, after grouping by metric."
            )
            continue

        min_functions_for_metric = min(
            len(funs) for funs in metric_sep_functions.values()
        )
        max_functions_for_metric = max(
            len(funs) for funs in metric_sep_functions.values()
        )
        if min_functions_for_metric * 2 < max_functions_for_metric:
            logger.warning(
                f"Cancel extracting metric data for '{local_id}' of '{project_name}'. Huge difference in number of functions per metric. This should not have happened."
            )
            continue

        target = meta["target"]
        engine = meta["engine"]
        sanitizer = meta["sanitizer"]
        commit = meta["commit"]
        fuzzer = get_fuzzer(crash, target, engine, sanitizer, "inst", commit)
        fuzzer_meta = fuzzer["meta"]
        crash_class = "noclass" if not "class" in fuzzer_meta else fuzzer_meta["class"]
        traceback_length = len(fuzzer_meta["traceback"])

        for metric, sorted_functions in metric_sep_functions.items():
            num_functions = len(sorted_functions)
            hits, frame_nos, names, function_ids = evaluate_metric(
                sorted_functions, local_id, maxcutoff
            )
            for topn, (hit, frame_no, name, function_id) in enumerate(
                zip(hits, frame_nos, names, function_ids), start=1
            ):
                row = (
                    project_name,
                    local_id,
                    timestamp,
                    sanitizer,
                    engine,
                    crash_class,
                    metric,
                    topn,
                    hit,
                    frame_no,
                    name,
                    traceback_length,
                    num_functions,
                )
                rows.append(row)

    df = pd.DataFrame(rows, columns=columns)
    df.sort_values(by=["project_name", "local_id", "metric"], inplace=True)
    df.to_csv(output, index=False)


@click.command()
@click.option(
    "--database",
    "-d",
    type=click.Path(file_okay=False),
    required=True,
    help="Database directory",
)
@click.option(
    "--functions",
    type=click.Path(file_okay=False),
    required=True,
    help="Database directory",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(exists=False),
    required=True,
    help="Output file",
)
@click.option(
    "--maxcutoff", type=int, default=10, help="Cutoff for highest scoring functions."
)
@click.option("--nprocs", type=int, default=1, help="Number of parallel processes")
@click.option("--progress", is_flag=True, help="Print progress bar (stdout)")
@click.option(
    "--filter-file",
    "-f",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Filter file (csv)",
)
def cli(*args, **kwargs):
    run(*args, **kwargs)


# @cli.command()
# @click.option(
#    "--seed", "-s", type=int, default=1337, help="Seed to use for the random metric."
# )
# @click.pass_context
# def random(ctx, *args, **kwargs):
#    assert len(args) == 0
#    run(
#        *ctx.obj["entry"]["args"],
#        **ctx.obj["entry"]["kwargs"],
#        metric="random",
#        metric_options={},
#    )
#
#
# @cli.command()
# @click.pass_context
# def perfect(ctx, *args, **kwargs):
#    assert len(args) == 0
#    run(
#        *ctx.obj["entry"]["args"],
#        **ctx.obj["entry"]["kwargs"],
#        metric="perfect",
#        metric_options={},
#    )
#
#
# @cli.command()
# @click.pass_context
# def imperfect(ctx, *args, **kwargs):
#    assert len(args) == 0
#    run(
#        *ctx.obj["entry"]["args"],
#        **ctx.obj["entry"]["kwargs"],
#        metric="imperfect",
#        metric_options={},
#    )
#
#
# @cli.command()
# @click.option(
#    "--normalize/--no-normalize",
#    default=True,
#    help="Normalize the severity for the number of lines of each function",
# )
# @click.pass_context
# def rats(ctx, *args, **kwargs):
#    assert len(args) == 0
#    run(
#        *ctx.obj["entry"]["args"],
#        **ctx.obj["entry"]["kwargs"],
#        metric="rats",
#        metric_options={"normalize": kwargs["normalize"]},
#    )
#
#
# @cli.command()
# @click.option(
#    "--normalize/--no-normalize",
#    default=True,
#    help="Normalize the severity for the number of lines of each function",
# )
# @click.pass_context
# def cppcheck(ctx, *args, **kwargs):
#    assert len(args) == 0
#    run(
#        *ctx.obj["entry"]["args"],
#        **ctx.obj["entry"]["kwargs"],
#        metric="cppcheck",
#        metric_options={"normalize": kwargs["normalize"]},
#    )


if __name__ == "__main__":
    cli()
