#!/bin/bash
set -e

# ensure `python` resolves to python3
ln -sf /usr/bin/python3 /usr/local/bin/python
export PYTHON3=/usr/bin/python3
export PYTHON=/usr/bin/python3
export PIP_NO_BUILD_ISOLATION=1

# expose KrisLibrary's CMake modules where Klampt expects them when the repo is bind-mounted
if [ -d /workspace/Cpp ]; then
  mkdir -p /workspace/Cpp/Dependencies
  if [ ! -e /workspace/Cpp/Dependencies/KrisLibrary ]; then
    ln -s /opt/KrisLibrary /workspace/Cpp/Dependencies/KrisLibrary
  fi
fi

source /opt/ros/humble/setup.bash

exec "$@"
