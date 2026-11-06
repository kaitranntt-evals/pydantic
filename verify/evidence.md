## Environment

All runs on this VM (Ubuntu, 8 cores). The eval's `/opt/venv` did not exist, so it was recreated exactly as `startup.sh` does
(`uv venv /opt/venv --python 3.13`, `uv pip install maturin==1.15.0 pytest==9.1.1 pytest-timeout==2.3.1`,
`uv sync --frozen --all-packages --all-extras --group testing-extra`), then `maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen`.
Claim-target branches were fetched from `kaitranntt-evals/pydantic-schema-gather-to-core` (added as git remote `target`) and checked
out in separate `jj` workspaces, each with its own venv built the same way:

| checkout | commit | venv |
|---|---|---|
| `/home/ubuntu/repos/pydantic` — `pydantic-schema-gather-to-core-perfect` (audited solution) | `585c9944900a` | `/opt/venv` |
| `/home/ubuntu/repos/pydantic-c12` — `evalon/pydantic-s-4aec16e5` (C1, C2) | `11447fb477a4` | `/opt/venv-c12` |
| `/home/ubuntu/repos/pydantic-c3` — `evalon/pydantic-s-7555a0b4` (C3) | `28ea588f5a6a` | `/opt/venv-c3` |

All three share merge-base `a2c935478b7f4d51d6d781d1c95339c8d69c05d0` ("Use maturin `--pgo` option (#13220)").
`maturin develop … --frozen` exited 0 in every checkout (`/tmp/build-*.log`, `Finished `dev` profile`).

## C1

Branch `evalon/pydantic-s-4aec16e5`, file `pydantic-core/src/schema_gather.rs` lines 114-126:

```rust
/// Iterate over the values of a dict (fast path) or of any mapping.
fn for_each_value<'py>(obj: &Bound<'py, PyAny>, mut f: impl FnMut(Bound<'py, PyAny>) -> PyResult<()>) -> PyResult<()> {
    if let Ok(dict) = obj.cast::<PyDict>() {
        for (_, value) in dict.iter() {
            f(value)?;
        }
    } else {
        for value in obj.call_method0(intern!(obj.py(), "values"))?.try_iter()? {
```

`cast::<PyDict>()` succeeds for dict subclasses, so the storage-order fast path is taken and `values()` is never called.
(The names in the claim — `children_values_required` / `push_values` / `mapping_values` — do not exist on this branch; `for_each_value` is the equivalent.)

Eval fixture (byte-exact copy of `tests/test_eval_schema_gather_traversal.py` from `eval_tests.zip`, copied into the workspace and removed afterwards):

```sh
cd /home/ubuntu/repos/pydantic-c12 && export PATH=/opt/venv-c12/bin:$PATH VIRTUAL_ENV=/opt/venv-c12
pytest -q tests/test_eval_schema_gather_traversal.py -k "test_mapping_values_protocol or test_sequence_and_metadata_protocol" -p no:cacheprovider
```

```console
>       assert list(result_rev['collected_references'].keys()) == ['b', 'a'], "ReversedValuesDict values() bypassed"
E       AssertionError: ReversedValuesDict values() bypassed
E       assert ['a', 'b'] == ['b', 'a']
tests/test_eval_schema_gather_traversal.py:241: AssertionError
Results (0.14s):
         1 failed
         1 passed
         2 deselected
```

Direct probe (`verify/repro/c1_c2_dict_list_subclass_probe.py`; `ReversedValuesDict.values()` returns `reversed(list(super().values()))`,
fields stored as `f_a`, `f_b`):

```sh
cd /home/ubuntu/repos/pydantic-c12 && /opt/venv-c12/bin/python /home/ubuntu/repos/pydantic/verify/repro/c1_c2_dict_list_subclass_probe.py
```

```console
C1 storage order  : ['f_a', 'f_b']
C1 values() order : ['b', 'a']
C1 collected order: ['a', 'b']
```

Same probe on the audited `pydantic-schema-gather-to-core-perfect` checkout (`/opt/venv/bin/python …`) and against the pure-Python
`pydantic/_internal/_schema_gather.py` from the merge-base `a2c935478` both print `C1 collected order: ['b', 'a']`, i.e. the
pre-existing behaviour honours `values()` and only the `evalon/pydantic-s-4aec16e5` implementation follows storage order.

Verdict: CONFIRMED. Impact: only reachable when a caller hands a `dict` subclass with an overridden `values()` as a core-schema
mapping (`fields`, `definitions`-like containers); the order of `collected_references` (and hence of deferred discriminator
handling / inlining order) then silently follows dict storage order rather than the subclass's protocol. Ordinary `dict`
inputs are unaffected. The eval fixture `test_mapping_values_protocol` fails on this branch.

## C2

Branch `evalon/pydantic-s-4aec16e5`, `pydantic-core/src/schema_gather.rs` lines 100-112:

```rust
/// Iterate over the items of a list (fast path) or of any iterable.
fn for_each_item<'py>(obj: &Bound<'py, PyAny>, mut f: impl FnMut(Bound<'py, PyAny>) -> PyResult<()>) -> PyResult<()> {
    if let Ok(list) = obj.cast::<PyList>() {
        for item in list.iter() {
            f(item)?;
        }
    } else {
        for item in obj.try_iter()? {
```

(The claim's `for_each_item` exists; `push_iter` / `extend_from_iterable` do not — `for_each_item` is the only item iterator.)

Direct probe (`verify/repro/c1_c2_dict_list_subclass_probe.py`): `SwappedList(list)` stores
`[definition_reference_schema('stored')]` but its `__iter__` yields `[definition_reference_schema('yielded')]`.

```sh
cd /home/ubuntu/repos/pydantic-c12 && /opt/venv-c12/bin/python /home/ubuntu/repos/pydantic/verify/repro/c1_c2_dict_list_subclass_probe.py
```

```console
C2 list(stored)   : ['stored']
C2 iter(yielded)  : ['yielded']
C2 collected      : ['stored']
C2 union collected: ['stored']
```

Same probe on the audited `pydantic-schema-gather-to-core-perfect` checkout and against the merge-base pure-Python gatherer:

```console
C2 collected      : ['yielded']
C2 union collected: ['yielded']
```

The eval fixture `test_sequence_and_metadata_protocol` PASSES on `evalon/pydantic-s-4aec16e5` (see the C1 run above: `1 passed`)
because its `ReversedTuple` is a **tuple** subclass, which does not match the `PyList` fast path; the fixture therefore does not
exercise the list-subclass case the claim describes.

Verdict: CONFIRMED. Impact: a `list` subclass whose `__iter__` yields something other than its stored elements is traversed by
stored contents, so the children reachable only through `__iter__` are never visited (their `definition-ref`s are not collected,
their discriminators not deferred) and children present only in storage are. Only `list` subclasses with a divergent
`__iter__` trigger it; plain lists, tuples and generators behave as before. No existing fixture catches it.

## C3

Branch `evalon/pydantic-s-7555a0b4`. Fixtures:

- `pydantic-core/tests/test_schema_gather.py::test_deeply_nested_schema` — `depth = 100_000` (lines 96-106)
- `tests/test_internal.py::test_gather_schemas_for_cleaning_deeply_nested_schema` — `depth = 10_000` (lines 350-362)
- `tests/test_internal.py::test_clean_schema_deeply_nested_schema` — `depth = 10_000` (lines 365-378)

`grep -n 'skip\|xfail\|platform' tests/test_internal.py pydantic-core/tests/test_schema_gather.py pydantic-core/tests/conftest.py`
shows no `emscripten`/platform skip on any of them (only an unrelated `xfail` at `tests/test_internal.py:66` and `importorskip('devtools')` at :148).
The file `tests/test_schema_gather.py` named by the claim does not exist on this branch; the nearest equivalents are the three fixtures above.

### teardown part

Line trace of each fixture body (`verify/repro/c3_trace_deep_fixtures.py`, uses `sys.settrace` and prints every distinct source
line executed, plus `gc.get_objects()` counts before/after):

```sh
cd /home/ubuntu/repos/pydantic-c3 && /opt/venv-c3/bin/python /home/ubuntu/repos/pydantic/verify/repro/c3_trace_deep_fixtures.py
```

```console
### .../pydantic-c3/pydantic-core/tests/test_schema_gather.py::test_deeply_nested_schema (tracked objects before=31625 after=31609)
  L97: depth = 100_000
  L98: innermost = core_schema.definition_reference_schema('Model')
  L99: schema = innermost
  L100: for _ in range(depth):
  L101: schema = core_schema.list_schema(schema)
  L103: recursion_limit = sys.getrecursionlimit()
  L104: result = gather_schemas_for_cleaning(schema, {'Model': core_schema.int_schema(ref='Model')})
  L105: assert sys.getrecursionlimit() == recursion_limit
  L106: assert result['collected_references']['Model'] is innermost
  distinct lines executed: 9; total line events: 200008

### .../pydantic-c3/tests/test_internal.py::test_gather_schemas_for_cleaning_deeply_nested_schema (tracked objects before=31612 after=31612)
  L351: depth = 10_000
  ...
  L362: assert result['deferred_discriminator_schemas'] == []
  distinct lines executed: 11; total line events: 20010

### .../pydantic-c3/tests/test_internal.py::test_clean_schema_deeply_nested_schema (tracked objects before=31612 after=31612)
  L366: depth = 10_000
  ...
  L375: for _ in range(depth):
  L376: assert cleaned['type'] == 'list'
  L377: cleaned = cleaned['items_schema']
  L378: assert cleaned == cs.int_schema(ref='Model')
  distinct lines executed: 11; total line events: 50008
```

Every executed line is construction, the call under test, or an assertion; none pops/clears/unlinks levels before the function
returns. The whole 100,000- / 10,000-level graph is released at once when the locals go out of scope (object count returns to
baseline), i.e. by the interpreter's recursive container deallocation. On native CPython 3.13 this is harmless
(`/opt/venv-c3/bin/python -c "...100000 nested dicts...; del s"` → `native CPython deleted depth 100000 OK`).

teardown: CONFIRMED for all three fixtures (released intact, no iterative teardown).

### platform_execution part

CI selection (`.github/workflows/ci.yml` job `test-pyemscripten`, lines 549-587, Python 3.14 matrix): after installing the Pyodide
wheel it runs, from the repository root with no `working-directory`:

```yaml
          python -m pytest
```

Root `pyproject.toml:186` has `testpaths = ['tests']`, and `tests/pydantic_core` is a symlink to `../pydantic-core/tests`
(`ls -la tests | grep pydantic_core` → `pydantic_core -> ../pydantic-core/tests`), so that command collects both the 10,000-level
internal fixtures and the 100,000-level native fixture:

```sh
cd /home/ubuntu/repos/pydantic-c3 && /opt/venv-c3/bin/python -m pytest --collect-only -q -p no:cacheprovider | grep deeply_nested
```

```console
tests/pydantic_core/test_schema_gather.py::test_deeply_nested_schema
tests/test_internal.py::test_gather_schemas_for_cleaning_deeply_nested_schema
tests/test_internal.py::test_clean_schema_deeply_nested_schema
```

(plus two unrelated `test_core_schema_with_deeply_nested_schema_with_multiple_references_gets_inlined` cases and a benchmark).

Skip evaluation as on Pyodide: the plugin `verify/repro/c3_emsim_plugin.py` sets `sys.platform = 'emscripten'` in
`pytest_configure`, before test modules are imported, so every `skipif(sys.platform == 'emscripten')` evaluates as it would on Pyodide.

```sh
cd /home/ubuntu/repos/pydantic-c3 && PYTHONPATH=/home/ubuntu/repos/pydantic/verify/repro /opt/venv-c3/bin/python -m pytest -p c3_emsim_plugin -q -rs -p no:cacheprovider tests/test_internal.py tests/pydantic_core/test_schema_gather.py -k deeply_nested
```

```console
.....                                                                    [100%]
Results (0.34s):
         5 passed
        47 deselected
```

Contrast on the audited `pydantic-schema-gather-to-core-perfect` checkout, whose `tests/test_schema_gather.py:243` carries
`@pytest.mark.skipif(sys.platform == 'emscripten', reason='Deallocating the deeply nested schema overflows the JS stack')`:

```sh
cd /home/ubuntu/repos/pydantic && PYTHONPATH=verify/repro /opt/venv/bin/python -m pytest -p c3_emsim_plugin -q -rs -p no:cacheprovider tests/test_schema_gather.py tests/test_internal.py -k deeply_nested
```

```console
s..                                                                      [100%]
Results (0.10s):
         2 passed
         1 skipped
```

Actual Emscripten behaviour (CPython 3.14 under Pyodide 314.0.7 in Node 22.14.0, `verify/repro/c3_pyodide_dealloc.mjs`; builds the
same `list_schema`-shaped nesting as the fixtures and deletes it):

```sh
cd /tmp/pyo && npm install pyodide   # -> pyodide@314.0.7
node /home/ubuntu/repos/pydantic/verify/repro/c3_pyodide_dealloc.mjs 1000
node /home/ubuntu/repos/pydantic/verify/repro/c3_pyodide_dealloc.mjs 10000
node /home/ubuntu/repos/pydantic/verify/repro/c3_pyodide_dealloc.mjs 100000
```

```console
pyodide python: 3.14.2 (main, Sep 14 2026, 03:03:51) [Clang 23.0.0git ...
built depth 1000 recursion limit 1000
deleted OK depth 1000
---
built depth 10000 recursion limit 1000
Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers.
The cause of the fatal error was:
RangeError: Maximum call stack size exceeded
  pyodide_fatal_error: true
Stack (most recent call first):
  File "<exec>", line 8 in <module>        # line 8 is `del schema`
---
built depth 100000 recursion limit 1000
Pyodide has suffered a fatal error. ...
RangeError: Maximum call stack size exceeded
```

Construction and the (iterative, Rust) gather survive; the crash happens at `del schema`, i.e. during deallocation of the intact graph,
at both 10,000 and 100,000 levels. This is a fatal interpreter error, not a catchable Python exception, so under the CI selection above
the Pyodide pytest process dies rather than reporting a failure.

platform_execution: CONFIRMED (no skip; all three deep fixtures are selected by the PyEmscripten job's `python -m pytest`).

Verdict (both parts): CONFIRMED. Impact: the `test-pyemscripten` CI job for this branch will hit a Pyodide fatal
`RangeError: Maximum call stack size exceeded` when the first deep fixture's graph is torn down. The upstream solution
(`pydantic-schema-gather-to-core-perfect`) avoids it with the `skipif(sys.platform == 'emscripten')` marker quoted above;
an alternative is to dismantle the graph iteratively at the end of each fixture.

## C4

Audited branch `pydantic-schema-gather-to-core-perfect` (`585c9944900a`) in `/home/ubuntu/repos/pydantic`.

Changed Python test files:

```sh
git diff --name-only a2c935478b7f4d51d6d781d1c95339c8d69c05d0 585c9944900a -- '*.py' | grep -i test
```

```console
tests/test_schema_gather.py
```

(No files under `pydantic-core/tests` changed, so the only "package root" involved is the repository root.)

Build (solution's procedure, `startup.sh` tail):

```sh
cd /home/ubuntu/repos/pydantic && export PATH=/opt/venv/bin:$HOME/.cargo/bin:$PATH VIRTUAL_ENV=/opt/venv UV_PROJECT_ENVIRONMENT=/opt/venv UV_OFFLINE=1 CARGO_NET_OFFLINE=true
maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
```

```console
   Compiling pydantic-core v2.48.0 (/home/ubuntu/repos/pydantic/pydantic-core)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 4.51s
📦 Built wheel for CPython 3.13 to /tmp/.tmpo2EGKB/pydantic_core-2.48.0-cp313-cp313-linux_x86_64.whl
EXIT=0
```

Test runs (both plain `pytest` from `/opt/venv` and `uv run --frozen pytest`, as the claim words it):

```sh
pytest -q tests/test_internal.py tests/test_schema_gather.py -p no:cacheprovider
uv run --frozen pytest -q tests/test_internal.py -p no:cacheprovider
uv run --frozen pytest -q tests/test_schema_gather.py -p no:cacheprovider
```

```console
...xx................................................                    [100%]
Results (0.62s):
        51 passed
         2 xfailed
---
...xx................................                                    [100%]
Results (0.50s):
        35 passed
         2 xfailed
---
................                                                         [100%]
Results (0.08s):
        16 passed
```

The two `xfailed` are the pre-existing `@pytest.mark.xfail` at `tests/test_internal.py:66`
(`test_core_schema_simple_recursive_schema_uses_refs`, present at the merge-base), not failures. No collection error, no failing assertion.

Verdict: REFUTED.
