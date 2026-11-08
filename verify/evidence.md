## Evidence — run `v-a7b6ca56`

Audited branch: `pydantic-schema-gather-to-core-perfect` (commit `585c9944900a`, parent `a2c935478`), checked out as `verify/pydantic-schema-gather-to-core-v-a7b6ca56`.
Environment: `/opt/venv` (CPython 3.13.18) built with `uv venv --python 3.13`, `uv pip install maturin==1.15.0 pytest==9.1.1 pytest-timeout==2.3.1`, `uv sync --frozen --all-packages --all-extras --group testing-extra`, then `maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen`. Claim-target branches were checked out into separate `jj` workspaces (`/home/ubuntu/repos/pydantic-c3`, `/home/ubuntu/repos/pydantic-c4`) with their own venvs (`/opt/venv-c3` py3.13, `/opt/venv-c4-310` py3.10.12, `/opt/venv-c4-311` py3.11) and their own `maturin develop` build.

`verify/repro/reference_schema_gather.py` is a byte-for-byte copy of `pydantic/_internal/_schema_gather.py` at `a2c935478` (the pre-change pure-Python traversal), used as the behavioural oracle by the probes (`git show a2c935478:pydantic/_internal/_schema_gather.py > verify/repro/reference_schema_gather.py`).

Baseline: the eval fixtures all pass on the audited branch.

```console
$ cp ~/attachments/.../eval_tests/tests/test_eval_*.py tests/ && /opt/venv/bin/pytest tests/test_eval_schema_gather_*.py -q -p no:cacheprovider
Results (0.59s):
        75 passed
```

## C1

Claim: the native gather exhausts a child generator before processing its yielded schemas, changing collected references / deferred discriminators when the generator and child metadata callbacks share mutable state.

Code under audit (`pydantic-core/src/schema_gather.rs`): `extend_from_iterable` drains any non-list/non-tuple iterable into a `SmallVec` (`for item in iterable.try_iter()? { children.push(item?); }`) inside `collect_child_schemas`, and `GatherCtx::enter` only pushes the collected children onto the work stack afterwards. The reference Python did `for s in schema['items_schema']: traverse_schema(s, context)` (child fully traversed before the next item is requested).

Probe: `verify/repro/c1_c2_iterable_interleaving_probe.py` — a `tuple` schema whose `items_schema` generator yields child 1 (`definition-ref` → `first`, metadata is a `dict` subclass whose `__contains__` increments a shared counter and reports the discriminator key) and then a child 2 whose `schema_ref` and deferral depend on whether child 1's metadata callback already ran.

```console
$ cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c1_c2_iterable_interleaving_probe.py
--- C1 generator / native (branch under audit)
  event: iter: yield child1(first)
  event: iter: yield child2(before_callback, deferred=False)
  event: iter: exhausted
  event: metadata.__contains__(child1)
  event: metadata.__contains__(child2)
  collected_references keys: ['first', 'before_callback']
  deferred_discriminator_schemas: ['first']
--- C1 generator / reference Python implementation (a2c935478)
  event: iter: yield child1(first)
  event: metadata.__contains__(child1)
  event: iter: yield child2(after_callback, deferred=True)
  event: metadata.__contains__(child2)
  event: iter: exhausted
  collected_references keys: ['first', 'after_callback']
  deferred_discriminator_schemas: ['first', 'after_callback']
  => C1 generator: results DIFFER between native and reference
...
EXIT=1
```

Observed: the generator is exhausted (`iter: exhausted`) before any child metadata callback runs; both `collected_references` keys (`before_callback` vs `after_callback`) and `deferred_discriminator_schemas` (1 vs 2 entries) differ from the child-by-child reference. The eval fixtures (`test_iterables`, `test_sequence_and_metadata_protocol`) only use stateless generators/iterators, so they stay green (75 passed above).

Impact reasoning: triggering this requires a core schema whose child container is a lazy iterable with side-effecting `__contains__` metadata — nothing pydantic's own `GenerateSchema` produces (it emits lists/dicts, for which `extend_from_iterable` takes the materialised fast path and no ordering question arises). The difference is real but confined to hand-built, deliberately stateful schemas.

## C2

Claim: the native gather collects every item from a stateful child iterable (not only generators) before traversing its children, changing references / deferred metadata that depend on callbacks from earlier children.

Same code path as C1 (`extend_from_iterable` → `try_iter()` loop drains any iterable). Probe: second half of `verify/repro/c1_c2_iterable_interleaving_probe.py`, using `StatefulIterable` (a class with `__iter__`/`__next__`, i.e. not a generator object) whose second item depends on whether the first child's metadata callback ran.

```console
$ cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c1_c2_iterable_interleaving_probe.py
...
--- C2 StatefulIterable / native (branch under audit)
  event: iter: yield child1(first)
  event: iter: yield child2(before_callback, deferred=False)
  event: iter: exhausted
  event: metadata.__contains__(child1)
  event: metadata.__contains__(child2)
  collected_references keys: ['first', 'before_callback']
  deferred_discriminator_schemas: ['first']
--- C2 StatefulIterable / reference Python implementation (a2c935478)
  event: iter: yield child1(first)
  event: metadata.__contains__(child1)
  event: iter: yield child2(after_callback, deferred=True)
  event: metadata.__contains__(child2)
  event: iter: exhausted
  collected_references keys: ['first', 'after_callback']
  deferred_discriminator_schemas: ['first', 'after_callback']
  => C2 StatefulIterable: results DIFFER between native and reference
EXIT=1
```

Observed: all items are collected (`iter: exhausted`) before the first child is traversed; collected references and deferred-discriminator list differ from child-by-child processing. Fixtures `tests/test_eval_schema_gather_traversal.py` and `tests/test_eval_schema_gather_references.py` pass on the audited branch (75 passed, see baseline), so they do not detect this.

Impact reasoning: same as C1 — only reachable with hand-built lazy, side-effecting child iterables; ordinary `list`/`tuple`/`dict` children are unaffected.

## C3

Target branch: `evalon/pydantic-s-03297959` from `kaitranntt-evals/pydantic-schema-gather-to-core` (commit `fea903de72ee`), checked out at `/home/ubuntu/repos/pydantic-c3`, built into `/opt/venv-c3` (py3.13).

```console
$ cd /home/ubuntu/repos/pydantic && git remote add evalrepo https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core && git fetch evalrepo evalon/pydantic-s-03297959 evalon/pydantic-s-44e1e127
 * [new branch]          evalon/pydantic-s-03297959 -> evalrepo/evalon/pydantic-s-03297959
 * [new branch]          evalon/pydantic-s-44e1e127 -> evalrepo/evalon/pydantic-s-44e1e127
$ jj workspace add ../pydantic-c3 -r evalon/pydantic-s-03297959@evalrepo
$ cd /home/ubuntu/repos/pydantic-c3 && /opt/venv-c3/bin/maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
🛠 Installed pydantic_core-2.48.0
$ /opt/venv-c3/bin/python -c "import pydantic_core._pydantic_core as m; print([n for n in dir(m) if 'gather' in n.lower()])"
['_gather_schemas']
```

Code on that branch (`pydantic-core/src/schema_gather.rs`, `GatherContext::traverse`): for `"dataclass-args" | "named-tuple"` it calls `push_children(fields)` first and `push_children(computed_fields)` second (children are pushed in reverse for the LIFO stack, so visit order is still computed_fields → fields), but `push_children` fully iterates (`children.try_iter()`) each iterable at push time — i.e. `fields` is consumed before `computed_fields`. The task-specified / reference order (`a2c935478`) is `for s in schema['computed_fields']: ...` then `for s in schema['fields']: ...`.

Probe: `verify/repro/c3_dataclass_args_order_probe.py` — a `dataclass-args` schema whose `computed_fields` generator sets a flag when iterated and whose `fields` generator yields a `definition-ref` to `fields_after_computed` if the flag is set, else `fields_before_computed`; child visits are recorded through metadata `__contains__`.

```console
$ cd /home/ubuntu/repos/pydantic-c3 && /opt/venv-c3/bin/python /home/ubuntu/repos/pydantic/verify/repro/c3_dataclass_args_order_probe.py
--- native (branch under test)
  event: consume: fields iterated -> selects fields_before_computed
  event: consume: computed_fields iterated
  event: visit: computed
  event: visit: fields_before_computed
  collected_references keys: ['computed', 'fields_before_computed']
--- reference Python implementation (a2c935478)
  event: consume: computed_fields iterated
  event: visit: computed
  event: consume: fields iterated -> selects fields_after_computed
  event: visit: fields_after_computed
  collected_references keys: ['computed', 'fields_after_computed']
=> selected references DIFFER between native and reference
EXIT=1
```

Control — the same probe on the audited branch (`pydantic-schema-gather-to-core-perfect`, which consumes `computed_fields` before `fields`) matches the reference:

```console
$ cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c3_dataclass_args_order_probe.py
--- native (branch under test)
  event: consume: computed_fields iterated
  event: consume: fields iterated -> selects fields_after_computed
  event: visit: computed
  event: visit: fields_after_computed
  collected_references keys: ['computed', 'fields_after_computed']
--- reference Python implementation (a2c935478)
  ...
  collected_references keys: ['computed', 'fields_after_computed']
=> selected references IDENTICAL between native and reference
EXIT=0
```

Observed on the target branch: group consumption order is `fields` → `computed_fields` (reverse of the task-specified traversal order), while the child-visit order is still `computed` → field; the consumption order causes a different reference (`fields_before_computed` instead of `fields_after_computed`) to be collected.

Eval fixtures on that branch (incidental, for context — not part of the claim): `/opt/venv-c3/bin/python -m pytest tests/test_eval_schema_gather_*.py -q` → `1 failed, 74 passed`; the failure is `test_mapping_values_protocol`: `AssertionError: ReversedValuesDict values() bypassed — assert ['a', 'b'] == ['b', 'a']` (the branch casts `fields` to `PyDict` and iterates `.values()` natively). `test_all_schema_kinds` (which uses list-backed `dataclass-args`) passes, so the fixtures do not observe the consumption order.

Impact reasoning: visit order (and therefore results) is correct for `list`-backed `computed_fields`/`fields`, which is all `GenerateSchema` produces; only a stateful lazy `fields` iterable whose output depends on `computed_fields` having been iterated observes the difference.

## C4

Target branch: `evalon/pydantic-s-44e1e127` from `kaitranntt-evals/pydantic-schema-gather-to-core` (commit `b51f06acda18`), checked out at `/home/ubuntu/repos/pydantic-c4`. `pyproject.toml` on that branch: `requires-python = '>=3.10'`, so 3.10 and 3.11 are supported versions.

The delivered tests (`tests/test_internal.py`) import `TypedDict` from `typing` (line 10: `from typing import Annotated, Any, Literal, NamedTuple, TypedDict`) and define `class _GatherTD(TypedDict)` (line 550), which `test_gather_schemas_for_cleaning_matches_reference_implementation` feeds to `GenerateSchema(ConfigWrapper(None)).generate_schema(...)` (parametrised id `typed-dict`). `pydantic/_internal/_generate_schema.py:129` has `_SUPPORTS_TYPEDDICT = sys.version_info >= (3, 12)` and `_typed_dict_schema` raises `PydanticUserError` for `typing.TypedDict` below 3.12.

Environments (same lockfile / configuration as the solution; `uv sync --frozen --all-packages --all-extras --group testing-extra` then `maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen`):

```console
$ /opt/venv-c4-310/bin/python -c "import sys, pydantic_core, pydantic; print(sys.version, pydantic_core.__file__, pydantic.__file__)"
3.10.12 (main, Aug 31 2026, 10:18:17) [GCC 11.4.0] /home/ubuntu/repos/pydantic-c4/pydantic-core/python/pydantic_core/__init__.py /home/ubuntu/repos/pydantic-c4/pydantic/__init__.py
$ /opt/venv-c4-311/bin/maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen   # Python 3.11 venv, same branch
🛠 Installed pydantic_core-2.48.0
```

Python 3.10:

```console
$ cd /home/ubuntu/repos/pydantic-c4 && /opt/venv-c4-310/bin/python -m pytest tests/test_internal.py -q -p no:cacheprovider -k gather
.......F  tests/test_internal.py:564 test_gather_schemas_for_cleaning_matches_reference_implementation[typed-dict]
_ test_gather_schemas_for_cleaning_matches_reference_implementation[typed-dict] _
tests/test_internal.py:596:
            if not _SUPPORTS_TYPEDDICT and type(typed_dict_cls).__module__ == 'typing':
>               raise PydanticUserError(
                    'Please use `typing_extensions.TypedDict` instead of `typing.TypedDict` on Python < 3.12.',
                    code='typed-dict-version',
                )
E               pydantic.errors.PydanticUserError: Please use `typing_extensions.TypedDict` instead of `typing.TypedDict` on Python < 3.12.
E               For further information visit https://errors.pydantic.dev/2.14/u/typed-dict-version
pydantic/_internal/_generate_schema.py:1427: PydanticUserError
Results (0.37s):
         1 failed
        15 passed
        37 deselected
```

Python 3.11:

```console
$ cd /home/ubuntu/repos/pydantic-c4 && /opt/venv-c4-311/bin/python -m pytest tests/test_internal.py -q -p no:cacheprovider -k gather
.......F  tests/test_internal.py:564 test_gather_schemas_for_cleaning_matches_reference_implementation[typed-dict]
tests/test_internal.py:596:
E               pydantic.errors.PydanticUserError: Please use `typing_extensions.TypedDict` instead of `typing.TypedDict` on Python < 3.12.
E               For further information visit https://errors.pydantic.dev/2.14/u/typed-dict-version
pydantic/_internal/_generate_schema.py:1427: PydanticUserError
Results (0.37s):
         1 failed
        15 passed
        37 deselected
```

Single-node re-run on both interpreters gives the same exception:

```console
$ /opt/venv-c4-310/bin/python -m pytest "tests/test_internal.py::test_gather_schemas_for_cleaning_matches_reference_implementation[typed-dict]" -q -p no:cacheprovider
E               pydantic.errors.PydanticUserError: Please use `typing_extensions.TypedDict` instead of `typing.TypedDict` on Python < 3.12.
         1 failed
$ /opt/venv-c4-311/bin/python -m pytest "tests/test_internal.py::test_gather_schemas_for_cleaning_matches_reference_implementation[typed-dict]" -q -p no:cacheprovider
E               pydantic.errors.PydanticUserError: Please use `typing_extensions.TypedDict` instead of `typing.TypedDict` on Python < 3.12.
         1 failed
```

Observed: on both supported interpreters the delivered `typed-dict` case fails in `GenerateSchema.generate_schema` (`tests/test_internal.py:596`) with `PydanticUserError` code `typed-dict-version`, because `_GatherTD` is built from `typing.TypedDict`. The other 15 gather tests pass on both versions, so the failure is specific to the TypedDict construction path.

Impact reasoning: the repo's CI matrix runs tests on every supported Python (`requires-python >= 3.10`), so the delivered test file fails CI on 3.10 and 3.11 regardless of the correctness of the Rust gather. Fix: `from typing_extensions import TypedDict` in `tests/test_internal.py` (as other tests in the repo do), or skip the `typed-dict` case below 3.12.
