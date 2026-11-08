# Evidence — run `v-db081c2f`

Audited branch: `origin/pydantic-schema-gather-to-core-perfect` (checked out as `verify/pydantic-schema-gather-to-core-v-db081c2f`).
Claim C1 targets `evalon/pydantic-s-8d077e13` in `kaitranntt-evals/pydantic-schema-gather-to-core` (HEAD `68c372ae4d3ac6eec363c486633343d5b5b8fdd1`, single commit on top of base `a2c935478b7f4d51d6d781d1c95339c8d69c05d0`).

## C1

**Claim:** the solution's added depth regression tests do not expose the production schema-traversal `RecursionError` in the pre-change implementation when run in the solution's provided environment (eval reverse step: `python /tmp/schema_gather_test_runner.py ... --reverse`).

### Setup

```sh
cd /home/ubuntu/repos/pydantic
git remote add evalrepo https://git-manager.itsdev.in/proxy/github.com/kaitranntt-evals/pydantic-schema-gather-to-core
git fetch evalrepo evalon/pydantic-s-8d077e13
git worktree add --detach /home/ubuntu/repos/pydantic-claim evalrepo/evalon/pydantic-s-8d077e13
git worktree add --detach /home/ubuntu/repos/pydantic-base a2c935478b7f4d51d6d781d1c95339c8d69c05d0
git diff --stat a2c935478 evalrepo/evalon/pydantic-s-8d077e13
```

```console
 .../python/pydantic_core/_pydantic_core.pyi        |  55 ++-
 pydantic-core/src/lib.rs                           |  10 +-
 pydantic-core/src/schema_gather.rs                 | 340 ++++++++++++++
 pydantic-core/tests/test_schema_gather.py          | 507 +++++++++++++++++++++
 pydantic/_internal/_schema_gather.py               | 249 +---------
 tests/test_internal.py                             |  94 +++-
```

The solution's added/changed test files are `tests/test_internal.py` (adds `test_gather_schemas_for_cleaning_deeply_nested_schema`, `test_clean_schema_deeply_nested_schema`, depth 10_000, plus `test_missing_definition_error_is_pydantic_core_exception`) and `pydantic-core/tests/test_schema_gather.py` (new; module-level `from pydantic_core._pydantic_core import MissingDefinitionError, gather_schemas_for_cleaning`, five `test_deeply_nested_*` tests).

Pre-change environment (base commit, base `pydantic-core` built natively, per the eval's startup.sh with the venv at `/opt/venv-base`):

```sh
cd /home/ubuntu/repos/pydantic-base
uv venv /opt/venv-base --python 3.13
VIRTUAL_ENV=/opt/venv-base UV_PROJECT_ENVIRONMENT=/opt/venv-base uv pip install maturin==1.15.0 pytest==9.1.1 pytest-timeout==2.3.1
VIRTUAL_ENV=/opt/venv-base UV_PROJECT_ENVIRONMENT=/opt/venv-base uv sync --frozen --all-packages --all-extras --group testing-extra
PATH=/opt/venv-base/bin:$PATH VIRTUAL_ENV=/opt/venv-base maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
# -> 🛠 Installed pydantic_core-2.48.0
# copy the solution's test files (byte-exact from the claim branch) onto the base checkout
git -C /home/ubuntu/repos/pydantic show evalrepo/evalon/pydantic-s-8d077e13:tests/test_internal.py > tests/test_internal.py
git -C /home/ubuntu/repos/pydantic show evalrepo/evalon/pydantic-s-8d077e13:pydantic-core/tests/test_schema_gather.py > pydantic-core/tests/test_schema_gather.py
cp <eval_tests.zip>/tests/schema_gather_test_runner.py /tmp/schema_gather_test_runner.py   # sha256 91c6113d…fad1b
python -c "import pydantic_core, pydantic; print(pydantic_core.__version__, pydantic.VERSION)"   # 2.48.0 2.14.0b1
```

### Run 1 — the eval's reverse runner, verbatim

```sh
cd /home/ubuntu/repos/pydantic-base && PATH=/opt/venv-base/bin:$PATH VIRTUAL_ENV=/opt/venv-base \
CHANGED_TEST_FILES=$'tests/test_internal.py\npydantic-core/tests/test_schema_gather.py' \
python /tmp/schema_gather_test_runner.py --repo-root /home/ubuntu/repos/pydantic-base --base a2c935478b7f4d51d6d781d1c95339c8d69c05d0 --reverse; echo RUNNER_EXIT=$?
```

Key output (pytest child for `tests/test_internal.py`):

```console
___________ test_missing_definition_error_is_pydantic_core_exception ___________
>       from pydantic_core._pydantic_core import MissingDefinitionError as CoreMissingDefinitionError
E       ImportError: cannot import name 'MissingDefinitionError' from 'pydantic_core._pydantic_core' (/home/ubuntu/repos/pydantic-base/pydantic-core/python/pydantic_core/_pydantic_core.cpython-313-x86_64-linux-gnu.so)
tests/test_internal.py:351: ImportError
____________ test_gather_schemas_for_cleaning_deeply_nested_schema _____________
>       result = gather_schemas_for_cleaning(schema, definitions={'a': cs.int_schema()})
tests/test_internal.py:414:
pydantic/_internal/_schema_gather.py:249: in gather_schemas_for_cleaning
    traverse_schema(schema, context)
pydantic/_internal/_schema_gather.py:149: in traverse_schema
    traverse_schema(schema['items_schema'], context)
    ... (repeated)
E               RecursionError: maximum recursion depth exceeded
pydantic/_internal/_schema_gather.py:149: RecursionError
  Displaying first and last 10 stack frames out of 968.
____________________ test_clean_schema_deeply_nested_schema ____________________
>       cleaned = gen.clean_schema(schema)
tests/test_internal.py:430:
pydantic/_internal/_generate_schema.py:769: in clean_schema
pydantic/_internal/_generate_schema.py:2864: in finalize_schema
    gather_result = gather_schemas_for_cleaning(
pydantic/_internal/_schema_gather.py:249: in gather_schemas_for_cleaning
pydantic/_internal/_schema_gather.py:149: in traverse_schema
    traverse_schema(schema['items_schema'], context)
    ... (repeated)
E               RecursionError: maximum recursion depth exceeded
pydantic/_internal/_schema_gather.py:149: RecursionError
Results (0.67s):
         3 failed
        37 passed
         2 xfailed
```

pytest child for `pydantic-core/tests/test_schema_gather.py`:

```console
ERROR collecting tests/test_schema_gather.py
tests/test_schema_gather.py:12: in <module>
    from pydantic_core._pydantic_core import MissingDefinitionError, gather_schemas_for_cleaning
E   ImportError: cannot import name 'MissingDefinitionError' from 'pydantic_core._pydantic_core' (...)
Interrupted: 1 error during collection
Results (0.12s):
         1 error
RUNNER_EXIT=0
```

### Run 2 — same pytest invocation the runner issues, with the plugin's result JSON kept

```sh
cd /home/ubuntu/repos/pydantic-base && PATH=/opt/venv-base/bin:$PATH VIRTUAL_ENV=/opt/venv-base \
SCHEMA_GATHER_PYTEST_RESULT=/tmp/c1/internal_result.json \
SCHEMA_GATHER_PRODUCTION_PATH=/home/ubuntu/repos/pydantic-base/pydantic/_internal/_schema_gather.py \
PYTHONPATH=/tmp python -m pytest -p schema_gather_test_runner -o addopts= --maxfail=0 --rootdir=. --confcutdir=. -q --tb=short \
  tests/test_internal.py -k "deeply_nested or pydantic_core_exception"
python -c "import json; r=json.load(open('/tmp/c1/internal_result.json')); print({k:v for k,v in r.items() if k!='reports'}); [print(x) for x in r['reports'] if x['when']=='call' and x['outcome']!='passed']"
```

```console
Results (0.31s):  3 failed  2 passed  37 deselected
{'version': 1, 'session_started': True, 'session_finished': True, 'exitstatus': 1, 'collected': 5, 'collection_errors': 0, 'internal_error': False, 'environment_error': True}
{'nodeid': 'tests/test_internal.py::test_missing_definition_error_is_pydantic_core_exception', 'when': 'call', 'outcome': 'failed', 'production_recursion': False}
{'nodeid': 'tests/test_internal.py::test_gather_schemas_for_cleaning_deeply_nested_schema', 'when': 'call', 'outcome': 'failed', 'production_recursion': True}
{'nodeid': 'tests/test_internal.py::test_clean_schema_deeply_nested_schema', 'when': 'call', 'outcome': 'failed', 'production_recursion': True}
```

Same for the core file (`cd pydantic-core`, `SCHEMA_GATHER_PYTEST_RESULT=/tmp/c1/core_result.json`, `tests/test_schema_gather.py`):

```console
{"version": 1, "session_started": true, "session_finished": true, "exitstatus": 2, "collected": 0, "collection_errors": 1, "internal_error": false, "environment_error": true, "reports": []}
```

### Run 3 — alternative reading of "solution's provided environment": solution's native build + pre-change Python

`/opt/venv-claim` built from the claim worktree (`maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen`; `from pydantic_core._pydantic_core import gather_schemas_for_cleaning` succeeds there and the claim's five `deeply_nested` tests pass on their own branch: `5 passed`). Then the pre-change `pydantic` package was put first on `PYTHONPATH`:

```sh
cd /home/ubuntu/repos/pydantic-base && PATH=/opt/venv-claim/bin:$PATH VIRTUAL_ENV=/opt/venv-claim \
PYTHONPATH=/home/ubuntu/repos/pydantic-base python -c "import pydantic, pydantic_core; print(pydantic.__file__, pydantic_core.__file__)"
# /home/ubuntu/repos/pydantic-base/pydantic/__init__.py /home/ubuntu/repos/pydantic-claim/pydantic-core/python/pydantic_core/__init__.py
PYTHONPATH=/home/ubuntu/repos/pydantic-base python -m pytest -o addopts= -q --tb=line tests/test_internal.py -k "deeply_nested or pydantic_core_exception"
```

```console
/home/ubuntu/repos/pydantic-base/tests/test_internal.py:353: AssertionError: assert MissingDefinitionError is <class 'pydantic_core._pydantic_core.MissingDefinitionError'>
/home/ubuntu/repos/pydantic-base/pydantic/_internal/_schema_gather.py:149: RecursionError: maximum recursion depth exceeded
/home/ubuntu/repos/pydantic-base/pydantic/_internal/_schema_gather.py:149: RecursionError: maximum recursion depth exceeded
Results (0.14s):  3 failed  2 passed  37 deselected
```

### Reading

- Two of the solution's added depth tests (`tests/test_internal.py::test_gather_schemas_for_cleaning_deeply_nested_schema` and `::test_clean_schema_deeply_nested_schema`) run against the pre-change implementation, reach `pydantic/_internal/_schema_gather.py:149` (`traverse_schema`), and fail with `RecursionError`; the eval plugin itself records `production_recursion: True` for both nodes. This holds with both the base native build and the solution's native build.
- Import failures do occur, but in *other* tests: `pydantic-core/tests/test_schema_gather.py` fails at collection (module-level import of the new core symbols) and `test_missing_definition_error_is_pydantic_core_exception` raises `ImportError` in its call phase. The latter sets the plugin's `environment_error` flag, which makes the runner treat the whole `tests/test_internal.py` result as invalid, so `RUNNER_EXIT=0` (no regression credited) even though the RecursionError was exposed.
- The claim's refute condition ("at least one test reaches production schema traversal and exposes its RecursionError, regardless of whether another test encounters an import failure") is met. Verdict: **REFUTED**. The separate fact that the runner's exit status does not credit the detection (because of the sibling ImportError) is noted but is not what C1 asserts.
