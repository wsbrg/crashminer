""" Calculate metrics for each function of a job.

Crash metrics are assigned to each function of a job and aim at describing the
function's likelihood to be part of the reason the program crashes.
"""
import sys
import click
import functools as ft
from fsdict import fsdict
from easymp import addlogging, parallel, execute

from utils.utils import *
from modules.crashmetrics.leopard import complexity_metric, vulnerability_metric
from modules.crashmetrics.codet5p import codet5p_metric
from modules.crashmetrics.rats import rats_metric
from modules.crashmetrics.cppcheck import cppcheck_metric
from modules.crashmetrics.random import random_metric
from modules.crashmetrics.recent import recent_changes_metric
from modules.crashmetrics.sanitizer import sanitizer_metric


def run(database, nprocs, progress, function, easymp=True):
    database = fsdict(database)
    functions = list(database)
    shuffle(functions)
    function_chunks = chunks(functions, chunk_size=1024)

    if easymp:
        execute(
            ft.partial(function, database=database),
            it=function_chunks,
            nprocs=nprocs,
            chunksize=max(1, min(len(function_chunks) // nprocs, 128)),
            progress=progress,
            total=len(function_chunks),
            progress_file=sys.stdout,
        )
    else:
        function(database)


@click.group()
@click.option(
    "--database",
    "-d",
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help="The function database to work on",
)
@click.option("--nprocs", type=int, default=1, help="Number of parallel processes")
@click.option("--progress", is_flag=True, help="Print progress bar (stdout)")
@click.pass_context
def cli(ctx, *args, **kwargs):
    ctx.ensure_object(dict)
    ctx.obj["metrics"] = {
        "args": args,
        "kwargs": kwargs,
    }


@cli.command()
@click.pass_context
def codet5p(ctx, *args, **kwargs):
    run(
        *ctx.obj["metrics"]["args"],
        **ctx.obj["metrics"]["kwargs"],
        function=ft.partial(codet5p_metric, **kwargs),
        easymp=False,
    )


@cli.command()
@click.pass_context
def complexity(ctx, *args, **kwargs):
    run(
        *ctx.obj["metrics"]["args"],
        **ctx.obj["metrics"]["kwargs"],
        function=ft.partial(complexity_metric, **kwargs)
    )


@cli.command()
@click.pass_context
def vulnerability(ctx, *args, **kwargs):
    run(
        *ctx.obj["metrics"]["args"],
        **ctx.obj["metrics"]["kwargs"],
        function=ft.partial(vulnerability_metric, **kwargs)
    )


@cli.command()
@click.option(
    "--normalize/--no-normalize",
    default=True,
    help="Normalize the severity for the number of lines of each function",
)
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    help="Overwrite scores which have already been calculated",
)
@click.pass_context
def rats(ctx, *args, **kwargs):
    run(
        *ctx.obj["metrics"]["args"],
        **ctx.obj["metrics"]["kwargs"],
        function=ft.partial(rats_metric, **kwargs)
    )


@cli.command()
@click.option(
    "--normalize/--no-normalize",
    default=True,
    help="Normalize the severity for the number of lines of each function",
)
@click.pass_context
def cppcheck(ctx, *args, **kwargs):
    run(
        *ctx.obj["metrics"]["args"],
        **ctx.obj["metrics"]["kwargs"],
        function=ft.partial(cppcheck_metric, **kwargs)
    )


@cli.command()
@click.option(
    "--crash-database",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="The crash database.",
)
@click.pass_context
def recent_changes(ctx, *args, **kwargs):
    run(
        *ctx.obj["metrics"]["args"],
        **ctx.obj["metrics"]["kwargs"],
        function=ft.partial(recent_changes_metric, **kwargs),
        easymp=False
    )


@cli.command()
@click.option(
    "--crash-database",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="The crash database.",
)
@click.pass_context
def sanitizers(ctx, *args, **kwargs):
    run(
        *ctx.obj["metrics"]["args"],
        **ctx.obj["metrics"]["kwargs"],
        function=ft.partial(sanitizer_metric, **kwargs),
        easymp=False
    )


@cli.command()
@click.option(
    "--seed", "-s", type=int, default=1337, help="Seed to use for the random metric."
)
@click.pass_context
def random(ctx, *args, **kwargs):
    run(
        *ctx.obj["metrics"]["args"],
        **ctx.obj["metrics"]["kwargs"],
        function=ft.partial(random_metric, **kwargs)
    )


if __name__ == "__main__":
    cli()
