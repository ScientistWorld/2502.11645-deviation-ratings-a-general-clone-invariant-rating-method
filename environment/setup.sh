#!/bin/bash
# Install runtime Python deps into /home/user/pkgs.

set -e

mkdir -p /home/user/pkgs

python3 -m pip install --no-cache-dir --target /home/user/pkgs numpy scipy
