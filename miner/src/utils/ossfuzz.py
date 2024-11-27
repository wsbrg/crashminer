import io
import tarfile
import os, os.path as osp
from config import *
from utils.utils import *
from easymp import addlogging


@addlogging
def ossfuzz_clone(directory, git_url, git_commit):
    cmd = [
        "git",
        "clone",
        git_url,
    ]
    res = do_run(cmd, cwd=directory)
    if res["returncode"] != 0:
        logger.warning(f"git clone {git_url} failed.")
        return False, ""
    res = do_run(
        f"git checkout {git_commit}".split(" "),
        cwd=osp.join(directory, "oss-fuzz"),
    )
    if res["returncode"] != 0:
        logger.warning(f"git checkout {git_commit} failed.")
        return False, ""
    return True, res


def remove_fuzzing_image(project_name, commit, working_directory):
    cmd = [
        "docker",
        "image",
        "rm",
        "gcr.io/oss-fuzz/%s_%s" % (project_name, commit),
    ]
    do_run(cmd, cwd=working_directory)


@addlogging
def ossfuzz_fuzz(
    directory,
    engine,
    sanitizer,
    commit,
    timeout,
    aflgo_exploitation,
    directed,
    project_name,
    target,
    out_directory=None,
    fuzzer_out_directory=None,
    dry_run=False,
    apptainer=None,
):
    cmd = []
    if not dry_run:
        cmd += ["unbuffer"]
    cmd += [
        "python3",
        "infra/helper.py",
        "run_fuzzer",
    ]

    if not directed:
        cmd += ["--aflgo_disable_directed"]

    if aflgo_exploitation:
        cmd += [
            "--aflgo_exploitation",
            aflgo_exploitation,
        ]

    if apptainer != None:
        cmd += [
            "--apptainer",
            apptainer,
        ]

    cmd += [
        "--engine",
        engine,
        "--sanitizer",
        sanitizer,
        "--commit",
        commit,
        "--timeout",
        timeout,
        "-e",
        "AFL_NO_UI=1",
        "--out_directory",
        str(out_directory),
        "--fuzzer_out_directory",
        str(fuzzer_out_directory),
        project_name,
        target,
    ]

    if dry_run:
        return " ".join(cmd)

    logger.info(f"Fuzz. Running:\n{' '.join(cmd)}")
    res = do_run(cmd, cwd=directory)
    return res


@addlogging
def ossfuzz_build_fuzzer(
    target,
    fuzzer,
    sanitizer,
    commit,
    cpus,
    project_name,
    working_directory,
    out_directory=None,
    instrumentation=True,
    savetemps=False,
    directed_targets=[],
):
    cmd = [
        "unbuffer",
        "python3",
        "infra/helper.py",
        "build_fuzzers",
        "--architecture",
        "x86_64",
        "--engine",
        fuzzer,
        "--sanitizer",
        sanitizer,
        "--commit",
        commit,
        "--fuzztarget",
        target,
        "--clean",
        "--dwarf",
        "4",
        "--cpus",
        "%f" % cpus,
        "--out_directory",
        str(out_directory),
    ]

    if len(directed_targets) > 0:
        cmd += [
            "--aflgo_mode",
            "targets",
            "--aflgo_targets",
            ",".join(f"{fpath}:{lineno}" for fpath, lineno in directed_targets),
        ]
    if not instrumentation:
        cmd += ["--noinst"]
    if savetemps:
        cmd += ["--savetemps"]
    cmd += [
        project_name,
    ]
    logger.info(f"Building fuzzer. Running:\n{' '.join(cmd)}")
    res = do_run(cmd, cwd=working_directory)
    return res


@addlogging
def ossfuzz_reproduce(
    commit, project_name, target, testcase_path, working_directory, out_directory
):
    cmd = [
        "unbuffer",
        "python3",
        "infra/helper.py",
        "reproduce",
        "--out_directory",
        str(out_directory),
        "--commit",
        commit,
        project_name,
        target,
        str(testcase_path),
    ]
    logger.info(f"Reproduce crash. Running:\n{' '.join(cmd)}")
    res = do_run(cmd, cwd=working_directory)
    return res
