#!/usr/bin/env bash
# Compile every example into dist/.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/dist"
for f in "$ROOT"/examples/*.atml; do
  base="$(basename "$f" .atml)"
  python3 "$ROOT/compiler/atmlc.py" build "$f" -o "$ROOT/dist/$base.html"
done
echo "built $(ls "$ROOT"/dist/*.html | wc -l) files into dist/"
