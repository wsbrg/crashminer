""" This module revolves around the creation of plots and tables.
"""

import click
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from sklearn.metrics import ndcg_score
from tqdm import tqdm
from pathlib import Path
from config import TRIVIAL_FUNCTIONS
from fsdict import fsdict
from itertools import groupby

METRICS = [
    "linevul",
    "codet5p",
    "rats",
    "cppcheck",
    "random",
    "reveal",
    "complexity",
    "vulnerability",
    "recent",
    "sanitizer",
    #"sanitizer-asan",
    #"sanitizer-msan",
    #"sanitizer-ubsan",
    "all",
]


def load_functions(functions_path):
    functions = fsdict(functions_path)
    dataset = []

    for _, function in tqdm(functions.items(), total=len(functions), desc="Load functions"):
        meta = function["meta"]
        dataset.append(meta)

    return dataset


def create_queries(functions, metrics, ignore_functions):
    queries = defaultdict(lambda: defaultdict(list))

    for meta in tqdm(functions, desc="Create queries"):
        origins = meta["origins"]
        function_origins = groupby(origins, lambda origin: int(origin["crash"]))

        for crash_id, crash_origins in function_origins:
            crash_origins_init = list(crash_origins)
            crash_origins = crash_origins_init
            crash_origins = filter(
                lambda origin: origin["name"].lower() not in ignore_functions,
                crash_origins,
            )
            framenos = map(
                lambda origin: origin["annotation"]["frameno"], crash_origins
            )
            max_frameno = max(framenos, default=-1)

            is_crash = max_frameno > -1

            for metric in metrics:
                score = meta["metrics"][metric]
                queries[crash_id][metric].append((score, is_crash))

    return queries


def queries_to_numpy(queries, metric):
    X = []
    y = []
    query_groups = []

    for query in queries.values():
        query_metric = query[metric]
        if len(query_metric) == 0:
            continue

        x_query = []
        y_query = []

        for feature_vec, label in query_metric:
            x_query.append(feature_vec)
            y_query.append(label)

        if sum(y_query) == 0:
            continue

        X += x_query
        y += y_query
        query_groups.append(len(query_metric))

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.uint8)
    query_groups = np.array(query_groups, dtype=np.uint32)

    return X, y, query_groups


def calc_ndcg(X, y, query_groups, k):
    scores = np.zeros(len(query_groups))
    scores[:] = np.nan
    cur_idx = 0

    for idx, query_size in enumerate(query_groups):
        x_query = X[cur_idx : cur_idx + query_size]
        y_query = y[cur_idx : cur_idx + query_size]
        cur_idx += query_size

        if y_query.sum() == 0:
            continue

        score = ndcg_score([y_query], [x_query], k=k)
        scores[idx] = score

    return scores


def plot_mean_ndcg(functions_path, output_path, metric, cutoff):
    ignore_functions = set(name.lower() for name in TRIVIAL_FUNCTIONS)
    metrics = [metric] if metric != "all" else [m for m in METRICS if not m == "all"]
    functions = load_functions(functions_path)

    # Create queries
    queries = create_queries(functions, metrics, ignore_functions)

    for metric in tqdm(metrics, desc="Calculate scores for target selection methods"):
        X, y, query_groups = queries_to_numpy(queries, metric)

        # Calc ndcg scores
        scores = [np.nanmean(calc_ndcg(X, y, query_groups, k)) for k in range(1, cutoff+1)]
    
        plt.plot(list(range(1, cutoff+1)), scores, label=metric)
    
    plt.title("Mean-NDCG (underastimating label-strategy)")
    plt.xlabel("#Retrieved functions")
    plt.ylabel("mean-NDCG")
    plt.legend()
    plt.xscale("log")
    plt.savefig(output_path)


@click.command()
@click.option(
    "--functions",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, exists=True, path_type=Path),
    help="Path of the functions directory.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(exists=False),
    required=True,
    help="Output file.",
)
@click.option(
    "--metric",
    default="vulnerability",
    type=click.Choice(METRICS),
    help="Target selection method to calculate the NDCG for.",
)
@click.option(
    "--topn",
    type=int,
    required=True,
    help="Evaluate using the <topn> highest ranking functions for each target selection method.",
)
@click.pass_context
def cli(ctx, functions, output, metric, topn):
    plot_mean_ndcg(functions, output, metric, topn)


if __name__ == "__main__":
    cli()
