import re
from fsdict import fsdict
from pathlib import Path
from shutil import copy
from utils.utils import *


def calculate_score(fpath, normalize):
    if not fpath.exists():
        return -1.0

    with open(fpath, "rb") as f:
        data = f.read()

    low = len(re.findall(b": Low:", data))
    medium = len(re.findall(b": Medium:", data))
    high = len(re.findall(b": High:", data))
    cum_severity = low * 1.0 + medium * 2.0 + high * 3.0

    if normalize:
        return cum_severity / len(data.split(b"\n"))

    return cum_severity


@with_tempdir
def rats_metric(directory, function_ids, database, normalize, overwrite):
    directory = Path(directory)
    in_dir = directory / "in"
    out_dir = directory / "out"

    in_dir.mkdir()
    out_dir.mkdir()

    for idx, function_id in enumerate(function_ids):
        meta = database[function_id]["meta"]
        if "metrics" in meta and "rats" in meta["metrics"] and not overwrite:
            continue
        fpath = database[function_id].abspath / "source"
        copy(fpath, in_dir / f"{idx}.c")

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{str(in_dir)}:/in",
        "-v",
        f"{str(out_dir)}:/out",
        "rats",
    ]
    res = do_run(cmd)

    for idx, function_id in enumerate(function_ids):
        fpath = out_dir / str(idx)
        function = database[function_id]
        meta = function["meta"]
        if "metrics" in meta and "rats" in meta["metrics"] and not overwrite:
            continue
        if not "metrics" in meta:
            meta["metrics"] = {}

        metric_value = calculate_score(fpath, normalize)
        meta["metrics"]["rats"] = metric_value
        function["meta"] = meta
