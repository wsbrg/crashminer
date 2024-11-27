#!/bin/bash

set -e

source env/bin/activate

data_dir=./data
output_dir=$data_dir/results/evaluation
output_path=${output_dir}/mean-ndcg.png

metric=all
maxcutoff=1000

mkdir -p ${output_dir}

echo "[+] Create the mean-NDCG plot at '${output_path}' for metric '${metric}'"
python src/cli.py evaluate --functions ${data_dir}/functions -o ${output_path} --metric ${metric} --topn ${maxcutoff}
