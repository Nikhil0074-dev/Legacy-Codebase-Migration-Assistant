#!/usr/bin/env sh
set -e
cd "$(dirname "$0")/../backend"
[ -d tools/node_modules ] || (cd tools && npm install --silent)
python3 -m pytest -v
