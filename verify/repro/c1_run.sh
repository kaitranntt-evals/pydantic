#!/bin/bash
# Run: verify/repro/c1_run.sh <worktree> <runtime-venv>   (needs /opt/venv-tools with pyright==1.1.411 mypy==2.3.0; omit <runtime-venv> to type-check only)
set -u
WT=$(realpath "$1"); RT=${2:-}; HERE=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d); cp "$HERE/c1_schemaerror_subclass.py" "$TMP/probe.py"
cat > "$TMP/pyrightconfig.json" <<JSON
{"include": ["probe.py"], "extraPaths": ["$WT/pydantic-core/python"], "typeCheckingMode": "strict"}
JSON
cd "$TMP"
echo "== declaration ($WT)"; grep -n -B2 '^class SchemaError\|^class SchemaGatherMissingDefinitionError' "$WT/pydantic-core/python/pydantic_core/_pydantic_core.pyi"
echo "== pyright"; /opt/venv-tools/bin/pyright --pythonpath /opt/venv-tools/bin/python -p pyrightconfig.json; echo "pyright exit=$?"
echo "== mypy"; MYPYPATH="$WT/pydantic-core/python" /opt/venv-tools/bin/mypy --follow-imports=silent probe.py; echo "mypy exit=$?"
if [ -n "$RT" ]; then
  echo "== runtime"; "$RT/bin/python" -c "import pydantic_core, sys; print(pydantic_core.__file__); from pydantic_core import SchemaError as S; print('Py_TPFLAGS_BASETYPE set:', bool(S.__flags__ & (1 << 10)))"
  "$RT/bin/python" probe.py; echo "python exit=$?"
fi
