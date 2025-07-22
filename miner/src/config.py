from pathlib import Path

CWD = str(Path.cwd())

# MNayer oss fuzz fork
# Use remote clone
#OSSFUZZ_GIT_URL = "https://github.com/MNayer/oss-fuzz.git"
# Use local clone (recommended, faster)
# Change the URL to point to your oss-fuzz directory
OSSFUZZ_GIT_URL = f"file://{CWD}/oss-fuzz"
OSSFUZZ_GIT_COMMIT = "HEAD"

# Place to clone the oss-fuzz repository to
TEMPDIR = "/tmp/"

# Only consider functions which come from this directory or its
# subdirectories for further processing, so that system files
# libraries, etc. are excluded.
BUILD_PREFIX = "/src/"

# File extension
C_EXTENSIONS = ["c", "h"]
CPP_EXTENSIONS = ["cpp", "cc", "cxx", "hpp", "hxx"]

# Clusterfuzz build prefixes. Function which come from this directories
# are ignored in the processing steps. Since "/src/llvm-project" is too
# restrictive when the fuzz target project is llvm itself, we use the less
# restrictive "/src/llvm-project/compiler-rt/lib/fuzzer/" filter, but
# only if the project is LLVM.
IGNORE_BUILD_PREFIXES = [
    "/src/llvm-project/compiler-rt/lib/fuzzer/",
    "/src/aflplusplus",
    "/src/honggfuzz",
    "/src/libfuzzer",
]
IGNORE_BUILD_PREFIXES_RESTRICTIVE = IGNORE_BUILD_PREFIXES + ["/src/llvm-project"]

# We might want to exclude source code from system directories
SOURCE_FUNCTION_EXCLUDE_DIRS = [
    "/usr/include",
    "/usr/lib",
    "/usr/bin",
    "/usr/local/include",
    "/usr/local/lib",
    "/usr/local/bin",
]

# Docker container names for CPG creation
SOURCE_CPG_DOCKER = "source-cpg"

# Dictionary of CPG node labels. The dictionary is constructed by:
# Splitting CPG dot labels to the tuple
# (<IDENTIFIER>,<first word of additional info>)
#CPG_DICT = "./cpgdict.txt"

# Treesitter parser library
PARSER_LIB = f"{CWD}/src/utils/parsers/build/languages.so"

# We cannot use treesitter out-of-the-box since huge file cause problems so
# that not all functions from a file are being extracted. As a solution we
# perform a leightweight pre-parsing breaking the file in smaller parts which
# we then subject to analysis by treesitter. The following controls the depth
# of the pre-parsing.
PREPARSE_DEPTH = 3

# Fuzzers
DIRECTED_FUZZERS = ["aflgo"]

# List of implemented crashmetrics
CRASHMETRICS = ["perfect", "imperfect", "traceback", "random", "rats", "cppcheck", "codet5p", "linevul"]

# Trivial functions
# When matching the predictions of the target localization methods with actual
# crash tracebacks, we're ignoring trivial functions, as they are part of many,
# tracebacks and are likely not causal for the crash
TRIVIAL_FUNCTIONS = ["LLVMFuzzerTestOneInput", "main", "intentional_segfault", "fuzz"]
