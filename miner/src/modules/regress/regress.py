import click
import sys
import functools as ft
from config import *
from utils.utils import *
from utils.filter import filter_it
from utils.modules import build_fuzzer, reproduce, get_fuzzer
from utils.ossfuzz import *
from toolz.curried import *
from easymp import addlogging, parallel, execute
from fsdict import fsdict


def identify_fuzzer(fuzzer):
    fuzzer = fuzzer.lower()
    if "libfuzzer" in fuzzer:
        fuzzer = "libfuzzer"
    elif "afl" in fuzzer:
        fuzzer = "afl"
    elif "honggfuzz" in fuzzer:
        fuzzer = "honggfuzz"
    elif "dataflow" in fuzzer:
        fuzzer = "dataflow"
    else:
        fuzzer = None
    return fuzzer


def identify_sanitizer(sanitizer):
    sanitizer = sanitizer.lower()
    if "address" in sanitizer or "asan" in sanitizer:
        sanitizer = "address"
    elif "undefined" in sanitizer or "ubsan" in sanitizer:
        sanitizer = "undefined"
    elif "memory" in sanitizer or "msan" in sanitizer:
        sanitizer = "memory"
    elif "coverage" in sanitizer:
        sanitizer = "coverage"
    elif "dataflow" in sanitizer:
        sanitizer = "dataflow"
    elif "thread" in sanitizer:
        sanitizer = "thread"
    else:
        sanitizer = None
    return sanitizer


@curry
def commit_filter(crash_ts, maxdays, commit):
    commit_ts = int(commit["timestamp"])
    delta = crash_ts - commit_ts

    # Commit time must be prior to crash time
    if delta < 0:
        return False

    if maxdays != None:
        # Time between finding the crash and the commit
        # must be less than maxdays.
        max_delta = maxdays * 24 * 60 * 60  # maxdays in seconds
        return delta < max_delta
    else:
        return True


def choose_commits(crash, maxdays, maxcommits):
    # Only use commits within the specified maximum time span to try to
    # reproduce the testacase.
    crash_ts = crash["meta"]["timestamp"]
    project_commits = crash["project"]["commits"]
    commits = list(filter(commit_filter(crash_ts, maxdays), project_commits))

    # If there are no commits within maxdays prior to the crash, use older ones
    if len(commits) == 0:
        commits = list(filter(commit_filter(crash_ts, None), project_commits))

    # Choose >>maxcommits<< commits evenly distributed from the commit list.
    if len(commits) > maxcommits:
        commits = [
            commits[i]
            for i in range(
                0, len(commits), max((len(commits) - 1) // (maxcommits - 1), 1)
            )
        ]

    return commits


@addlogging
def reproduce_commit(
    fuzzer,
    project_name,
    commit,
    target,
    engine,
    sanitizer,
    testcase_path,
    cpus,
):
    # Build fuzzer
    build_success = build_fuzzer(
        fuzzer, project_name, commit, target, engine, sanitizer, cpus, savetemps=True
    )
    if not build_success:
        return False

    # Reproduce
    reproduction_success = reproduce(
        fuzzer, project_name, target, commit, testcase_path
    )
    if not reproduction_success:
        return False

    return True


@parallel
@addlogging
def regress_crash(
    crash,
    testcases,
    maxdays,
    maxcommits,
    engine,
    sanitizer,
    cpus,
    skip_error,
    skip_success,
):
    meta = crash["meta"]
    local_id = meta["localId"]
    project_name = meta["project"]
    project = crash["project"]
    testcase_path = Path(testcases) / local_id

    logger.info(f"Reproduce crash with id {local_id} of project '{project_name}'.")

    if "reproduced" in meta and meta["reproduced"] and skip_success:
        logger.info(
            f"Already reproduced crash with id {local_id} of project '{project_name}'. Skipping."
        )
        return

    if "reproduced" in meta and not meta["reproduced"] and skip_error:
        logger.info(
            f"Already tried to reproduce crash with id {local_id} of project '{project_name}'. Skipping."
        )
        return

    if not testcase_path.is_file():
        logger.warning(
            f"No testcase for crash with id {local_id} of project '{project_name}'."
        )
        return

    # Set sanitizer, engine and target
    sanitizer = identify_sanitizer(meta["sanitizer"]) if not sanitizer else sanitizer
    engine = identify_fuzzer(meta["fuzzer"]) if not engine else engine
    engine = identify_fuzzer(meta["fuzzer"]) if not engine else engine
    engine = identify_fuzzer(meta["fuzzingEngine"]) if not engine else engine
    target = meta["targetBinary"] if meta["targetBinary"] else meta["fuzzTarget"]
    if not sanitizer:
        logger.warning(
            f"Invalid sanitizer '{sanitizer}' for crash {local_id} of project {project_name}."
        )
        return

    if not engine:
        logger.warning(
            f"Invalid engine '{engine}' for crash {local_id} of project {project_name}."
        )
        return
    if not target:
        logger.warning(
            f"Invalid fuzzer '{fuzzer}' for crash {local_id} of project {project_name}."
        )
        return

    # Regress crash
    commits = choose_commits(crash, maxdays, maxcommits)
    for commit in commits:
        instrumentation = "inst"
        commit_hash = commit["hash"]
        fuzzer = get_fuzzer(
            crash,
            target,
            engine,
            sanitizer,
            instrumentation,
            commit_hash,
            {},
            create=True,
        )

        reproduced = reproduce_commit(
            fuzzer,
            project_name,
            commit["hash"],
            target,
            engine,
            sanitizer,
            testcase_path=testcase_path,
            cpus=cpus,
        )
        fuzzer_meta = fuzzer["meta"]

        if reproduced:
            meta["reproduced"] = True
            meta["engine"] = engine
            meta["sanitizer"] = sanitizer
            meta["target"] = target
            meta["commit"] = commit["hash"]
            fuzzer_meta["reproduced"] = True
            fuzzer["meta"] = fuzzer_meta
            break

        fuzzer_meta["reproduced"] = False
        fuzzer["meta"] = fuzzer_meta
        meta["reproduced"] = False

    crash["meta"] = meta


def run(
    database,
    filter_file,
    nprocs,
    progress,
    **kwargs,
):
    database = fsdict(database)
    crashes = list(filter_it(database, filter_file))
    shuffle(crashes)
    regress_crash_part = ft.partial(regress_crash, **kwargs)
    execute(
        regress_crash_part,
        it=crashes,
        nprocs=nprocs,
        chunksize=max(1, min(len(crashes) // nprocs, 64)),
        progress=progress,
        total=len(crashes),
        progress_file=sys.stdout,
    )


@click.command()
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
@click.option("--nprocs", type=int, default=1, help="Number of parallel processes")
@click.option("--progress", is_flag=True, help="Print progress bar (stdout)")
@click.option(
    "--testcases",
    "-t",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    required=True,
    help="Testcases directory",
)
@click.option(
    "--engine",
    "-e",
    type=str,
    default=None,
    help="Fuzzing engine used to regress the crash (defaults to the engine from the crash report)",
)
@click.option(
    "--sanitizer",
    "-s",
    type=str,
    default=None,
    help="Sanitizer used to regress the crash (defaults to the sanitizer from the crash report)",
)
@click.option(
    "--skip-error/--no-skip-error",
    default=True,
    help="Skip already processed crashes (failed ones)",
)
@click.option(
    "--skip-success/--no-skip-success",
    default=True,
    help="Skip already processed crashes (successfull ones)",
)
@click.option(
    "--cpus",
    type=float,
    default=0.0,
    help="Limit number of cpus for each docker container (0. means no limit)",
)
@click.option(
    "--maxdays",
    type=int,
    default=80,
    help="Number of days to consider when reproducing a crash",
)
@click.option(
    "--maxcommits",
    type=int,
    default=3,
    help="Maximum number of commits to test between [crashreportday - maxdays, crashreportday]",
)
def cli(*args, **kwargs):
    run(*args, **kwargs)


if __name__ == "__main__":
    cli()
