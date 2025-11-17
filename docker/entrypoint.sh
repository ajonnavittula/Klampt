#!/bin/bash
set -e

if [ -d /workspace ]; then
  if [ -f /workspace/setup.py ] || [ -f /workspace/pyproject.toml ]; then
    python3 -m pip install -e /workspace
  fi
fi

exec "$@"
