import subprocess
import json
import logging
import sys


def save_json(path, data):
    with open(path, "w") as f:
        f.write(json.dumps(data))


def load_json(path):
    with open(path, "r") as f:
        data = json.loads(f.read())
    return data


def do_run(cmd, cwd=None, timeout=None):
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
    log = {
        "returncode": res.returncode,
        "stdout": res.stdout.decode("utf-8", errors="ignore"),
        "stderr": res.stderr.decode("utf-8", errors="ignore"),
    }
    return log
