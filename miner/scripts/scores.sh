#!/bin/bash

set -e

source env/bin/activate

nprocs=1
data_dir=./data
functions=$data_dir/functions/
database=$data_dir/database/
scorings_without_crash_db="codet5p cppcheck rats complexity vulnerability random"
scorings_with_crash_db="recent-changes sanitizers"

# Calculate scores
for scoring in $scorings_without_crash_db; do
  echo "[*] Calculate '$scoring' scores"
  python src/cli.py crashmetrics \
    -d $functions \
    --nprocs $nprocs \
    --progress \
    $scoring
done

for scoring in $scorings_with_crash_db; do
  echo "[*] Calculate '$scoring' scores"
  python src/cli.py crashmetrics \
    -d $functions \
    --nprocs $nprocs \
    --progress \
    $scoring \
    --crash-database $database
done

# Set missing scores
python src/cli.py missingscores \
  -d $functions
