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

if [ -d ${database} ]; then
  for scoring in $scorings_with_crash_db; do
    echo "[*] Calculate '$scoring' scores"
    python src/cli.py crashmetrics \
      -d $functions \
      --nprocs $nprocs \
      --progress \
      $scoring \
      --crash-database $database
  done
else
  echo "[!] The metrics '${scorings_with_crash_db}' cannot be calculated as they require the full database from scraping."
  echo "    This database does not exist at '${scorings_with_crash_db}'. This error is expected if you did not re-scrape."
fi

# Set missing scores
python src/cli.py missingscores \
  -d $functions
