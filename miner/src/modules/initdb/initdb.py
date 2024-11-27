import click
from fsdict import fsdict
from tqdm import tqdm

from utils.utils import *


def run(
    projects,
    database,
    filter_file,
    overwrite,
    progress,
):
    projects = json_read(projects)
    if progress:
        it = tqdm(projects.items(), total=len(projects))
    else:
        it = projects.items()
    database = fsdict(database, overwrite=overwrite)
    for project_name, project in it:
        if not "commits" in project:
            print(f"[!] Commits missing for project '{project_name}'")
            continue

        # Create meta
        if not project_name in database:
            database[project_name] = fsdict()
            meta = {
                key: value
                for key, value in project.items()
                if not key in ["commits", "crashes"]
            }
            database[project_name]["meta"] = meta

        # Update commits
        if "commits" in database[project_name]:
            commits = database[project_name]["commits"]
            if len(project["commits"]) > len(commits):
                database[project_name]["commits"] = project["commits"]
        else:
            database[project_name]["commits"] = project["commits"]

        # Update crashes
        database[project_name]["crashes"] = fsdict()
        for crash in project["crashes"]:
            local_id = str(crash["localId"])
            if local_id in database[project_name]["crashes"]:
                continue
            database[project_name]["crashes"][local_id] = fsdict()
            crash_meta = {key: value for key, value in crash.items()}
            crash_meta["localId"] = str(crash_meta["localId"])
            database[project_name]["crashes"][local_id]["meta"] = crash_meta
            database[project_name]["crashes"][local_id]["project"] = database[
                project_name
            ]


@click.command()
@click.option(
    "--projects",
    "-p",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    required=True,
    help="Inputs file (projects)",
)
@click.option(
    "--database",
    "-d",
    type=click.Path(file_okay=False, resolve_path=True),
    required=True,
    help="Database directory",
)
@click.option(
    "--filter-file",
    "-f",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    default=None,
    help="Filter file",
)
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    help="Overwrite projects which are already in the database directory.",
)
@click.option("--progress", is_flag=True, help="Print progress bar (stdout)")
def cli(*args, **kwargs):
    run(*args, **kwargs)


if __name__ == "__main__":
    cli()
