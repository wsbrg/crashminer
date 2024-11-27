import json
import os, os.path as osp
import io
import tarfile
import gzip
import random
import base64 as b64
import subprocess
import functools as ft
from cliffs_delta import cliffs_delta as lib_cliffs_delta
from scipy.stats import mannwhitneyu as lib_mannwhitneyu
#from toolz import curry
#from toolz.curried import compose_left, map, filter, do, groupby, first, concat, reduce
#from itertools import starmap
from hashlib import md5
from tempfile import TemporaryDirectory
from pathlib import Path

from config import TEMPDIR


#starmap = curry(starmap)
#flatten = concat


def with_tempdir(func):
    @ft.wraps(func)
    def inner(*args, **kwargs):
        with TemporaryDirectory(dir=TEMPDIR) as directory:
            return func(Path(directory), *args, **kwargs)

    return inner


#def iter_files(directory):
#    for fpath in (
#        os.path.join(base_dir, file)
#        for base_dir, _, files in os.walk(directory)
#        for file in files
#    ):
#        yield fpath


def b64_encode(bytes):
    return b64.b64encode(bytes).decode("ascii")


def b64_decode(string):
    return b64.b64decode(string)


#def parse_parentheses(string):
#    assert len(string) > 1
#    assert string.startswith("(")
#    level = 0
#    for idx, char in enumerate(string):
#        if char == "(":
#            level += 1
#        elif char == ")":
#            level -= 1
#            if level == 0:
#                return string[1:idx]
#    # Parsing error!
#    return ""


#def tuple_sum(x, y):
#    return [x[i] + y[i] for i in range(min(len(x), len(y)))]


def md5sum(string):
    return md5(string.encode("utf-8")).digest()


#def targets_to_string(targets):
#    return ",".join(f"{file}:{lineno}" for file, lineno in targets)


#def hash_targets(targets):
#    if isinstance(targets, str):
#        return md5sum(targets).hex()
#    else:
#        return md5sum(targets_to_string(targets)).hex()


def do_run(cmd, cwd=None):
    res = subprocess.run(cmd, cwd=cwd, capture_output=True)
    log = {
        "returncode": res.returncode,
        "stdout": res.stdout.decode("utf-8", errors="ignore"),
        "stderr": res.stderr.decode("utf-8", errors="ignore"),
    }
    return log


def fread(fpath):
    with open(fpath, "r", errors="ignore") as f:
        return f.read()


#def fread_bytes(fpath):
#    with open(fpath, "rb") as f:
#        return f.read()
#
#
#def fread_compressed(fpath):
#    with gzip.open(fpath, "rb") as f:
#        return f.read()
#

#def fread_lines(fpath):
#    with open(fpath, "r") as f:
#        while True:
#            line = f.readline()
#            if not line:
#                break
#            yield line
#

#@curry
def fwrite(fpath, data):
    with open(fpath, "w") as f:
        f.write(data)
    return data


#@curry
#def fwrite_bytes(fpath, data):
#    with open(fpath, "wb") as f:
#        f.write(data)
#    return data
#
#
#@curry
#def fwrite_compressed(fpath, data):
#    with gzip.open(fpath, "wb") as f:
#        f.write(data)
#    return data


def json_read(fpath):
    return json.loads(fread(fpath))


#def json_read_compressed(fpath):
#    return compose_left(
#        fread_compressed,
#        json.loads,
#    )(fpath)


#@curry
#def json_write(fpath, data):
#    compose_left(json.dumps, fwrite(fpath))(data)
#    return data


#@curry
#def json_write_compressed(fpath, data):
#    compose_left(
#        json.dumps,
#        lambda serialized: serialized.encode("ascii"),
#        fwrite_compressed(fpath),
#    )(data)
#    return data


#def consume_left(*args, **kwargs):
#    composition = compose_left(*args, **kwargs)
#
#    def consume(it):
#        for el in composition(it):
#            pass
#
#    return consume


def is_definition(function):
    """

    Since joern doesn't distinguish between function declarations and definitions,
    we're using a very simple heuristic. If the function's source code contains an
    opening curly bracket, we assume it's a definition.
    """
    # Note: C++ standard defines <% as a synonym for {.
    return "{" in function or "<%" in function


#def b64_tar_extract(b64_tar, outdir):
#    """Extract a base64 encoded tarfile"""
#    # Write build dir into oss-fuzz dir
#    fobj = io.BytesIO(b64_decode(b64_tar))
#    with tarfile.open(fileobj=fobj) as tar:
#        tar.extractall(outdir)
#
#
#def b64_tar_create(directory):
#    """Create a b64 encoded tarfile containing the given directory"""
#    fobj = io.BytesIO()
#    with tarfile.open(fileobj=fobj, mode="w:gz") as tar:
#        tar.add(directory, arcname=osp.basename(directory))
#    fobj.seek(0)
#    return b64_encode(fobj.read())


def chunks(iterable, *, chunk_size):
    return [
        iterable[chunk : chunk + chunk_size]
        for chunk in range(0, len(iterable), chunk_size)
    ]


def shuffle(iterable):
    return random.shuffle(iterable)


#def time_str2sec(timeout):
#    assert len(timeout) > 1
#    unit = timeout[-1].lower()
#    value = int(timeout[:-1])
#    if unit == "s":
#        return value
#    if unit == "m":
#        return value * 60
#    if unit == "h":
#        return value * 60 ** 2
#    if unit == "d":
#        return value * 60 ** 2 * 24
#    raise ValueError("Invalid unit.")
#
#
#def time_sec2str(seconds):
#    assert seconds > 0
#    seconds = int(seconds)
#    m, s = divmod(seconds, 60)
#    if m == 0:
#        return "%02dm%02ds" % (0, s)
#    h, m = divmod(m, 60)
#    if h == 0:
#        return "%02dm%02ds" % (m, s)
#    d, h = divmod(h, 24)
#    if d == 0:
#        return "%02dh%02dm" % (h, m)
#    return "%02dd%02dh" % (d, h)


def cliffs_delta(l1, l2):
    d,_ = lib_cliffs_delta(l1, l2)
    return d


def vargha_delaney_a(l1, l2):
    d = cliffs_delta(l1, l2)
    vda = (d + 1) / 2
    return vda


def mannwhitneyu(l1, l2):
    stat, pvalue = lib_mannwhitneyu(l1, l2)
    return pvalue


class hashdict(dict):
    def __hash__(self):
        return hash(tuple(sorted(self.items())))


class hashlist(list):
    def __hash__(self):
        return hash(tuple(el for el in self))
