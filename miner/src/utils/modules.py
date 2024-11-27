from fsdict import fsdict
from easymp import addlogging

from utils.ossfuzz import *
from utils.utils import *


#def parse_stats(fpath):
#    # TODO
#    return {}


#def parse_crashes(crashes_dir):
#    fnames = os.listdir(crashes_dir)
#    fnames = filter(lambda fname: "README" not in fname and not fname.endswith(".json"), fnames)
#    crashes = []
#    for fname in fnames:
#        crash_path = osp.join(crashes_dir, fname)
#        id, time = fname.split(",")[:2]
#        id = int(id.split(":")[1])
#        time = int(time)
#        crashes.append(
#            {
#                "id": id,
#                "time": time,
#                "testcase": fname,
#                "result": json_read(osp.join(crashes_dir, f"{fname}.json")),
#            }
#        )
#    return crashes
#
#
#def parse_hangs(hangs_dir):
#    # TODO
#    return []


#def parse_fuzzing_results(out_directory):
#    """Parse refuzzed crashes."""
#    # Find the output directory
#    # fnames = os.listdir(out_directory)
#    # fnames = filter(lambda fname: "aflgo" in fname and "out" in fname, fnames)
#    # fnames = list(fnames)
#    # if len(fnames) != 1:
#    #    return
#
#    # Set the crashes, hangs and stats paths
#    # crashes_dir = osp.join(out_directory, fnames[0], "crashes")
#    # hangs_dir = osp.join(out_directory, fnames[0], "hangs")
#    # stats_path = osp.join(out_directory, fnames[0], "fuzzer_stats")
#    crashes_dir = osp.join(out_directory, "crashes")
#    hangs_dir = osp.join(out_directory, "hangs")
#    stats_path = osp.join(out_directory, "fuzzer_stats")
#
#    # Parse the crashes, hangs and stats
#    crashes = parse_crashes(crashes_dir)
#    hangs = parse_hangs(hangs_dir)
#    fuzzer_stats = parse_stats(stats_path)
#
#    return crashes, hangs, fuzzer_stats


def cm_perfect_tuple():
    return ()


def cm_imperfect_tuple():
    return ()


def cm_random_tuple(seed):
    return (str(seed),)


def cm_rats_tuple(normalize):
    return ("norm" if normalize else "nonorm",)


def cm_cppcheck_tuple(normalize):
    return ("norm" if normalize else "nonorm",)


def cm_codet5p_tuple(normalize):
    return ("norm" if normalize else "nonorm",)


def cm_linevul_tuple(normalize):
    return ("norm" if normalize else "nonorm",)


def cm_reveal_tuple(normalize):
    return ("norm" if normalize else "nonorm",)


def crashmetric_tuple(crashmetric, crashmetric_options):
    if crashmetric == "perfect":
        return cm_perfect_tuple(**crashmetric_options)
    if crashmetric == "imperfect":
        return cm_imperfect_tuple(**crashmetric_options)
    if crashmetric == "random":
        return cm_random_tuple(**crashmetric_options)
    if crashmetric == "rats":
        return cm_rats_tuple(**crashmetric_options)
    if crashmetric == "cppcheck":
        return cm_cppcheck_tuple(**crashmetric_options)
    if crashmetric == "codet5p":
        return cm_codet5p_tuple(**crashmetric_options)
    if crashmetric == "linevul":
        return cm_linevul_tuple(**crashmetric_options)
    if crashmetric == "reveal":
        return cm_reveal_tuple(**crashmetric_options)
    raise ValueError(f"Invalid crashmetric: '{crashmetric}'")


def libfuzzer_tuple():
    return ()


def afl_tuple():
    return ()


def honggfuzz_tuple():
    return ()


def aflgo_tuple(topn, crashmetric, crashmetric_options, **kwargs):
    tup = (topn, crashmetric)
    tup += crashmetric_tuple(crashmetric, crashmetric_options)
    return tup


def engine_tuple(engine, engine_options):
    if engine == "libfuzzer":
        return libfuzzer_tuple(**engine_options)
    if engine == "aflgo":
        return aflgo_tuple(**engine_options)
    if engine == "afl":
        return afl_tuple(**engine_options)
    if engine == "honggfuzz":
        return honggfuzz_tuple(**engine_options)
    raise ValueError(f"Invalid engine: '{engine}'")


def fuzzer_tuple(target, engine, sanitizer, instrumentation, commit, engine_options):
    instrumentation = "inst" if instrumentation else "noinst"
    tup = (target, engine, sanitizer, instrumentation, commit)
    if engine_options != None and engine_options != {}:
        tup += engine_tuple(engine, engine_options)
    return tup


def get_fuzzer(
    fsd,
    target,
    engine,
    sanitizer,
    instrumentation,
    commit,
    engine_options=None,
    create=False,
):
    create_fsdict_on_keyerror_saved = fsd.create_fsdict_on_keyerror
    fsd.create_fsdict_on_keyerror = create

    tup = ("fuzzers",)
    tup += fuzzer_tuple(
        target, engine, sanitizer, instrumentation, commit, engine_options
    )
    for el in tup:
        fsd = fsd[str(el)]

    fsd.create_fsdict_on_keyerror = create_fsdict_on_keyerror_saved

    return fsd


def fuzzer_exists(
    fsd, target, engine, sanitizer, instrumentation, commit, engine_options=None
):
    try:
        get_fuzzer(
            fsd, target, engine, sanitizer, instrumentation, commit, engine_options
        )
    except KeyError:
        return False
    return True


def fuzzer_get_runs(fsd, fuzzing_options, create=False):
    create_fsdict_on_keyerror_saved = fsd.create_fsdict_on_keyerror
    fsd.create_fsdict_on_keyerror = create
    tup = ("fuzzing",)
    tup += fuzzing_options
    for el in tup:
        fsd = fsd[el]
    fsd.create_fsdict_on_keyerror = create_fsdict_on_keyerror_saved
    return fsd


def crash_get_runs(fsd, fuzzer_options, fuzzing_options, create=False):
    fuzzer = get_fuzzer(*fuzzer_options)
    return fuzzer_get_runs(fuzzer, fuzzing_options, create)


#def perfect_targets(crash, topn):
#    """Use the traceback's functions as targets."""
#    meta = crash["meta"]
#    fuzzer = get_fuzzer(
#        crash,
#        meta["target"],
#        meta["engine"],
#        meta["sanitizer"],
#        "inst",
#        meta["commit"],
#        {},
#    )
#    traceback = fuzzer["meta"]["traceback"]
#    traceback = (frame for frame in traceback if "function" in frame)
#    traceback = (frame for frame in traceback if "fpath" in frame["function"])
#    traceback = (frame for frame in traceback if "linenum" in frame["function"])
#    targets = [
#        (frame["function"]["fpath"], frame["function"]["linenum"])
#        for frame in traceback
#    ]
#    return targets[:topn]
#
#
#def imperfect_targets(crash, function_database, topn):
#    """Use the traceback's functions as targets, but exclude the offset within
#    the function.
#    """
#    meta = crash["meta"]
#    project_name = meta["project"]
#    local_id = meta["localId"]
#    fuzzer = get_fuzzer(
#        crash,
#        meta["target"],
#        meta["engine"],
#        meta["sanitizer"],
#        "inst",
#        meta["commit"],
#        {},
#    )
#    function_ids = sorted(list(fuzzer["functionIds"]))
#    functions = (function_database[id]["meta"] for id in function_ids)
#    targets = []
#    for function in functions:
#        origins = filter(
#            lambda origin: origin["project"] == project_name
#            and origin["crash"] == local_id,
#            function["origins"],
#        )
#        for origin in origins:
#            for frameno in origin["annotation"]["framenos"]:
#                targets.append((frameno, origin, function["target"]))
#    targets = sorted(targets, key=lambda el: el[0])
#    return [
#        (origin["fpath"], origin["start"] + target_offset)
#        for _, origin, target_offset in targets[:topn]
#    ]
#
#
#def select_targets(crash, function_database, crashmetric, topn):
#    function_database = fsdict(function_database)
#    meta = crash["meta"]
#    project_name = meta["project"]
#    local_id = meta["localId"]
#    if crashmetric == "perfect":
#        targets = perfect_targets(crash, topn)
#    elif crashmetric == "imperfect":
#        targets = imperfect_targets(crash, function_database, topn)
#    else:
#        fuzzer = get_fuzzer(
#            crash,
#            meta["target"],
#            meta["engine"],
#            meta["sanitizer"],
#            "inst",
#            meta["commit"],
#            {},
#        )
#        function_ids = sorted(list(fuzzer["functionIds"]))
#        functions = (function_database[id]["meta"] for id in function_ids)
#        functions = sorted(
#            functions,
#            key=lambda function: function["metrics"][crashmetric],
#            reverse=True,
#        )
#        targets = []
#        for function in functions:
#            origins = filter(
#                lambda origin: origin["project"] == project_name
#                and origin["crash"] == local_id,
#                function["origins"],
#            )
#            for origin in origins:
#                # Function origin as target
#                #targets.append((origin["fpath"], origin["start"]))
#                
#                # Function origin + offset as target (this might work better
#                # for aflgo, than using the function's first line)
#                targets.append((origin["fpath"], origin["start"] + function["target"]))
#
#    used = set()
#    for target in targets:
#        if len(used) == topn:
#            break
#        if target not in used:
#            used.add(target)
#            yield target


@with_tempdir
@addlogging
def build_fuzzer(
    directory,
    fuzzer,
    project_name,
    commit,
    target,
    engine,
    sanitizer,
    cpus,
    instrumentation=True,
    savetemps=False,
    directed_targets=[],
):
    if not "log" in fuzzer:
        fuzzer["log"] = fsdict()
    if not "out" in fuzzer:
        fuzzer["out"] = fsdict()
    meta = fuzzer["meta"] if "meta" in fuzzer else {}

    # Clone OSS-Fuzz Github repository
    clone_success, log = ossfuzz_clone(directory, OSSFUZZ_GIT_URL, OSSFUZZ_GIT_COMMIT)
    if not clone_success:
        meta["buildSuccess"] = False
        fuzzer["meta"] = meta
        return False
    fuzzer["log"]["ossClone"] = log
    ossfuzz_path = directory / "oss-fuzz"

    # Build fuzzer
    logger.info(
        f"Build target '{target}' with engine '{engine}' and sanitizer '{sanitizer}' for project {project_name} @ {commit}."
    )
    build_fuzzer_options = {
        "target": target,
        "fuzzer": engine,
        "sanitizer": sanitizer,
        "commit": commit,
        "cpus": cpus,
        "project_name": project_name,
        "working_directory": ossfuzz_path,
        "out_directory": fuzzer["out"].abspath,
        "instrumentation": instrumentation,
        "savetemps": savetemps,
        "directed_targets": directed_targets,
    }
    res = ossfuzz_build_fuzzer(**build_fuzzer_options)
    logger.info(
        f"Building fuzzer for crash project {project_name} @ {commit} finished."
    )
    fuzzer["log"]["buildFuzzer"] = res
    remove_fuzzing_image(project_name, commit, ossfuzz_path)

    # Check if fuzzer was built successfully
    if res["returncode"] != 0:
        meta["buildSuccess"] = False
        fuzzer["meta"] = meta
        logger.warning(f"Building fuzzer for project {project_name} @ {commit} failed.")
        return False

    logger.info(
        f"Building fuzzer for project {project_name} @ {commit} finished successfully."
    )
    meta["buildSuccess"] = True
    fuzzer["meta"] = meta
    return True


@with_tempdir
@addlogging
def reproduce(directory, fuzzer, project_name, target, commit, testcase_path):
    # Create directories
    if not "log" in fuzzer:
        fuzzer["log"] = fsdict()
    if not "out" in fuzzer:
        fuzzer["out"] = fsdict()

    # Clone OSS-Fuzz Github repository
    clone_success, output = ossfuzz_clone(
        directory, OSSFUZZ_GIT_URL, OSSFUZZ_GIT_COMMIT
    )
    fuzzer["log"]["ossClone"] = output
    if not clone_success:
        return False
    ossfuzz_path = directory / "oss-fuzz"

    # Run fuzzer with single testcase to reproduce the crash
    logger.info(
        f"Running fuzzer '{target}' of project {project_name} @ {commit} with single testcase '{str(testcase_path)}'."
    )
    reproduce_options = {
        "commit": commit,
        "project_name": project_name,
        "target": target,
        "testcase_path": testcase_path,
        "working_directory": ossfuzz_path,
        "out_directory": fuzzer["out"].abspath,
    }
    res = ossfuzz_reproduce(**reproduce_options)
    fuzzer["log"]["reproduction"] = res
    reproduced = "SUMMARY" in res["stdout"]
    if reproduced:
        logger.info(f"Reproduction finished successfully.")
    else:
        logger.warning(f"Reproduction finished but could not reproduce the crash.")

    return reproduced


@with_tempdir
@addlogging
def fuzz(
    directory,
    crash,
    log,
    commit,
    target,
    engine,
    sanitizer,
    testcase_path,
    instrumentation=True,
    directed_targets=[],
):
    project = fsdict(project._basepath, project._path, create_fsdict_on_keyerror=True)
    project_name = project["meta"]["project"]
    result = get_fuzzer(
        project, target, engine, sanitizer, instrumentation, directed_targets, commit
    )

    # Clone OSS-Fuzz Github repository
    clone_success, output = ossfuzz_clone(
        directory, OSSFUZZ_GIT_URL, OSSFUZZ_GIT_COMMIT
    )
    log["ossClone"] = output
    if not clone_success:
        return False
    ossfuzz_path = directory / "oss-fuzz"

    # Run fuzzer
    logger.info(f"Running fuzzer '{target}' of project {project_name} @ {commit}.")
    fuzz_options = {
        "directory": directory,
        "engine": engine,
        "sanitizer": sanitizer,
        "commit": commit,
        "timeout": timeout,
        "aflgo_exploitation": exploitation,
        "project_name": project_name,
        "target": target,
        "out_directory": result["out"].abspath,
    }
    res = ossfuzz_fuzz(**reproduce_options)
    logger.info(f"Fuzzing finished.")
    log["fuzzing"] = res

    return res.returncode == 0
