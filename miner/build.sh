#!/bin/bash

if ! python -V | grep "3.9.23" &>/dev/null; then
  echo "[!] The code has only been tested with python version 3.9.23."
  echo "    Some parts are known to break for recent python versions,"
  echo "    such as 3.13.x. Therefore, please use 3.9.23 to make sure"
  echo "    the experiments work as expected. You may want to use pyenv"
  echo "    to setup a 3.9.23 python interpreter for this repository."
  exit 1
fi


# Check if in venv
python -c "import sys; sys.exit(1 if sys.prefix == sys.base_prefix else 0)"
if [[ $? -ne 0 ]]; then
  set -e
  if [ ! -d env/ ]; then
    echo "[*] Create virtual environment"
    python -m venv env
  fi
  source env/bin/activate
fi

# Exit on fail
set -e

echo "[*] Install python dependencies"
python -m pip install -r requirements.txt

echo "[*] Setup tree-sitter parsers"
pushd src/utils/parsers
find . -mindepth 1 -maxdepth 1 -type d -print0 | xargs -0 rm -rf
git clone https://github.com/tree-sitter/tree-sitter-c
pushd tree-sitter-c
git checkout df6ac34d5eb1dccfac8f2a9011a8491300818d7c
popd
git clone https://github.com/tree-sitter/tree-sitter-cpp
pushd tree-sitter-cpp
git checkout 72fd00128f1c38319670cbf4bcedbba0dc849d96
popd
python build_parsers.py
popd

echo "[*] Setup oss-fuzz"
git clone https://github.com/MNayer/oss-fuzz.git
pushd oss-fuzz
git checkout 59d11e8ad04c23aa741ad8395587942be2710852
docker build --pull -t gcr.io/oss-fuzz-base/base-image "$@" infra/base-images/base-image
docker build -t gcr.io/oss-fuzz-base/base-clang "$@" infra/base-images/base-clang
docker build -t gcr.io/oss-fuzz-base/base-builder "$@" infra/base-images/base-builder
docker build -t gcr.io/oss-fuzz-base/base-runner "$@" infra/base-images/base-runner
popd

echo "[*] Setup mcpp"
git clone https://github.com/LPirch/mcpp.git
pushd mcpp
#git checkout 42718f0015e9a45589938a8909c115d0052e59a3
git checkout a26b21246b7e9af317193ce8afb93ddd87ef8abc
pip install .
popd

echo "[*] Setup rats"
pushd sast/rats
./build.sh
popd

echo "[*] Setup cppcheck"
pushd sast/cppcheck
./build.sh
popd

if [ ! -d data/testcases ]; then
  echo "[*] Download testcases"
  pushd data
    wget https://tubcloud.tu-berlin.de/s/5ofZBZpW5z7L4zC/download/testcases.tar.gz
    tar xzf testcases.tar.gz
    rm -rf testcases.tar.gz
  popd
fi
if [ ! -f data/projects.json ]; then
  echo "[*] Download scrape result"
  pushd data
    wget https://tubcloud.tu-berlin.de/s/jR7BxPnRHqzMWYT/download/projects.json
  popd
fi
if [ ! -d assets ]; then
  echo "[*] Download CodeT5+ model"
  mkdir assets
  pushd assets
    wget https://tubcloud.tu-berlin.de/s/jx6XicX5ZsL2T8j/download/model_normalized.bin
  popd
fi
