#!/bin/bash
# Install Python packages into the container overlay.
#
# This paper needs CVXPY for linear programming.
# Game theory computation — CPU only, no GPU required.

set -e

# CVXPY for sequential LP solving (deviation rating algorithm)
uv pip install --system \
    numpy \
    cvxpy \
    scipy

# ECOS solver (ships with CVXPY, but explicit install for safety)
uv pip install --system \
    ecos

# Optional: SCS solver as fallback
uv pip install --system \
    scs
