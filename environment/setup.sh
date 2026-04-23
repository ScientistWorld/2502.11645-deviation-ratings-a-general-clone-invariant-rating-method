#!/bin/bash
# Install runtime Python deps into /home/user/pkgs.

set -e

mkdir -p /home/user/pkgs

# The scheduler's setup wrapper rewrites `python3 -m pip` to `uv pip`.
# Call the container's interpreter by absolute path to preserve pip's
# `--target` behavior and avoid writes to /usr/local.
/usr/local/bin/python3 -m pip install --no-cache-dir --target /home/user/pkgs numpy scipy
