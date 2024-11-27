import os
import sys
import random
import io
import re
import subprocess
import posixpath
import multiprocessing as mp
import functools as ft
from pathlib import Path
from dataclasses import dataclass
from typing import List
from elftools.elf.elffile import ELFFile
from fsdict import fsdict
from tqdm import tqdm

from utils.modules import fuzzer_exists, get_fuzzer


@dataclass
class Bundle:
    name: str
    crashes: List[int]


@dataclass
class Function:
    mangled_name: str
    instructions: List[str]
    low_pc: int
    high_pc: int
    name: str = ""
    file_name: str = ""
    line: int = -1


def llvm_demangle(mangled_names):
    input_names = "\n".join(mangled_names)
    input_names = input_names.encode("utf-8")
    res = subprocess.run(["llvm-cxxfilt"], input=input_names, capture_output=True)
    assert res.returncode == 0
    output = res.stdout.decode("utf-8").strip()
    names = [name.strip() for name in output.split("\n")]
    assert len(names) == len(mangled_names)
    return names


def lpe_filename(line_program, file_index):
    # https://github.com/eliben/pyelftools/blob/master/elftools/dwarf/dwarfinfo.py
    # Retrieving the filename associated with a line program entry
    # involves two levels of indirection: we take the file index from
    # the LPE to grab the file_entry from the line program header,
    # then take the directory index from the file_entry to grab the
    # directory name from the line program header. Finally, we
    # join the (base) filename from the file_entry to the directory
    # name to get the absolute filename.
    lp_header = line_program.header
    file_entries = lp_header["file_entry"]

    # File and directory indices are 1-indexed.
    file_entry = file_entries[file_index - 1]
    dir_index = file_entry["dir_index"]

    # A dir_index of 0 indicates that no absolute directory was recorded during
    # compilation; return just the basename.
    if dir_index == 0:
        return file_entry.name.decode()

    directory = lp_header["include_directory"][dir_index - 1]
    return posixpath.join(directory, file_entry.name).decode()


#def process_elffile(filename):
#    function_origins = {}
#
#    with open(filename, "rb") as f:
#        elffile = ELFFile(f)
#
#        if not elffile.has_dwarf_info():
#            return
#
#        dwarf_info = elffile.get_dwarf_info()
#
#        for CU in dwarf_info.iter_CUs():
#            line_program = dwarf_info.line_program_for_CU(CU)
#            if line_program is None:
#                print(
#                    "WARNING: DWARF info is missing a line program for this CU",
#                    file=sys.stderr,
#                )
#                continue
#
#            for die in CU.iter_DIEs():
#                if die.tag != "DW_TAG_subprogram":
#                    continue
#
#                if not "DW_AT_decl_file" in die.attributes:
#                    continue
#
#                if not "DW_AT_name" in die.attributes:
#                    continue
#
#                function_name = die.attributes["DW_AT_name"].value.decode("utf-8")
#
#                index = die.attributes["DW_AT_decl_file"].value
#                source_file = lpe_filename(line_program, index)
#
#                if "initfun" in function_name.lower():
#                    print(function_name)
#                    print(die.attributes.keys())
#                    print(source_file)
#                    print("")
#
#                yield source_file, function_name


def skip_whitespace_lines(f):
    while True:
        start = f.tell()
        line = f.readline()
        if len(line) == 0:
            raise RuntimeError()

        if len(line.strip()) > 0:
            f.seek(start)
            return


def is_function_separator(f):
    start = f.tell()

    next_line = f.readline()
    if len(next_line) == 0:
        raise RuntimeError()

    if next_line == "\n":
        f.seek(start)
        return True

    f.seek(start)
    return False


def is_next_section(f):
    start = f.tell()

    next_line = f.readline()
    if len(next_line) == 0:
        raise RuntimeError()

    if next_line.startswith("Disassembly of section"):
        f.seek(start)
        return True

    f.seek(start)
    return False


def parse_function_header(f):
    line = f.readline().strip()
    match = re.match("^[0-9a-fA-F]+ <(.*)>:$", line)
    assert match is not None

    return match.group(1)


def parse_function_instructions(f):
    while not is_function_separator(f):
        instruction_line = f.readline()
        yield instruction_line

def get_addr_of_instr(instr):
    addr_str = instr.strip().split(":")[0]
    try:
        addr = int(addr_str, base=16)
    except ValueError:
        return None
    return addr

def parse_function(f):
    mangled_name = parse_function_header(f)
    instructions = list(parse_function_instructions(f))
    skip_whitespace_lines(f)

    low_pc = get_addr_of_instr(instructions[0])
    high_pc = get_addr_of_instr(instructions[-1])

    if low_pc == None or high_pc == None:
        return None

    return Function(mangled_name=mangled_name, instructions=instructions, low_pc=low_pc, high_pc=high_pc)


def parse_section(f):
    while not is_next_section(f):
        function = parse_function(f)
        if function != None:
            yield function


def parse_objdump(f):
    while True:
        line = f.readline()
        if len(line) == 0:
            raise RuntimeError()

        if "Disassembly of section .text:" in line:
            break

    skip_whitespace_lines(f)
    yield from parse_section(f)


def process_objdump(filename):
    p = subprocess.run(
        ["objdump", "-D", "-M", "intel", filename], stdout=subprocess.PIPE
    )
    p.check_returncode()

    content = io.StringIO(p.stdout.decode("utf-8"))
    yield from parse_objdump(content)


def function_score(instructions):
    sanitizer_patterns = {"asan": "__asan", "ubsan": "__ubsan", "msan": "__msan"}
    sanitizer_count = {key: 0 for key in sanitizer_patterns}
    for instruction in instructions:
        for sanitizer, pattern in sanitizer_patterns.items():
            if pattern in instruction.lower():
                sanitizer_count[sanitizer] += 1
    return sanitizer_count


def augment_with_demangled_name(functions):
    mangled_names = [function.mangled_name for function in functions]
    names = llvm_demangle(mangled_names)
    for function, name in zip(functions, names):
        function.name = name
    return functions


def augment_with_dwarf_info(filename, functions):
    function_origins = {}

    with open(filename, "rb") as f:
        elffile = ELFFile(f)

        if not elffile.has_dwarf_info():
            return

        dwarf_info = elffile.get_dwarf_info()

        for CU in dwarf_info.iter_CUs():
            line_program = dwarf_info.line_program_for_CU(CU)
            for entry in line_program.get_entries():
                if entry.state:
                    for function in functions:
                        low_pc = function.low_pc
                        high_pc = function.high_pc
                        if low_pc <= entry.state.address <= high_pc:
                            function.file_name = lpe_filename(line_program, entry.state.file)
                            function.line = entry.state.line
                            yield function


def get_extension(file_name):
    if not "." in file_name:
        return ""
    return file_name.split(".")[-1].lower()


def sanitizer_scores_file(elf_path):
    functions = list(process_objdump(elf_path))
    functions = augment_with_demangled_name(functions)
    functions = augment_with_dwarf_info(elf_path, functions)
    dwarf_functions = {}
    for function in functions:
        # Filter invalid functions
        if function.file_name == "" or function.line < 0:
            continue

        low_pc = function.low_pc
        if not low_pc in dwarf_functions:
            dwarf_functions[low_pc] = function
            continue

        # Prefer source files over header files
        old_ext = get_extension(dwarf_functions[low_pc].file_name)
        new_ext = get_extension(function.file_name)
        if "c" in new_ext and not "c" in old_ext:
            dwarf_functions[low_pc] = function

    scores = []
    for function in dwarf_functions.values():
        score = function_score(function.instructions)
        scores.append((function.name, function.file_name, function.line, score))
    return scores


def get_first_mismatch(it1, it2):
    for idx, (el1, el2) in enumerate(zip(it1, it2)):
        if el1 != el2:
            return idx
    return min(len(it1), len(it2))


def sanitizer_scores_crash(crash, functions_by_local_id):
    scores = []
    meta = crash["meta"]
    project_name = meta["project"]
    local_id = int(meta["localId"])

    if not "reproduced" in meta or not meta["reproduced"]:
        return scores

    if not local_id in functions_by_local_id:
        return scores

    target = meta["target"]
    commit = meta["commit"]
    sanitizer = meta["sanitizer"]
    instrumentation = True
    engine = meta["engine"]
    fuzzer_options = (
        target,
        engine,
        sanitizer,
        instrumentation,
        commit,
    )
    if not fuzzer_exists(crash, *fuzzer_options):
        print(f"Cannot find fuzzer for crash '{local_id}' of '{project_name}'.")
        return scores
    fuzzer = get_fuzzer(crash, target, engine, sanitizer, instrumentation, commit)
    fuzzer_path = fuzzer.abspath / "out" / target
    raw_scores = sanitizer_scores_file(str(fuzzer_path))
    if len(raw_scores) == 0:
        return scores

    for function_id, origin in functions_by_local_id[local_id]:
        fpath = origin["fpath"]
        origin_name = origin["name"]
        origin_line = origin["start"]
        MAX_LINE_DISTANCE = 5

        # Find best matching source file
        scored_files = []
        for name, source_file, line, san_scores in raw_scores:
            # We perform the matching via names and line number. If there are
            # names missing, we can't perform the matching.
            if len(name) == 0 or len(origin_name) == 0:
                continue

            # Either function name should contain the other We don't test for
            # equal names as one might be fully qualified with namespaces and
            # the other without. Or template brackets and the others without.
            # Or what else C++ might throw at us.
            if not (name in origin_name or origin_name in name):
                continue

            # Make sure at least the file names match.
            if Path(fpath).name != Path(source_file).name:
                continue

            # Calculate a score measuring how well the full file paths match.
            first_mismatch = get_first_mismatch(fpath[::-1], source_file[::-1])

            scored_files.append((san_scores, first_mismatch))


        if len(scored_files) == 0:
            continue

        sanitizer_scores, _ = max(
            scored_files, key=lambda el: el[1]
        )

        scores.append((function_id, sanitizer_scores))

    return scores


def sanitizer_scores_project(bundle, crash_database, functions_by_local_id):
    project_name = bundle.name
    project = crash_database[project_name]
    scores = []

    if not "crashes" in project:
        return scores

    # Collect reproduced crashes for the project
    for local_id in bundle.crashes:
        crash = project["crashes"][str(local_id)]
        scores += sanitizer_scores_crash(crash, functions_by_local_id)

    return scores


def create_scores_in_parallel(bundles, database, crash_database, functions_by_local_id, nprocs):
    with mp.Pool(nprocs) as p:
        scores_it = p.imap_unordered(
            ft.partial(
                sanitizer_scores_project,
                crash_database=crash_database,
                functions_by_local_id=functions_by_local_id,
            ),
            bundles,
        )
        for score_list in tqdm(scores_it, total=len(bundles)):
            for function_id, sanitizer_scores in score_list:
                meta = database[function_id]["meta"]
                if not "metrics" in meta:
                    meta["metrics"] = {}
                metrics = meta["metrics"]
                
                total_score = 0
                for sanitizer, score in sanitizer_scores.items():
                    key = f"sanitizer-{sanitizer}"
                    if not key in metrics or metrics[key] < score:
                        metrics[key] = score
                    total_score += metrics[key]

                metrics["sanitizer"] = total_score
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


def sanitizer_metric(database, crash_database):
    crash_database = fsdict(crash_database)

    # Load all function meta into RAM
    print("[*] Load functions into ram")
    functions = {
        function_id: function["meta"] for function_id, function in tqdm(database.items(), total=len(database))
    }

    with mp.Manager() as manager:
        # Map code all function locations to local ids
        print("[*] Create crash to function mapping")

        functions_by_local_id = {}

        for function_id, meta in tqdm(functions.items(), total=len(functions)):
            for origin in meta["origins"]:
                local_id = origin["crash"]
                local_id = int(local_id)

                if not local_id in functions_by_local_id:
                    functions_by_local_id[local_id] = []

                functions_by_local_id[local_id].append((function_id, origin))

        functions_by_local_id = manager.dict(functions_by_local_id)


        # Aggregate all scores
        nprocs = int(os.cpu_count() / 2)
        max_bundle_size = 32

        # If we parallelize over the projects the load per process might be vary unfair.
        # Process might get the whole bundle of LLVM crashes, so that every other process
        # in the pool ends up waiting for the LLVM process to finish. As a solution
        # we're creating small bundles of project x n-crashes, which every process has to
        # process.
        bundles = create_bundles(crash_database, functions_by_local_id, max_bundle_size)
        random.shuffle(bundles)

        create_scores_in_parallel(bundles, database, crash_database, functions_by_local_id, nprocs)
