#!/bin/bash

set -e

if [ ! -d data/functions ]; then
  echo "[*] Download functions dataset"
  pushd data
    wget https://tubcloud.tu-berlin.de/s/iJZnd7TKz3Br4gD/download/functions.tar.gz
    tar xzf functions.tar.gz
  popd
fi
