#!/bin/bash

set -e

logdir=./logs
datadir=./data

if [ ! -d env/ ]; then
  echo "[!] Run build.sh first"
fi

if [ ! -d $logdir ]; then
  echo "[*] Create empty logging directory at '$logdir'"
  mkdir -p $logdir
fi

if [ ! -d $datadir ]; then
  echo "[*] Create empty data directory at '$datadir'"
  mkdir -p $datadir
fi

echo "[*] Activate virtual environment"
source env/bin/activate

echo "[+] Start scraping (issues)"
python src/scraper.py issues -s $datadir/issues.json > $logdir/scraper_issues.log
echo "[+] Start scraping (comments)"
python src/scraper.py comments -s $datadir/comments.json $datadir/issues.json > $logdir/scraper_comments.log
echo "[+] Start analyzing (analyze)"
python src/analyze.py analyze -s $datadir/analyzed.json $datadir/comments.json > $logdir/analyze_analyze.log
echo "[+] Start analyzing (ossfuzz)"
python src/analyze.py ossfuzz -s $datadir/ossfuzz.json $datadir/analyzed.json > $logdir/analyze_ossfuzz.log
echo "[+] Start analyze (git)"
python src/analyze.py git -s $datadir/projects.json $datadir/ossfuzz.json > $logdir/analyze_git.log
echo "[+] Start downloading testcases"
python src/testcases.py data/testcases/ data/projects.json > $logdir/testcases.log
