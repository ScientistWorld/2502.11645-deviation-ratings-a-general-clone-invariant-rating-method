#!/bin/bash
# Install runtime Python deps into the container system Python.

set -e

uv pip install --system numpy scipy
