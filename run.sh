#!/usr/bin/env bash
# Run the scraper with project dependencies (macOS-friendly: no global pip/python needed).
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python 3 first (e.g. xcode-select --install or python.org)." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv ..."
  python3 -m venv .venv
fi

echo "Installing dependencies (if needed) ..."
.venv/bin/python -m pip install -q -r requirements.txt

exec .venv/bin/python scraper.py "$@"
