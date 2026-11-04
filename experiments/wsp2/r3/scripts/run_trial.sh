#!/bin/bash
# usage: run_trial.sh <name> <edits.json> [patch.py extra args]
set -e
cd ~/wsp-exp16/r3
NAME=$1; EDITS=$2; shift 2
~/ml/.venv/bin/python scripts/patch.py --edits "$EDITS" --model ~/wsp-exp/models/Qwen3-0.6B --out ~/wsp-exp16/r3/trial-model "$@" > results/${NAME}_receipt.txt 2>&1
cat results/${NAME}_receipt.txt
~/ml/.venv/bin/python ~/wsp-exp/harness/score.py --model ~/wsp-exp16/r3/trial-model --split t2_diagnostic --out results/${NAME}_t2.json 2>/dev/null | tail -2
python3 - << PY
import json
d=json.load(open("results/${NAME}_t2.json"))["splits"]["t2_diagnostic"]
print("${NAME} per-category:", {k: f"{v['correct']}/{v['n']}" for k,v in d["per_category"].items()})
PY
rm -rf ~/wsp-exp16/r3/trial-model
