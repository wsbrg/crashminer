#!/bin/bash

set -e

source env/bin/activate

data_dir=./data

# Logfile
logdir=$data_dir/logs
regress_log=$logdir/regress.out
extraction_log=$logdir/extraction.out
buildfuzzer_log=$logdir/buildfuzzer.out
reproduction_log=$logdir/reproduction.out

projects=$data_dir/projects.json
filter=$data_dir/filter
database=$data_dir/database/
functions=$data_dir/functions/
testcases=$data_dir/testcases/

nprocs=4

# Create directories
mkdir -p $logdir
mkdir -p $database
mkdir -p $functions


echo "=== Init Database ==="
python src/cli.py initdb \
	-p $projects \
       	-d $database
echo ""

echo "=== Regress ==="
python src/cli.py regress \
	-d $database \
	-f $filter \
	--nprocs $nprocs \
	--progress \
	-t $testcases 2> $regress_log
echo ""

echo "=== Extraction ==="
python src/cli.py extraction \
	-d $database \
	-o $functions \
	-f $filter \
	--nprocs $nprocs \
	--progress 2> $extraction_log
echo ""
