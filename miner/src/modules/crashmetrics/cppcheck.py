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

    error = len(re.findall(b'severity="error"', data))
    warning = len(re.findall(b'severity="warning"', data))
    style = len(re.findall(b'severity="style"', data))
    portability = len(re.findall(b'severity="portability"', data))
    information = len(re.findall(b'severity="information"', data))
    cum_severity = (
        information * 1.0
        + portability * 2.0
        + style * 3.0
        + warning * 4.0
        + error * 5.0
    )

    if normalize:
        return cum_severity / len(data.split(b"\n"))

    return cum_severity


@with_tempdir
def cppcheck_metric(directory, function_ids, database, normalize):
    directory = Path(directory)
    in_dir = directory / "in"
    out_dir = directory / "out"

    in_dir.mkdir()
    out_dir.mkdir()

    for idx, function_id in enumerate(function_ids):
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
        "cppcheck",
    ]
    res = do_run(cmd)

    for idx, function_id in enumerate(function_ids):
        fpath = out_dir / str(idx)
        function = database[function_id]
        meta = function["meta"]
        if not "metrics" in meta:
            meta["metrics"] = {}

        metric_value = calculate_score(fpath, normalize)
        meta["metrics"]["cppcheck"] = metric_value
        function["meta"] = meta
