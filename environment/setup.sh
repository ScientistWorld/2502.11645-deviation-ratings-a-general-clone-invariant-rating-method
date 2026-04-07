#!/bin/bash
# Install scipy/numpy into /home/user/pkgs (overlay is read-only at runtime).
# PYTHONPATH must be set at runtime for packages to be found.

set -e

export UV_CACHE_DIR=/tmp/uv_cache
mkdir -p /home/user/pkgs

# Install to user-writable directory, avoiding the read-only overlay.
uv pip install --system --target /home/user/pkgs numpy scipy

# Create a script to set PYTHONPATH for all runs
cat > /home/user/pkgs/activate.sh << 'EOF'
#!/bin/bash
export PYTHONPATH=/home/user/pkgs:$PYTHONPATH
EOF
chmod +x /home/user/pkgs/activate.sh