#!/bin/bash

if [ ! -d env/ ]; then
  echo "[*] Create virtual environment"
  python -m venv env
fi

echo "[*] Activate virtual environment"
source env/bin/activate

echo "[*] Install requirements"
pip install -r requirements.txt
