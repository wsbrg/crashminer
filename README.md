![CrashMiner](crashminer.png)

# SoK: Where to Fuzz? Assessing Target Selection Methods in Directed Fuzzing

This code belongs to the publication

> Felix Weissberg, Jonas Möller, Tom Ganz, Erik Imgrund, Lukas Pirch, Lukas
> Seidel, Moritz Schloegel, Thorsten Eisenhofer, and Konrad Rieck. 2024. SoK:
> Where to Fuzz? Assessing Target Selection Methods in Directed Fuzzing. In
> Proceedings of the 19th ACM Asia Conference on Computer and Communications
> Security (ASIA CCS '24). Association for Computing Machinery, New York, NY,
> USA, 1539–1553. https://doi.org/10.1145/3634737.3661141

## Overview

This repository contains the code to compare various target selection methods for directed fuzzing. For this comparison, we use crashes identified through the [OSS-Fuzz](https://google.github.io/oss-fuzz/) project. These crashes are reproduced to extract tracebacks, enabling us to identify the involved functions and build a function-level dataset. This dataset serves as the basis for comparing different target selection approaches, including static analysis tools (SAST), heuristic-based methods, and machine learning techniques.

The repository is divided into two components:

1. `scraper`: A tool that retrieves information from the OSS-Fuzz bug tracker.
2. `miner`: A tool that reproduces crashes, constructs the dataset, and evaluates various target selection methods.

If you do not wish to collect additional data, you can skip the scraper entirely and use the miner with our provided dataset. In this case, ensure that all required dependencies are installed before proceeding with the miner's build and run instructions.

## Dependencies
- expect
- python3
- python3-pip
- python3-venv
- docker
- git

## Quick start
After installing all dependencies, you have three options depending on how much of the pipeline you want to run:
1. Run the entire pipeline, from scraping the OSS-Fuzz website to comparing various target selection methods.
2. Skip the scraping step and start with reproducing the crashes, creating the database, and calculating scores for each function.
3. Start from our function database, recalculate the scores for each function and run the evaluation.

### 1. Run the whole pipeline
From within the `scraper/` directory, run:
```
./build.sh
./run.sh
```

Once finished, copy the output file `data/projects.json` file to `miner/data/` and `data/testcases` to `miner/data/testcases`. Then, from within the `miner/` directory run:
```
./build.sh
./scripts/build_targets.sh
./scripts/scores.sh
./scripts/eval.sh
```

### 2. Skip the scraper
From within the `miner/` directory run:
```
./build.sh
./scripts/build_targets.sh
./scripts/scores.sh
./scripts/eval.sh
```

### 3. Start from function database
From within the `miner/` directory run:
```
./build.sh
./download.sh
./scripts/scores.sh
./scripts/eval.sh
```

## Dataset
You can download our function dataset [here](https://tubcloud.tu-berlin.de/s/iGHzW5fdmAoBQjk). The dataset consists of a single jsonl file containing approximately 450k datapoints, each represented as a JSON object with two keys: `source` and `origins`.
- `source`: Contains the function's source code.
- `origins`: A list of all locations where this function appeared. For example, if two crashes of the same project were reproduced at different commit stages and the function was present in both versions, it will have two entries in the origins list.

Each origin entry includes three attributes:
- `project`: The name of the project.
- `crash`: The crash identification number, corresponding to the crash ID in the [OSS-Fuzz bug tracker](https://issues.oss-fuzz.com/issues).
- `frameno`: The lowest frame number of the function in the traceback of the crash, or -1 if it was not part of the traceback.

Example:
```json
{
  "source": "...",
  "origins": [
    {"project": "tmux", "crash": 37181, "frameno": 0},
    {"project": "tmux", "crash": 31106, "frameno": -1}
  ]
}
```
