import re
import os
import random
import multiprocessing as mp
from tempfile import TemporaryDirectory
from tqdm import tqdm
from dataclasses import dataclass
from typing import List

from utils.utils import *
from fsdict import fsdict
from config import TEMPDIR, C_EXTENSIONS, CPP_EXTENSIONS


@dataclass
class Bundle:
    name: str
    crashes: List[int]


def get_first_mismatch(it1, it2):
    for idx, (el1, el2) in enumerate(zip(it1, it2)):
        if el1 != el2:
            return idx
    return min(len(it1), len(it2))


def get_timestamps(source_file, git_directory):
    cmd = f"git blame -t {source_file}" 
    res = do_run(cmd.split(" "), cwd=str(git_directory))

    if res["returncode"] != 0:
        return []

    def line_to_timestamp(line):
        line = re.sub(" +", " ", line)
        match = re.match(".?[0-9a-f]+[^\(]+\(.+? ([0-9]+) [+-][0-9]+ [0-9]+\)", line)
        if match == None:
            return -1
        timestamp_str = match.group(1)
        try:
            timestamp = int(timestamp_str)
            return timestamp
        except ValueError:
            return -1

    lines = res["stdout"].strip().split("\n")
    timestamps = [line_to_timestamp(line) for line in lines]
    return timestamps


def recent_changes(git_directory, crash, functions_by_local_id):
    meta = crash["meta"]
    local_id = int(meta["localId"])
    project = meta["project"]
    commit = meta["commit"]

    if not local_id in functions_by_local_id:
        print(f"[!] No functions for crash {local_id}!")
        return []

    res = do_run(f"git checkout {commit}".split(" "), cwd=str(git_directory))
    if res["returncode"] != 0:
        print(
            f"[!] Checking out commit '{commit}' of project '{project}' for crash {local_id} failed!"
        )
        return []

    # Find all source files
    source_files = []
    for path in git_directory.rglob("*"):
        str_path = str(path)
        if not path.is_file():
            continue
        if any(str_path.lower().endswith(f".{ext}") for ext in C_EXTENSIONS):
            source_files.append(str_path)
            continue
        if any(str_path.lower().endswith(f".{ext}") for ext in CPP_EXTENSIONS):
            source_files.append(str_path)

    scores = []
    git_blame_cache = {}
    for function_id, origin in functions_by_local_id[local_id]:
        fpath = origin["fpath"]
        start = origin["start"]
        end = origin["end"]

        # Find best matching source file
        scored_files = [
            (source_file, get_first_mismatch(fpath[::-1], source_file[::-1]))
            for source_file in source_files
        ]
        source_file, first_mismatch = max(scored_files, key=lambda el: el[1])

        # Sanity check: at least the filename should match
        if Path(fpath).name != Path(source_file).name:
            continue

        # Find all changes within this range
        # Create the timestamps first if they are not already in the cache
        if not source_file in git_blame_cache:
            timestamps = get_timestamps(source_file, git_directory)
            if len(timestamps) == 0:
                print(f"[!] no timestamps for file '{source_file}'")
            git_blame_cache[source_file] = timestamps

        # Now find the most recent change for the function we are looking at
        timestamps = git_blame_cache[source_file]
        function_timestamps = timestamps[start:end]
        if len(function_timestamps) == 0:
            continue
        most_recent_timestamp = max(function_timestamps)
        scores.append((function_id, most_recent_timestamp))

    return scores


def recent_changes_metric_project(bundle, crash_database, functions_by_local_id):
    scores = []
    project_name = bundle.name
    crashes = bundle.crashes
    project = crash_database[project_name]

    with TemporaryDirectory(dir=TEMPDIR) as directory:
        directory = Path(directory)
        if not "meta" in project:
            return scores
        if not "crashes" in project:
            return scores
        meta = project["meta"]
        repo = meta["main_repo"]

        # Collect reproduced crashes for the project
        reproduced = []
        for local_id in crashes:
            crash = project["crashes"][str(local_id)]
            crash_meta = crash["meta"]
            if "reproduced" in crash_meta and crash_meta["reproduced"]:
                reproduced.append(local_id)

        # No crashes were reproduced for this project
        if len(reproduced) == 0:
            return scores

        # Clone github repository for the project
        res = do_run(f"git clone {repo} {directory}".split(" "))
        if res["returncode"] != 0:
            print(f"[!] Cloning repository for project {project_name} failed.")
            return scores

        for local_id in reproduced:
            crash = project["crashes"][str(local_id)]
            scores += recent_changes(directory, crash, functions_by_local_id)

    return scores


def create_scores_in_parallel(bundles, database, crash_database, functions_by_local_id, nprocs):
    with mp.Pool(nprocs) as p:
        scores_it = p.imap_unordered(
                ft.partial(recent_changes_metric_project, crash_database=crash_database, functions_by_local_id=functions_by_local_id),
                bundles
        )
        for score_list in tqdm(scores_it, total=len(bundles)):
            for function_id, score in score_list:
                meta = database[function_id]["meta"]

                if not "metrics" in meta:
                    meta["metrics"] = {}

                metrics = meta["metrics"]

                if not "recent" in metrics or metrics["recent"] < score:
                    metrics["recent"] = score

                meta["metrics"] = metrics
                database[function_id]["meta"] = meta


def create_bundles(crash_database, functions_by_local_id, max_bundle_size):
    bundles = []
    for project_name, project in crash_database.items():
        bundle = Bundle(name=project_name, crashes=[])
        for local_id, crash in project["crashes"].items():
            local_id = int(local_id)
            if not local_id in functions_by_local_id:
                continue
            if len(functions_by_local_id[local_id]) == 0:
                continue

            if len(bundle.crashes) == max_bundle_size:
                bundles.append(bundle)
                bundle = Bundle(name=project_name, crashes=[])

            bundle.crashes.append(local_id)

        if len(bundle.crashes) > 0:
            bundles.append(bundle)

    return bundles


def recent_changes_metric(database, crash_database):
    crash_database = fsdict(crash_database)

    # Load all function meta into RAM
    print("[*] Create function list")
    functions = {
        function_id: function["meta"] for function_id, function in tqdm(database.items(), total=len(database))
    }

    with mp.Manager() as manager:
        # Map code all function locations to local ids
        print("[*] Create crash to functions mapping")
        functions_by_local_id = {}

        for function_id, meta in tqdm(functions.items(), total=len(functions)):
            for origin in meta["origins"]:
                local_id = int(origin["crash"])

                if not local_id in functions_by_local_id:
                    functions_by_local_id[local_id] = []

                functions_by_local_id[local_id].append((function_id, origin))

        functions_by_local_id = manager.dict(functions_by_local_id)

        # Aggregate all recent-changes scores
        nprocs = int(os.cpu_count() / 2)
        max_bundle_size = 32
        
        # If we parallelize over the projects the load per process might be
        # vary unfair. One process might get the whole bundle of LLVM crashes,
        # so that every other process in the pool ends up waiting for the LLVM
        # process to finish. As a solution we're creating small bundles of
        # (project, n-crashes), which every process has to process.
        bundles = create_bundles(crash_database, functions_by_local_id, max_bundle_size)
        random.shuffle(bundles)
        bundles = sorted(bundles, key=lambda bundle: len(bundle.crashes), reverse=True)

        create_scores_in_parallel(bundles, database, crash_database, functions_by_local_id, nprocs)
