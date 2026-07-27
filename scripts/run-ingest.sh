#!/usr/bin/env bash

set -euo pipefail

echo
echo "========================================"
echo "        Animeplex Ingest Wizard"
echo "========================================"
echo

printf "Paste GitHub Token: "
read GITHUB_TOKEN

export GITHUB_TOKEN

echo
echo "Starting ingest..."
echo

python3 ingest-work.py "$@"

echo
echo "Finished."
read -rp "Press Enter to close..."
