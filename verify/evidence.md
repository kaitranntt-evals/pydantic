## Setup

Audited branch: [pydantic-schema-gather-to-core-perfect](https://github.com/kaitranntt-evals/pydantic/tree/pydantic-schema-gather-to-core-perfect) at `585c9944900af8d36901073c2eef0ce8d508e215` (eval base `a2c935478b7f4d51d6d781d1c95339c8d69c05d0`).

Claim branches come from the sibling repository `kaitranntt-evals/pydantic-schema-gather-to-core`, one detached worktree and one venv (own native build) each:

| claim | branch | commit | worktree | venv |
|---|---|---|---|---|
| C4 | [evalon/pydantic-s-d2a5977c](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-d2a5977c) | `f0e07f8fc` | `/home/ubuntu/repos/wt-d2a5977c` | `/opt/venv-d2a5977c` |
| C5 | [evalon/pydantic-s-c2733622](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-c2733622) | `33ffa3001` | `/home/ubuntu/repos/wt-c2733622` | `/opt/venv-c2733622` |
| C6 | [evalon/pydantic-s-734c6460](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-734c6460) | `8abb69442` | `/home/ubuntu/repos/wt-734c6460` | `/opt/venv-734c6460` |
| C7 | [evalon/pydantic-s-c9d6135f](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-c9d6135f) | `5908abf04` | `/home/ubuntu/repos/wt-c9d6135f` | `/opt/venv-c9d6135f` |
| C8 | [evalon/pydantic-s-e2125aea](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-e2125aea) | `68ba86251` | `/home/ubuntu/repos/wt-e2125aea` | `/opt/venv-e2125aea` |

```sh
cd /home/ubuntu/repos/pydantic
git fetch origin pydantic-schema-gather-to-core-perfect
git checkout -b verify/pydantic-schema-gather-to-core-v-aa5a3af4 origin/pydantic-schema-gather-to-core-perfect
git remote add claims https://git-manager.itsdev.in/proxy/github.com/kaitranntt-evals/pydantic-schema-gather-to-core
for b in d2a5977c c2733622 734c6460 c9d6135f e2125aea; do git fetch claims evalon/pydantic-s-$b; git worktree add --detach ../wt-$b FETCH_HEAD; done
git worktree add --detach ../wt-base a2c935478      # eval base, for controls

# per tree (venv = /opt/venv for the audited branch, /opt/venv-<id> for a claim branch), as in the eval's startup.sh:
uv venv $V --python 3.13; export VIRTUAL_ENV=$V UV_PROJECT_ENVIRONMENT=$V PATH=$V/bin:$HOME/.cargo/bin:$PATH
uv pip install maturin==1.15.0 pytest==9.1.1 pytest-timeout==2.3.1
uv sync --frozen --all-packages --all-extras --group testing-extra
maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
# typing claims only (C5, C8, controls): pyright is in the `linting`/`typechecking` groups, not installed by startup.sh
uv pip install pyright==1.1.411      # the version pinned in uv.lock

# "base walker" control = the pre-change pure-Python module, importable next to any build:
mkdir -p /tmp/basepy && git show a2c935478:pydantic/_internal/_schema_gather.py > /tmp/basepy/base_schema_gather.py
```

Toolchain: Python 3.13.18, rustc 1.99.1, clippy 0.1.99, rustfmt 1.10.0, pyright 1.1.411, uv 0.13.7. Full captured outputs are in `verify/logs/`.

The eval fixtures (archive copies, byte-exact) all pass on the audited branch, so none of them measures the behaviors confirmed below for C1, C2 and C3:

```console
$ cd /home/ubuntu/repos/pydantic && bash -c cp ~/fx/tests/test_eval_*.py tests/ && /opt/venv/bin/pytest tests/test_eval_schema_gather_*.py -q -p no:cacheprovider | tail -4; rm tests/test_eval_*.py
........................................................................ [ 85%]
............                                                             [100%]
Results (0.64s):
        84 passed
exit=0
```

## C1

**Claim:** gathering skips a distinct generator-produced schema whose address matches a cached address of a completed, released schema. Branch: [pydantic-schema-gather-to-core-perfect](https://github.com/kaitranntt-evals/pydantic/tree/pydantic-schema-gather-to-core-perfect).

Source context (`pydantic-core/src/schema_gather.rs`): `GatherCtx.visited: AHashMap<usize, usize>` is keyed by `schema.as_ptr() as usize`; `TraversalStep::Leave` owns the only native reference to a schema that came out of a non-list iterable (`extend_from_iterable`), and nothing removes the key when `Leave` is popped.

Probe: `verify/repro/c1_generator_address_reuse.py`. A `union` with two `chain` choices whose `steps` are independent generators. Part 1 traces the lifetime with a weak reference; part 2 yields 50 fresh plain dicts per branch, records `id()` of each, and compares with the result.

```console
$ cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c1_generator_address_reuse.py
lifetime: first-branch schema still alive when the second generator branch starts: False
A: second-branch schemas allocated at an address of a released first-branch schema: 50/50
A: second-branch definition-refs absent from collected_references (skipped): 50/50
A: skipped == reused-address set: True; refs at fresh addresses collected: True
B: reused addresses: 50/50; outcome for 50 refs to a missing definition: no exception
control (list-held): collected 50 of 50
RESULT: STALE-ADDRESS SKIP REPRODUCED (A=True, B=True)
exit=0
```

Observed, separately:

- *Retained identity (lifetime):* the first-branch schema is already dead when the second generator starts (`still alive ...: False`), and its address is still honoured as "visited" (next point).
- *Generated-branch trigger (traversal):* 50/50 second-branch schemas were allocated at addresses of released first-branch schemas, and exactly those 50 `definition-ref` schemas are absent from `collected_references`; with references to a missing definition no `MissingDefinitionError` is raised at all. The same shapes held in lists collect 50 of 50.

Control, pre-change pure-Python walker (`/tmp/basepy/c1_base.py` is the same script with the import replaced by `from base_schema_gather import ...`):

```console
$ cd /tmp/basepy && /opt/venv/bin/python c1_base.py
lifetime: first-branch schema still alive when the second generator branch starts: False
A: second-branch schemas allocated at an address of a released first-branch schema: 50/50
A: second-branch definition-refs absent from collected_references (skipped): 50/50
A: skipped == reused-address set: True; refs at fresh addresses collected: True
B: reused addresses: 50/50; outcome for 50 refs to a missing definition: no exception
control (list-held): collected 50 of 50
RESULT: STALE-ADDRESS SKIP REPRODUCED (A=True, B=True)
exit=0
```

Impact reasoning: the result is silently wrong (a reference is neither collected nor validated), but only for schemas whose child containers are one-shot iterables that create schemas on the fly. Schemas produced by pydantic's own `GenerateSchema` hold children in lists/dicts that stay alive for the whole call, so the everyday path is not affected. The pre-change Python walker keyed `visited` by `id()` and shows the identical outcome, so this is preserved behavior rather than a regression. Fix options: keep every visited object alive for the duration of the call (e.g. store `Bound` objects next to the address), or remove the key on `Leave` when the traversal held the last reference.

## C2

**Claim:** standard pickling cannot round-trip `MissingDefinitionError` because its declared module is not importable. Branch: [pydantic-schema-gather-to-core-perfect](https://github.com/kaitranntt-evals/pydantic/tree/pydantic-schema-gather-to-core-perfect).

Probe: `verify/repro/c2_pickle_missing_definition_error.py` (raises the exception through `gather_schemas_for_cleaning`, then pickles it with every protocol).

```console
$ cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c2_pickle_missing_definition_error.py
__module__ = pydantic_core._pydantic_core._schema_gather | __qualname__ = MissingDefinitionError
declared module in sys.modules: False
import of declared module: ModuleNotFoundError: No module named 'pydantic_core._pydantic_core._schema_gather'; 'pydantic_core._pydantic_core' is not a package
instance: MissingDefinitionError('missing') args = ('missing',) schema_reference = missing
protocol 0: PicklingError: Can't pickle <class 'pydantic_core._pydantic_core._schema_gather.MissingDefinitionError'>: import of module 'pydantic_core._pydantic_core._schema_gather' failed
protocol 1: PicklingError: Can't pickle <class 'pydantic_core._pydantic_core._schema_gather.MissingDefinitionError'>: import of module 'pydantic_core._pydantic_core._schema_gather' failed
protocol 2: PicklingError: Can't pickle <class 'pydantic_core._pydantic_core._schema_gather.MissingDefinitionError'>: import of module 'pydantic_core._pydantic_core._schema_gather' failed
protocol 3: PicklingError: Can't pickle <class 'pydantic_core._pydantic_core._schema_gather.MissingDefinitionError'>: import of module 'pydantic_core._pydantic_core._schema_gather' failed
protocol 4: PicklingError: Can't pickle <class 'pydantic_core._pydantic_core._schema_gather.MissingDefinitionError'>: import of module 'pydantic_core._pydantic_core._schema_gather' failed
protocol 5: PicklingError: Can't pickle <class 'pydantic_core._pydantic_core._schema_gather.MissingDefinitionError'>: import of module 'pydantic_core._pydantic_core._schema_gather' failed
copy.copy: True ('missing',)
RESULT: PICKLE ROUND TRIP FAILS
exit=0
```

Control, pre-change pure-Python class:

```sh
cd /tmp/basepy && /opt/venv/bin/python - <<'PY'
import pickle
from base_schema_gather import MissingDefinitionError, gather_schemas_for_cleaning
try: gather_schemas_for_cleaning({'type': 'definition-ref', 'schema_ref': 'missing'}, {})
except MissingDefinitionError as e: exc=e
r=pickle.loads(pickle.dumps(exc)); print('base walker:', type(r) is MissingDefinitionError, r.args, r.schema_reference, MissingDefinitionError.__module__)
PY
```

```console
base walker: True ('missing',) missing base_schema_gather
```

Observed: `__module__` is `pydantic_core._pydantic_core._schema_gather`, which is neither in `sys.modules` nor importable (`'pydantic_core._pydantic_core' is not a package`); `pickle.dumps` fails with `PicklingError` on protocols 0-5, so the failure is at dump time, before any restore. `copy.copy` still works. The branch itself documents the cause in `pydantic-core/.mypy-stubtest-allowlist` ("pyo3 submodules are only reachable as attributes, not through a dotted import").

Impact reasoning: a regression against the pre-change class, which round-trips. Reach is limited: the only production consumer, `pydantic/_internal/_generate_schema.py:2868`, catches the exception and converts it, so it normally never leaves the process; it matters when an uncaught instance crosses a process boundary (`multiprocessing`, `concurrent.futures.ProcessPoolExecutor`, pytest-xdist). Fix options: register the submodule in `sys.modules` at init (`sys.modules['pydantic_core._pydantic_core._schema_gather'] = ...`) or declare `module = "pydantic_core._pydantic_core"` and export the class there.

## C3

**Claim:** eager child collection reports a later structural error before `MissingDefinitionError` for an earlier child. Branch: [pydantic-schema-gather-to-core-perfect](https://github.com/kaitranntt-evals/pydantic/tree/pydantic-schema-gather-to-core-perfect).

Source context: `collect_child_schemas` resolves all children of a schema (`child_required` for `lax_schema` then `strict_schema`; `choice.get_item(0)` for every tuple choice) before the first child is entered.

Probe: `verify/repro/c3_eager_child_collection_error_order.py` (both schemas named by the claim, plus neighbours and a control).

```console
$ cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c3_eager_child_collection_error_order.py
lax-or-strict: lax_schema=<missing ref>, strict_schema absent
    -> KeyError: 'strict_schema'
union: choices=[<missing ref>, ()]
    -> IndexError: tuple index out of range
union: choices=[<missing ref>, []] (list-valued child)
    -> MissingDefinitionError('missing')
chain: steps=[<missing ref>, []] (list-valued child)
    -> MissingDefinitionError('missing')
tuple: items_schema=[<missing ref>, 1]
    -> MissingDefinitionError('missing')
json-or-python: json_schema=<missing ref>, python_schema absent
    -> KeyError: 'python_schema'
dict: keys_schema=<missing ref>, values_schema=[]
    -> MissingDefinitionError('missing')
arguments: [{schema: <missing ref>}, {}]
    -> KeyError: 'schema'
control: lax-or-strict with only the missing ref problem
    -> MissingDefinitionError('missing')
RESULT: 4 case(s) reported a later structural/cast error before MissingDefinitionError
exit=0
```

Control, pre-change pure-Python walker with the same script:

```console
$ cd /home/ubuntu/repos/pydantic && env PYTHONPATH=/tmp/basepy /opt/venv/bin/python verify/repro/c3_eager_child_collection_error_order.py base_schema_gather
lax-or-strict: lax_schema=<missing ref>, strict_schema absent
    -> MissingDefinitionError('missing')
union: choices=[<missing ref>, ()]
    -> MissingDefinitionError('missing')
union: choices=[<missing ref>, []] (list-valued child)
    -> MissingDefinitionError('missing')
chain: steps=[<missing ref>, []] (list-valued child)
    -> MissingDefinitionError('missing')
tuple: items_schema=[<missing ref>, 1]
    -> MissingDefinitionError('missing')
json-or-python: json_schema=<missing ref>, python_schema absent
    -> MissingDefinitionError('missing')
dict: keys_schema=<missing ref>, values_schema=[]
    -> MissingDefinitionError('missing')
arguments: [{schema: <missing ref>}, {}]
    -> MissingDefinitionError('missing')
control: lax-or-strict with only the missing ref problem
    -> MissingDefinitionError('missing')
RESULT: 0 case(s) reported a later structural/cast error before MissingDefinitionError
exit=1
```

Observed: both claimed cases hold - `lax-or-strict` without `strict_schema` raises `KeyError: 'strict_schema'`, and `union` with `choices=[<missing ref>, ()]` raises `IndexError: tuple index out of range`; `json-or-python` and `arguments` behave the same way (4 of 8 competing-error cases). The pre-change walker raises `MissingDefinitionError('missing')` in all of them. Cases where the later sibling is a wrong-typed object (rather than an absent key or empty tuple) still report `MissingDefinitionError`, because this branch defers the dict cast to `enter`.

Impact reasoning: only malformed schemas are affected, and only which exception wins; `GenerateSchema` converts `MissingDefinitionError` into its own error, so a hand-built or plugin-built schema with two defects now surfaces `KeyError`/`IndexError` from native code instead. The task statement asks to preserve `MissingDefinitionError` semantics. Fix: collect children lazily per child (push a "resolve key" step instead of the resolved child), or add the two shapes above to the test-suite and accept the new order explicitly.

## C4

**Claim:** a new temporary schema wrapper is treated as already visited when a later generating branch reuses the address of a completed wrapper. Branch: [evalon/pydantic-s-d2a5977c](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-d2a5977c).

Source context (`pydantic-core/src/schema_gather.rs` on that branch): `native_visited: AHashMap<usize, (usize, Option<usize>)>` is keyed by `schema.as_ptr() as usize`; `Work::Finish(id, start)` carries only the address, and the last owning step (`Work::Metadata(schema)`) drops the wrapper; children of iterables are pulled lazily (`Work::Next`).

Probe: `verify/repro/c4_wrapper_address_reuse.py`, run inside the claim worktree with the claim branch's own build.

```console
$ cd /home/ubuntu/repos/wt-d2a5977c && /opt/venv-d2a5977c/bin/python /home/ubuntu/repos/pydantic/verify/repro/c4_wrapper_address_reuse.py
lifetime: completed first-branch wrapper still alive when the second generating branch starts: False
skip: second-branch wrappers at a retained address: 50/50; their definition-refs missing from collected_references: 50/50; same set: True
skip: 50 fresh refs to a missing definition in the second branch -> no exception (reused addresses 50/50)
non-inlinable: single-use references u0..u49 marked non-inlinable (None): 2/50 (second-branch wrappers at a retained address: 50/50)
control (list-held wrappers): non-inlinable 0 of 50
RESULT: REPRODUCED (skip=True, non_inlinable=True)
exit=0
```

Observed, separately:

- *Completed-wrapper identity (lifetime):* the completed first-branch wrapper is dead when the second generating branch starts, while its address still matches in the cache.
- *Independent-branch trigger:* 50/50 second-branch wrappers reuse a retained address and all 50 of their `definition-ref` children are missing from `collected_references`; 50 references to a missing definition raise nothing; and 2 of 50 single-use references are wrongly marked non-inlinable (`None`) when unrelated `int` wrappers land on the address of a released `list` wrapper. List-held wrappers: 0 of 50 non-inlinable.

Control, pre-change pure-Python walker (same script, import replaced):

```console
$ cd /tmp/basepy && /opt/venv/bin/python c4_base.py
lifetime: completed first-branch wrapper still alive when the second generating branch starts: False
skip: second-branch wrappers at a retained address: 50/50; their definition-refs missing from collected_references: 50/50; same set: True
skip: 50 fresh refs to a missing definition in the second branch -> no exception (reused addresses 50/50)
non-inlinable: single-use references u0..u49 marked non-inlinable (None): 2/50 (second-branch wrappers at a retained address: 50/50)
control (list-held wrappers): non-inlinable 0 of 50
RESULT: REPRODUCED (skip=True, non_inlinable=True)
exit=0
```

Impact reasoning: same class as C1 - silently wrong gathering result, reachable only with one-shot iterables that build schemas on the fly, never with pydantic-generated schemas; identical to the pre-change walker's `id()`-keyed cache, so not a regression. Fix: keep visited objects alive for the call or drop the key when the wrapper is released.

## C5

**Claim:** the native gathering interface and its Python adapter contain typing incompatibilities detected by the repository's Pyright commands. Branch: [evalon/pydantic-s-c2733622](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-c2733622).

Commands: the pre-commit `typecheck` hook is `uv run pyright pydantic`; `make -C pydantic-core pyright` is `uv run pyright` in `pydantic-core`. Both were run with the claim branch's venv (`--pythonpath` instead of `uv run`, so that `uv` does not re-sync the environment). Replay: `verify/repro/c5_pyright_gather_interface.sh`.

```console
$ cd /home/ubuntu/repos/wt-c2733622 && /opt/venv-c2733622/bin/pyright --pythonpath /opt/venv-c2733622/bin/python pydantic
/home/ubuntu/repos/wt-c2733622/pydantic/_internal/_schema_gather.py
  /home/ubuntu/repos/wt-c2733622/pydantic/_internal/_schema_gather.py:58:12 - error: Type "dict[str, Any]" is not assignable to return type "GatherResult"
    "dict[str, Any]" is not assignable to "GatherResult" (reportReturnType)
1 error, 0 warnings, 0 informations

exit=1
$ cd /home/ubuntu/repos/wt-c2733622/pydantic-core && /opt/venv-c2733622/bin/pyright --pythonpath /opt/venv-c2733622/bin/python   # = make -C pydantic-core pyright
/home/ubuntu/repos/wt-c2733622/pydantic-core/python/pydantic_core/__init__.py
  /home/ubuntu/repos/wt-c2733622/pydantic-core/python/pydantic_core/__init__.py:45:5 - warning: "UNSET" is specified in __all__ but is not present in module (reportUnsupportedDunderAll)
0 errors, 1 warning, 0 informations

exit=0
```

Control, audited branch with the same commands:

```console
$ cd /home/ubuntu/repos/pydantic && /opt/venv/bin/pyright --pythonpath /opt/venv/bin/python pydantic
0 errors, 0 warnings, 0 informations

exit=0
$ cd /home/ubuntu/repos/pydantic/pydantic-core && /opt/venv/bin/pyright --pythonpath /opt/venv/bin/python   # = make -C pydantic-core pyright
/home/ubuntu/repos/pydantic/pydantic-core/python/pydantic_core/__init__.py
  /home/ubuntu/repos/pydantic/pydantic-core/python/pydantic_core/__init__.py:45:5 - warning: "UNSET" is specified in __all__ but is not present in module (reportUnsupportedDunderAll)
0 errors, 1 warning, 0 informations

exit=0
```

Observed: one error, in `pydantic/_internal/_schema_gather.py:58` - the stub declares `gather_schemas_for_cleaning(...) -> dict[str, Any]` and the adapter returns it as `GatherResult` (`reportReturnType`); exit status 1. The `pydantic-core` run reports 0 errors and the same single `UNSET` warning as the control, so nothing there is attributable to the gathering stubs (no decorator-placement or `TzInfo`/`@final` diagnostic).

Impact reasoning: the repository's typecheck hook (`make typecheck`, CI lint) fails on this branch; runtime behavior is unaffected. Fix: type the stub's return as the `GatherResult` shape (or a `TypedDict` in the stub), or `cast`/build the `GatherResult` in the adapter.

## C6

**Claim:** `pydantic_core.__all__` exposes gathering symbols that the explicit member list of `docs/api/pydantic_core.md` omits. Branch: [evalon/pydantic-s-734c6460](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-734c6460).

Probe: `verify/repro/c6_public_exports_vs_docs.py` (imports the built `pydantic_core`, parses the `members:` list of the docs page).

```console
$ cd /home/ubuntu/repos/wt-734c6460 && /opt/venv-734c6460/bin/python /home/ubuntu/repos/pydantic/verify/repro/c6_public_exports_vs_docs.py
pydantic_core file: /home/ubuntu/repos/wt-734c6460/pydantic-core/python/pydantic_core/__init__.py
gathering symbols in pydantic_core.__all__: ['MissingDefinitionError', 'GatherResult', 'gather_schemas_for_cleaning']
  MissingDefinitionError: importable=True module=pydantic_core._pydantic_core in docs member list=False
  GatherResult: importable=True module=pydantic_core in docs member list=False
  gather_schemas_for_cleaning: importable=True module=pydantic_core._pydantic_core in docs member list=False
all __all__ entries absent from the docs member list: ['CoreConfig', 'CoreSchema', 'CoreSchemaType', 'GatherResult', 'MissingDefinitionError', 'PydanticUndefined', 'PydanticUndefinedType', 'UNSET', 'gather_schemas_for_cleaning']
docs members absent from __all__: ['ErrorTypeInfo', 'MultiHostHost', 'list_all_errors']
RESULT: 3 public gathering symbol(s) undocumented: ['MissingDefinitionError', 'GatherResult', 'gather_schemas_for_cleaning']
exit=0
```

Control, audited branch:

```console
$ cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python /home/ubuntu/repos/pydantic/verify/repro/c6_public_exports_vs_docs.py
pydantic_core file: /home/ubuntu/repos/pydantic/pydantic-core/python/pydantic_core/__init__.py
gathering symbols in pydantic_core.__all__: []
all __all__ entries absent from the docs member list: ['CoreConfig', 'CoreSchema', 'CoreSchemaType', 'PydanticUndefined', 'PydanticUndefinedType', 'UNSET']
docs members absent from __all__: ['ErrorTypeInfo', 'MultiHostHost', 'list_all_errors']
RESULT: no undocumented public gathering symbol
exit=1
```

```console
$ cd /home/ubuntu/repos/wt-734c6460 && git diff --stat a2c935478 HEAD -- docs | wc -l
0
$ grep -rn "gather_schemas_for_cleaning\|MissingDefinitionError\|GatherResult" docs | head
$
```

Observed, separately:

- *Public exposure:* `MissingDefinitionError`, `GatherResult` and `gather_schemas_for_cleaning` are in `pydantic_core.__all__` and importable from the package root.
- *Documentation omission:* none of the three is in the docs member list, and the branch does not touch `docs/` at all.

Note: six other `__all__` names (`CoreConfig`, `CoreSchema`, `CoreSchemaType`, `PydanticUndefined`, `PydanticUndefinedType`, `UNSET`) were already absent from that list before the change, so the list is not a strict mirror of `__all__`; the three gathering names are the ones this branch adds.

Impact reasoning: an internal operation becomes part of the supported public surface of `pydantic_core` (star-import, API stability expectations) without documentation. Decision for the maintainer: make them private (as the audited branch does, via `_pydantic_core._schema_gather`) or document them.

## C7

**Claim:** preparing later sibling schemas eagerly changes the first reported failure from an earlier missing definition to a later structural or type error. Branch: [evalon/pydantic-s-c9d6135f](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-c9d6135f).

Source context: `schema_children` builds `SmallVec<[Bound<PyDict>; 4]>` for all children up front, with `get_as_req` for required keys and `cast_into::<PyDict>()` for every child.

Probe: `verify/repro/c7_eager_sibling_preparation_error_order.py`, run inside the claim worktree with its own build.

```console
$ cd /home/ubuntu/repos/wt-c9d6135f && /opt/venv-c9d6135f/bin/python /home/ubuntu/repos/pydantic/verify/repro/c7_eager_sibling_preparation_error_order.py
lax-or-strict: lax_schema=<missing ref>, strict_schema absent
    -> KeyError: 'strict_schema'
union: choices=[<missing ref>, ()]
    -> IndexError: tuple index out of range
union: choices=[<missing ref>, []] (list-valued child)
    -> TypeError: 'list' object is not an instance of 'dict'
chain: steps=[<missing ref>, []] (list-valued child)
    -> TypeError: 'list' object is not an instance of 'dict'
tuple: items_schema=[<missing ref>, 1]
    -> TypeError: 'int' object is not an instance of 'dict'
json-or-python: json_schema=<missing ref>, python_schema absent
    -> KeyError: 'python_schema'
dict: keys_schema=<missing ref>, values_schema=[]
    -> TypeError: 'list' object is not an instance of 'dict'
arguments: [{schema: <missing ref>}, {}]
    -> KeyError: 'schema'
control: lax-or-strict with only the missing ref problem
    -> MissingDefinitionError('missing')
RESULT: 8 case(s) reported a later structural/cast error before MissingDefinitionError
exit=0
```

Control, pre-change pure-Python walker with the same script:

```console
$ cd /home/ubuntu/repos/wt-c9d6135f && env PYTHONPATH=/tmp/basepy /opt/venv-c9d6135f/bin/python /home/ubuntu/repos/pydantic/verify/repro/c7_eager_sibling_preparation_error_order.py base_schema_gather
lax-or-strict: lax_schema=<missing ref>, strict_schema absent
    -> MissingDefinitionError('missing')
union: choices=[<missing ref>, ()]
    -> MissingDefinitionError('missing')
union: choices=[<missing ref>, []] (list-valued child)
    -> MissingDefinitionError('missing')
chain: steps=[<missing ref>, []] (list-valued child)
    -> MissingDefinitionError('missing')
tuple: items_schema=[<missing ref>, 1]
    -> MissingDefinitionError('missing')
json-or-python: json_schema=<missing ref>, python_schema absent
    -> MissingDefinitionError('missing')
dict: keys_schema=<missing ref>, values_schema=[]
    -> MissingDefinitionError('missing')
arguments: [{schema: <missing ref>}, {}]
    -> MissingDefinitionError('missing')
control: lax-or-strict with only the missing ref problem
    -> MissingDefinitionError('missing')
RESULT: 0 case(s) reported a later structural/cast error before MissingDefinitionError
exit=1
```

Observed: all 8 competing-error cases report the later sibling's error first, including the two named by the claim - missing `strict_schema` gives `KeyError: 'strict_schema'`, and an invalid list-valued child gives `TypeError: 'list' object is not an instance of 'dict'`. The pre-change walker gives `MissingDefinitionError('missing')` in every case; the control with only the missing reference still raises `MissingDefinitionError`.

Impact reasoning: malformed schemas only; the exception type changes from the documented `MissingDefinitionError` (which `GenerateSchema` handles) to `KeyError`/`TypeError`/`IndexError`. Fix: resolve and cast each child when it is visited rather than when its parent is entered.

## C8

**Claim:** the thin Python adapter retains unused traversal declarations or traversal-specific file-wide type-check suppressions. Branch: [evalon/pydantic-s-e2125aea](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-e2125aea).

Probe: `verify/repro/c8_adapter_leftovers.py` (AST name-usage analysis plus `git grep` for importers; then pyright on the file as delivered and with only the `# pyright:` line removed, file restored afterwards).

```console
$ cd /home/ubuntu/repos/wt-e2125aea && /opt/venv-e2125aea/bin/python /home/ubuntu/repos/pydantic/verify/repro/c8_adapter_leftovers.py
module-level imports/assignments: {'annotations': 'import (line 2)', 'Mapping': 'import (line 4)', 'TypeAlias': 'import (line 5)', 'TypedDict': 'import (line 5)', '_gather_schemas_for_cleaning': 'import (line 7)', 'ComputedField': 'import (line 8)', 'CoreSchema': 'import (line 8)', 'DefinitionReferenceSchema': 'import (line 8)', 'SerSchema': 'import (line 8)', 'AllSchemas': 'assignment (line 15)'}
  ComputedField: import (line 8); referenced by executable code in the adapter: False; appears only inside a string alias: True; importers elsewhere: []
  SerSchema: import (line 8); referenced by executable code in the adapter: False; appears only inside a string alias: True; importers elsewhere: []
  AllSchemas: assignment (line 15); referenced by executable code in the adapter: False; appears only inside a string alias: False; importers elsewhere: []
unused traversal-only declarations/imports: ['ComputedField', 'SerSchema', 'AllSchemas']
file-wide directive: # pyright: reportTypedDictNotRequiredAccess=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportAttributeAccessIssue=false
pyright, file as delivered:       (0, ['0 errors, 0 warnings, 0 informations'])
pyright, file-wide directive removed: (0, ['0 errors, 0 warnings, 0 informations'])
RESULT: unused declarations: True | file-wide suppression no longer needed: True
exit=0
```

Whole-package check with the directive removed (first line deleted with `sed -i '1d'`, then `git checkout` of the file):

```console
$ cd /home/ubuntu/repos/wt-e2125aea && sed -i '1d' pydantic/_internal/_schema_gather.py && /opt/venv-e2125aea/bin/pyright --pythonpath /opt/venv-e2125aea/bin/python pydantic
0 errors, 0 warnings, 0 informations
$ git checkout pydantic/_internal/_schema_gather.py && /opt/venv-e2125aea/bin/pyright --pythonpath /opt/venv-e2125aea/bin/python pydantic
0 errors, 0 warnings, 0 informations
$ grep -n "AllSchemas\|SerSchema\|ComputedField" pydantic/_internal/_schema_gather.py
9:    ComputedField,
12:    SerSchema,
15:AllSchemas: TypeAlias = 'CoreSchema | SerSchema | ComputedField'
$ /opt/venv-e2125aea/bin/ruff check --select F401,F841 pydantic/_internal/_schema_gather.py
All checks passed!
```

Control, audited branch (no such declarations, no directive):

```console
$ cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python /home/ubuntu/repos/pydantic/verify/repro/c8_adapter_leftovers.py
module-level imports/assignments: {'annotations': 'import (line 1)', 'TypedDict': 'import (line 3)', '_schema_gather': 'import (line 5)', 'CoreSchema': 'import (line 6)', 'DefinitionReferenceSchema': 'import (line 6)', '__all__': 'assignment (line 8)', 'MissingDefinitionError': 'assignment (line 14)'}
unused traversal-only declarations/imports: []
file-wide directive: None
RESULT: unused declarations: False | file-wide suppression no longer needed: False
exit=1
```

Observed, separately:

- *Unused declarations:* `AllSchemas` is assigned and never referenced anywhere in the repository; `SerSchema` and `ComputedField` are imported only to appear inside that alias string. Ruff does not flag them (a module-level alias counts as a use), so lint stays green.
- *Traversal suppressions:* the file-wide `# pyright: reportTypedDictNotRequiredAccess=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportAttributeAccessIssue=false` line suppresses nothing in the remaining code: pyright reports 0 errors with and without it (the one needed suppression is the inline `# pyright: ignore[reportReturnType]`).

Impact reasoning: no runtime effect; dead declarations and a blanket suppression that would hide future typing errors in four rule categories in this file. Fix: delete the alias, the two imports, the `TypeAlias` import and the first line.

## C9

**Claim:** the delivered sources fail the repository's Python or Rust lint and formatting requirements. Branch: [pydantic-schema-gather-to-core-perfect](https://github.com/kaitranntt-evals/pydantic/tree/pydantic-schema-gather-to-core-perfect).

```sh
cd /home/ubuntu/repos/pydantic
export PATH="/opt/venv/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH" VIRTUAL_ENV=/opt/venv UV_PROJECT_ENVIRONMENT=/opt/venv UV_FROZEN=1
make lint-python
make -C pydantic-core lint-rust
```

*Python lint* (`verify/logs/c9_lint_python.log`):

```console
uv 0.13.7 (x86_64-unknown-linux-gnu)
uv run ruff check pydantic tests docs/plugins release pydantic-core/python pydantic-core/tests pydantic-core/wasm-preview/run_tests.py
Uninstalled 1 package in 0.70ms
Installed 1 package in 1ms
All checks passed!
uv run ruff format --check pydantic tests docs/plugins release pydantic-core/python pydantic-core/tests pydantic-core/wasm-preview/run_tests.py
354 files already formatted
make lint-python exit=0
```

*Rust lint* (`verify/logs/c9_lint_rust.log`, diagnostics and status lines):

```console
cargo fmt --version
rustfmt 1.10.0-stable (58cf8f9c35 2026-10-13)
cargo fmt --all -- --check
cargo clippy --version
clippy 0.1.99 (58cf8f9c35 2026-10-13)
cargo clippy --tests -- -D warnings
error: use of irregular braces for `write!` macro
  --> src/definitions.rs:92:9
error: use of irregular braces for `write!` macro
  --> src/definitions.rs:95:13
error: use of irregular braces for `write!` macro
  --> src/definitions.rs:98:9
error: could not compile `pydantic-core` (lib test) due to 3 previous errors
warning: build failed, waiting for other jobs to finish...
error: could not compile `pydantic-core` (lib) due to 3 previous errors
make: *** [Makefile:86: lint-rust] Error 101
make -C pydantic-core lint-rust exit=2
```

Attribution checks:

```console
$ git diff --stat a2c935478 HEAD -- pydantic-core/src/definitions.rs | wc -l
0
$ (cd ../wt-base && make -C pydantic-core lint-rust)        # eval base a2c935478, same toolchain
error: use of irregular braces for `write!` macro
  --> src/definitions.rs:92:9
error: use of irregular braces for `write!` macro
  --> src/definitions.rs:95:13
error: use of irregular braces for `write!` macro
  --> src/definitions.rs:98:9
error: could not compile `pydantic-core` (lib test) due to 3 previous errors
error: could not compile `pydantic-core` (lib) due to 3 previous errors
BASE a2c935478 make -C pydantic-core lint-rust exit=2
$ (cd pydantic-core && cargo clippy --tests -- -D warnings -A clippy::nonstandard_macro_braces)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 7.88s
clippy with nonstandard_macro_braces allowed exit=0
```

Observed, separately:

- *Python lint:* `ruff check` and `ruff format --check` pass, exit 0. This part does not hold.
- *Rust lint:* `cargo fmt --all -- --check` passes; `cargo clippy --tests -- -D warnings` fails (make exit 2) with three `clippy::nonstandard_macro_braces` errors, all in `pydantic-core/src/definitions.rs:92,95,98` (`write![f, ...]`). That file is not touched by the solution, the eval base fails identically with this toolchain (clippy 0.1.99), and with that one lint allowed clippy is clean - there is no diagnostic in `schema_gather.rs` or `lib.rs`.

Impact reasoning: the task's own lint guideline (`make -C pydantic-core lint-rust`) exits non-zero on the delivered tree, with source diagnostics, so the claim's confirm condition is met for the Rust part; but the cause is pre-existing code meeting a newer clippy, not code the solution wrote. Anyone gating on this command sees red before and after the change. Fix: three one-token edits in `definitions.rs` (`write!(f, ...)`), as [evalon/pydantic-s-e2125aea](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-e2125aea) did, or pin the toolchain.

## C10

**Claim:** the delivered solution fails package-wide Python tests or Rust unit tests. Branch: [pydantic-schema-gather-to-core-perfect](https://github.com/kaitranntt-evals/pydantic/tree/pydantic-schema-gather-to-core-perfect).

```sh
cd /home/ubuntu/repos/pydantic
export PATH="/opt/venv/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH" VIRTUAL_ENV=/opt/venv UV_PROJECT_ENVIRONMENT=/opt/venv UV_FROZEN=1
CONTEXT=eval make test NUM_THREADS=1
cd pydantic-core && cargo test
```

*Package-wide Python tests* (`verify/logs/c10_make_test.log`):

```console
uv 0.13.7 (x86_64-unknown-linux-gnu)
uv run coverage run -m pytest --durations=10 --parallel-threads 1
============================= test session starts ==============================
```
```console
Results (66.22s):
     12431 passed
       472 skipped
        36 xfailed
CONTEXT=eval make test NUM_THREADS=1 exit=0
```

*Rust unit tests*, bare `cargo test` (`verify/logs/c10_cargo_test.log`):

```console
     Running unittests src/lib.rs (target/debug/deps/_pydantic_core-f2e1cf6c33a04555)
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
     Running tests/test.rs (target/debug/deps/test-413e3b7290da75fd)
/home/ubuntu/repos/pydantic/pydantic-core/target/debug/deps/test-413e3b7290da75fd: error while loading shared libraries: libpython3.13.so.1.0: cannot open shared object file: No such file or directory
error: test failed, to rerun pass `--test test`
cargo test exit=127
```

The second test binary did not start: the dynamic loader cannot find `libpython3.13.so.1.0` of the uv-managed interpreter. The eval base fails the same way (`verify/logs/c10_cargo_test_base.log`):

```console
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
/home/ubuntu/repos/wt-base/pydantic-core/target/debug/deps/test-413e3b7290da75fd: error while loading shared libraries: libpython3.13.so.1.0: cannot open shared object file: No such file or directory
error: test failed, to rerun pass `--test test`
BASE cargo test exit=127
```

With the interpreter's library directory on the loader path (`verify/logs/c10_cargo_test_ldpath.log`):

```sh
LIBDIR=$(/opt/venv/bin/python -c "import sysconfig;print(sysconfig.get_config_var('LIBDIR'))")   # /home/ubuntu/.local/share/uv/python/cpython-3.13.18-linux-x86_64-gnu/lib
LD_LIBRARY_PATH=$LIBDIR cargo test
```

```console
     Running unittests src/lib.rs (target/debug/deps/_pydantic_core-f2e1cf6c33a04555)
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
     Running tests/test.rs (target/debug/deps/test-413e3b7290da75fd)
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.03s
   Doc-tests _pydantic_core
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
cargo test exit=0
```

Observed, separately:

- *Package-wide Python tests:* 12431 passed, 472 skipped, 36 xfailed, exit 0 (includes the solution's `tests/test_schema_gather.py`).
- *Rust unit tests:* every test that runs passes (1 unit test, 3 integration tests, 0 doc-tests), exit 0 once `libpython` can be loaded. The non-zero status of the bare command is a loader error before any test executes, identical on the eval base, so it is not a failing test of the solution.
