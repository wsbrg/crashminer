import click

from modules.initdb import initdb
from modules.regress import regress
from modules.extraction import extraction
from modules.crashmetrics import crashmetrics
from modules.crashmetrics import missingscores
from modules.evaluate import evaluate
from modules.metricdata import metricdata


@click.group()
def cli():
    pass


if __name__ == "__main__":
    cli.add_command(initdb.cli, "initdb")
    cli.add_command(regress.cli, "regress")
    cli.add_command(extraction.cli, "extraction")
    cli.add_command(crashmetrics.cli, "crashmetrics")
    cli.add_command(missingscores.cli, "missingscores")
    cli.add_command(evaluate.cli, "evaluate")
    cli.add_command(metricdata.cli, "metricdata")
    cli()
