""" Analyse crash classes.
"""

import os
import json
import gzip
import re
import functools as ft

UNKNOWN = "unknown"
NOCRASH = "nocrash"

class_patterns = {
    # Address Sanitizer
    "asan_abrt_unknown_address": r"AddressSanitizer: ABRT on unknown address",
    "asan_negative_size_param": r"AddressSanitizer: negative-size-param",
    "asan_heap_buffer_overflow": r"AddressSanitizer: heap-buffer-overflow",
    "asan_stack_overflow": r"AddressSanitizer: stack-overflow",
    "asan_stack_buffer_overflow": r"AddressSanitizer: stack-buffer-overflow",
    "asan_segv": r"AddressSanitizer: SEGV on unknown address",
    "asan_heap_use_after_free": r"AddressSanitizer: heap-use-after-free",
    "asan_use_after_poison": r"AddressSanitizer: use-after-poison",
    "asan_stack_use_after_scope": r"AddressSanitizer: stack-use-after-scope",
    "asan_unknown_crash": r"AddressSanitizer: unknown-crash",
    "asan_fpe_on_unknown_address": r"AddressSanitizer: FPE on unknown address",
    "asan_attempting_free_on_address_which_was_not_malloced": r"AddressSanitizer: attempting free on address which was not malloc\(\)-ed",
    "asan_global_buffer_overflow": r"AddressSanitizer: global-buffer-overflow on address",
    "asan_attempting_double_free": r"AddressSanitizer: attempting double-free",
    "asan_stack_use_after_return": r"AddressSanitizer: stack-use-after-return",
    "asan_container_overflow": r"AddressSanitizer: container-overflow",
    "asan_allocator_is_out_of_memory": r"AddressSanitizer: allocator is out of memory trying to allocate",
    "asan_stack_buffer_underflow": r"AddressSanitizer: stack-buffer-underflow",
    "asan_dynamic_stack_buffer_overflow": r"AddressSanitizer: dynamic-stack-buffer-overflow",
    "asan_cpy_param_overlap": r"AddressSanitizer: .+cpy-param-overlap: memory ranges",
    "asan_ill_on_unknown_address": r"AddressSanitizer: ILL on unknown address",
    # Memory Sanitizer
    "msan_use_of_uninitialized_value": r"MemorySanitizer: use-of-uninitialized-value",
    "msan_segv_on_unknown_address": r"MemorySanitizer: SEGV on unknown address",
    "msan_stack_overflow": r"MemorySanitizer: stack-overflow",
    "msan_fpe_on_unknown_address": r"MemorySanitizer: FPE on unknown address",
    "msan_requested_allocation_size_exceeds_maximum_supported_size": r"MemorySanitizer: requested allocation size .+ exceeds maximum supported size",
    # Undefined Behavior Sanitizer
    "ubsan_runtime error_downcast_of_address": r"runtime error: downcast of address",
    "ubsan_runtime_error_signed_integer_overflow": r"runtime error: signed integer overflow",
    "ubsan_runtime_error_member_call_on_null_pointer": r"runtime error: member call on null pointer",
    "ubsan_runtime_error_member_call_on_address": r"runtime error: member call on address",
    "ubsan_runtime_error_passing_zero": r"runtime error: passing zero",
    "ubsan_runtime_error_left_shift_of_negative_value": r"runtime error: left shift of negative value",
    "ubsan_runtime_error_left_shift_of_by_places_cannot_be_represented": r"runtime error: left shift of .+ by .+ places cannot be represented",
    "ubsan_runtime_error_shift_exponent": r"runtime error: shift exponent",
    "ubsan_runtime_error_division_by_zero": r"runtime error: division by zero",
    "ubsan_runtime_error_negation_of_value_cannot_be_represented": r"runtime error: negation of .+ cannot be represented in type",
    "ubsan_runtime_error_load_of_value_which_is_not_a_valid_value": r"runtime error: load of value .+, which is not a valid value for type",
    "ubsan_runtime_error_load_of_address_address_with_insufficient_space": r"runtime error: load of address .+ with insufficient space for an object of type",
    "ubsan_runtime_error_reference_binding_to_null_pointer": r"runtime error: reference binding to null pointer",
    "ubsan_runtime_error_index_out_of_bounds": r"runtime error: index .+ out of bounds",
    "ubsan_runtime_error_store_to_address_with_insufficient_space": r"runtime error: store to address .+ with insufficient space",
    "ubsan_runtime_error_member_access_within_null_pointer": r"runtime error: member access within null pointer",
    "ubsan_runtime_error_load_of_null_pointer": r"runtime error: load of null pointer of type",
    "ubsan_segv_on_unknown_address": r"UndefinedBehaviorSanitizer: SEGV on unknown address",
    "ubsan_stack_overflow": r"UndefinedBehaviorSanitizer: stack-overflow",
    "ubsan_runtime_error_store_to_null_pointer": r"runtime error: store to null pointer of type",
    "ubsan_runtime_error_applying_non_zero_offset_to_null_pointer": r"runtime error: applying non-zero offset .*to null pointer",
    "ubsan_runtime_error_applying_non_zero_offset_to_non_null_pointer": r"runtime error: applying non-zero offset .*to non-null pointer",
    "ubsan_runtime_error_execution_reached_an_unreachable_program_point": r"runtime error: execution reached an unreachable program point",
    # Leak Sanitizer
    "leaksan_detected_memory_leaks": r"LeakSanitizer: detected memory leaks",
    # LibFuzzer
    "libfuzzer_version_cannot_be_undefined": r"version cannot be undefined",
    "libfuzzer_out_of_memory": r"libFuzzer: out-of-memory",
    "libfuzzer_timeout": r"libFuzzer: timeout",
    "libfuzzer_unable_to_write_nop_sequence": r"LLVM ERROR: unable to write nop sequence",
    "libfuzzer_unable_to_evaluate_offset_to_undefined_symbol": r"LLVM ERROR: unable to evaluate offset to undefined symbol",
    "libfuzzer_malformed_uleb128_extends_past_end": r"LLVM ERROR: malformed uleb128, extends past end",
    "libfuzzer_parsing_fde_data_failed": r"LLVM ERROR: Parsing FDE data at .+ failed due to missing CIE",
    "libfuzzer_fuzz_target_overwrites_its_const_input": r"ERROR: libFuzzer: fuzz target overwrites its const input",
    # Libfuzzer defaults
    "libfuzzer_deadly_signal": r"libFuzzer: deadly signal",
    "libfuzzer_fuzz_target_exited": r"ERROR: libFuzzer: fuzz target exited",
    # Default
    UNKNOWN: r"",
}


def iter_lines(fpath):
    with open(fpath, "r") as f:
        while True:
            line = f.readline()
            if line == "":
                break
            yield line


def iter_write(fpath, it):
    with open(fpath, "w") as f:
        for el in it:
            f.write("%s\n" % el)


def remove_escape_sequences(string):
    sub_pattern = r"(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]"
    return re.sub(sub_pattern, "", string)


def analyse_crash_class(log, print_errors=False):
    log = remove_escape_sequences(log)
    res_key = UNKNOWN
    cls_matches = filter(
        lambda cls: re.search(class_patterns[cls], log), class_patterns
    )
    if print_errors:
        cls_matches = list(cls_matches)
        if len(cls_matches) > 2:
            print("WARNING: Multiple matches: %s" % cls_matches)
            print(
                "NOTICE: 'libfuzzer_deadly_signal' and 'libfuzzer_fuzz_target_exited' are probably, okay."
            )
        return cls_matches[0]
    else:
        return next(cls_matches)


def group_crashes(crash_dict, crash_dict_new):
    for crash_class, logs in crash_dict_new.items():
        if crash_class not in crash_dict:
            crash_dict[crash_class] = []
        crash_dict[crash_class] += crash_dict_new[crash_class]
    return crash_dict


def main(fpath_in, fpath_out):
    lines = iter_lines(fpath_in)
    logs = map(json.loads, lines)
    crashes = map(
        lambda log: {analyse_crash_class(log["stdout"], print_errors=True): [log]}, logs
    )

    # Reduce the crash classes
    crash_dict = ft.reduce(group_crashes, crashes, {})

    # Print crash_dict stats
    total = 0
    for crash_class, logs in crash_dict.items():
        print("%s: %d" % (crash_class, len(logs)))
        total += len(logs)
    print("Total: %d" % total)

    # Dump unknown
    if UNKNOWN in crash_dict:
        unknown_logs = crash_dict[UNKNOWN]
        unknown_logs = map(json.dumps, unknown_logs)
        iter_write(fpath_out, unknown_logs)
    else:
        print("No unknown crashes!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print(
            "Usage: %s <crash logs file> <out file for unknown logs>"
            % (sys.argv[0], sys.argv[1])
        )
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
