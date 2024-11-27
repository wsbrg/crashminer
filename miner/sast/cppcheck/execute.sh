#!/bin/bash

for f in $(find /in -type f); do
	fname=$(basename $f | cut -d'.' -f1)
	cppcheck --enable=all --inconclusive --quiet --xml $f &> /out/$fname
done
