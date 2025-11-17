#!/bin/bash
set -e

# ensure `python` resolves to python3
ln -sf /usr/bin/python3 /usr/local/bin/python
export PYTHON3=/usr/bin/python3
export PYTHON=/usr/bin/python3
export PIP_NO_BUILD_ISOLATION=1

source /opt/ros/humble/setup.bash

if [ -d /workspace ]; then
  if [ -f /workspace/setup.py ] || [ -f /workspace/pyproject.toml ]; then
    python3 -m pip install -e /workspace
  fi
fi

exec "$@"
