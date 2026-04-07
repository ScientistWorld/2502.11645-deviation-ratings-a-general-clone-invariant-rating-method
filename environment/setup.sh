#!/bin/bash
# Install scipy/numpy into /home/user/pkgs (overlay is read-only at runtime).
# PYTHONPATH is prepended at container entrypoint to pick these up.

set -e

export UV_CACHE_DIR=/tmp/uv_cache
mkdir -p /home/user/pkgs

# Install to user-writable directory, avoiding the read-only overlay.
# UV_NO_PROGRESS=1 quiets output; --target is critical.
uv pip install --system --target /home/user/pkgs numpy scipy
