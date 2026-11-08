#!/usr/bin/env bash
# Run: bash verify/repro/c4_typed_dict_py310_311.sh <checkout of evalon/pydantic-s-44e1e127>   (needs uv + cargo; builds two venvs)
set -euo pipefail
repo=${1:?path to a checkout of evalon/pydantic-s-44e1e127}
for pyver in 3.10 3.11; do
  venv=/opt/venv-c4-${pyver//./}
  uv venv "$venv" --python "$pyver"
  VIRTUAL_ENV=$venv uv pip install maturin==1.15.0 pytest==9.1.1 pytest-timeout==2.3.1
  (cd "$repo" && VIRTUAL_ENV=$venv UV_PROJECT_ENVIRONMENT=$venv uv sync --frozen --all-packages --all-extras --group testing-extra \
     && VIRTUAL_ENV=$venv "$venv/bin/maturin" develop --manifest-path pydantic-core/Cargo.toml --uv --frozen)
  echo "=== Python $pyver"
  (cd "$repo" && "$venv/bin/python" -m pytest tests/test_internal.py -q -p no:cacheprovider -k gather) || true
done
