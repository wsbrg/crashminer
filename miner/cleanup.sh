#!/bin/bash

# Exit on fail
set -e

rm -rf env/
rm -rf utils/parsers/tree-sitter-c
rm -rf utils/parsers/tree-sitter-cpp
rm -rf oss-fuzz
rm -rf mcpp
rm -rf data/database data/functions data/logs data/results
rm -rf __pycache__
