#!/bin/bash

for f in $(find /in -type f); do
	fname=$(basename $f | cut -d'.' -f1)
	rats -w 3 --resultsonly --quiet $f &> /out/$fname
done
