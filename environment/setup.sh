#!/bin/bash
# Install runtime Python deps into /home/user/pkgs.
# The container overlay is not writable at /usr/local during setup, so we
# install into the workspace and expose it through PYTHONPATH.

set -e

export UV_CACHE_DIR=/tmp/uv_cache
mkdir -p /home/user/pkgs

uv pip install --target /home/user/pkgs numpy scipy
