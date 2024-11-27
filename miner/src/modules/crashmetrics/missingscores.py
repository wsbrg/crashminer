""" Set a default score (-1) to functions without scores.
"""
import click
from tqdm import tqdm

from fsdict import fsdict


def run(database):
    database = fsdict(database)

    # Find all utilized metrics
    used_metrics = set()

    for function in tqdm(database.values(), total=len(database)):
        meta = function["meta"]
        metrics = meta["metrics"]

        for metric in metrics:
            used_metrics.add(metric)

    # Set default scores to missing function scores
    for function in tqdm(database.values(), total=len(database)):
        meta = function["meta"]
        metrics = meta["metrics"]

        for metric in used_metrics:
            if not metric in metrics:
                metrics[metric] = -1

        meta["metrics"] = metrics
        function["meta"] = meta


@click.command()
@click.option(
    "--database",
    "-d",
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help="The function database to work on",
)
def cli(database):
    run(database)


if __name__ == "__main__":
    cli()
