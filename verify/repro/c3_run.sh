#!/bin/bash
# Run: bash verify/repro/c3_run.sh [stub-root ...]   -- type-checks c3_some_subclass.py against each <stub-root>/pydantic-core/python
# Needs: uv venv /opt/venv-tools --python 3.13 && VIRTUAL_ENV=/opt/venv-tools uv pip install pyright==1.1.411 mypy==2.3.0 typing-extensions
here=$(cd "$(dirname "$0")" && pwd)
roots=("$@"); [ ${#roots[@]} -eq 0 ] && roots=(/home/ubuntu/repos/pyd-e635 /home/ubuntu/repos/pyd-base)
for root in "${roots[@]}"; do
  echo "===== stubs from $root ($(git -C "$root" rev-parse --short HEAD))"
  grep -n -B2 '^class Some' "$root/pydantic-core/python/pydantic_core/_pydantic_core.pyi"
  d=$(mktemp -d); cp "$here/c3_some_subclass.py" "$d/"
  echo "{\"extraPaths\": [\"$root/pydantic-core/python\"]}" > "$d/pyrightconfig.json"
  (cd "$d" && /opt/venv-tools/bin/pyright --pythonpath /opt/venv-tools/bin/python c3_some_subclass.py; echo "pyright exit=$?")
  (cd "$d" && MYPYPATH="$root/pydantic-core/python" /opt/venv-tools/bin/mypy --python-executable /opt/venv-tools/bin/python c3_some_subclass.py; echo "mypy exit=$?")
done
