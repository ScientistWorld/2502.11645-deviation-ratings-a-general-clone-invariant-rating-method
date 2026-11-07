#!/bin/bash
# Held-out test evaluation for this benchmark. Takes no arguments.
#
# eval/test/evaluate.py generates the hidden games, runs the rating program
# scripts/rate.sh on them, and writes scoring/scores_test.json.
#
# python3 -I ignores PYTHONPATH, user site-packages and the working directory;
# exec replaces this shell so nothing appended to this file runs afterwards.

set -e

cd /home/user
mkdir -p scoring

exec python3 -I eval/test/evaluate.py
