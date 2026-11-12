#!/bin/bash
# Run: verify/repro/c5_pyright_gather_interface.sh <worktree of evalon/pydantic-s-c2733622> <its venv, with pyright==1.1.411 installed>
# C5: the repo's typing commands (`uv run pyright pydantic`, `make -C pydantic-core pyright`) on the claim branch.
# Exit status 0 = a diagnostic attributable to the gathering interface was reported.
W=${1:-/home/ubuntu/repos/wt-c2733622}; V=${2:-/opt/venv-c2733622}
cd "$W" || exit 2
echo "## pyright pydantic   (.pre-commit-config.yaml 'typecheck' hook: uv run pyright pydantic)"
"$V/bin/pyright" --pythonpath "$V/bin/python" pydantic 2>&1 | grep -v 'new pyright\|Please install' | tee /tmp/c5_root.txt
echo "## (cd pydantic-core && pyright)   (make -C pydantic-core pyright: uv run pyright)"
(cd pydantic-core && "$V/bin/pyright" --pythonpath "$V/bin/python" 2>&1 | grep -v 'new pyright\|Please install')
grep -q '_schema_gather.py.* - error' /tmp/c5_root.txt
