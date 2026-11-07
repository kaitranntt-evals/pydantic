## Setup (shared by all sections)

Audited branch: `origin/pydantic-schema-gather-to-core-perfect` (commit `585c99449`, one commit on top of base `a2c935478`), checked out as `verify/pydantic-schema-gather-to-core-v-1f1ec840` in `/home/ubuntu/repos/pydantic`.
Claim-target branches live in a second repository and were fetched into detached worktrees, each with its own venv + native build:

```sh
cd /home/ubuntu/repos/pydantic
git remote add evalrepo https://git-manager.itsdev.in/proxy/github.com/kaitranntt-evals/pydantic-schema-gather-to-core
git fetch evalrepo evalon/pydantic-s-7d6f1afb evalon/pydantic-s-f22cc9d7 evalon/pydantic-s-07335cde
for b in 7d6f1afb f22cc9d7 07335cde; do git worktree add /home/ubuntu/wt-$b evalrepo/evalon/pydantic-s-$b --detach; done
# per checkout (REPO, VENV): uv venv $VENV --python 3.13; uv pip install maturin==1.15.0 pytest==9.1.1 pytest-timeout==2.3.1;
#   uv sync --frozen --all-packages --all-extras --group testing-extra; maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
#   -> /opt/venv (audited), /opt/venv-7d6f1afb, /opt/venv-f22cc9d7, /opt/venv-07335cde
```

All builds ended with `🛠 Installed pydantic_core-2.48.0`; every venv imports `pydantic_core` from its own checkout (`<checkout>/pydantic-core/python/pydantic_core/__init__.py`, `.so` built 23:30).

The "former" behaviour used as the reference in every probe is the base commit's pure-Python implementation, extracted with
`git show a2c935478:pydantic/_internal/_schema_gather.py > /home/ubuntu/former_schema_gather.py` and loaded by each repro's `--former` flag.

Eval fixtures (`tests/test_eval_schema_gather_{traversal,references,errors}.py`, byte-exact from `eval_tests.zip`) were copied into each checkout's `tests/` and run with `python -m pytest <files> -q -p no:cacheprovider`:

```console
=== repos/pydantic (audited branch)      60 passed
=== wt-7d6f1afb (C2 branch)              60 passed
=== wt-f22cc9d7 (C4 branch)              32 failed, 28 passed
=== wt-07335cde (C5 branch)              10 failed, 50 passed
```

## C1

Claim: definition-ref resolution reads the stored contents of a `dict` subclass passed as `definitions`, ignoring its overridden `get`. Audited branch (`pydantic-core/src/schema_gather.rs::GatherCtx::enter` uses `self.definitions.get_item(&schema_ref)` on `Bound<PyDict>`).

```sh
cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c1_c3_definitions_get_override.py --former
```

```console
--- native (branch build)
  absent key (get supplies definition): MissingDefinitionError ('absent',)
  stored key hidden by get->None: RESOLVED -> {'hidden': True}
  overridden get() called with: []
--- former pure-Python (base a2c93547)
  absent key (get supplies definition): RESOLVED -> {'absent': True}
  stored key hidden by get->None: MissingDefinitionError ('hidden',)
  overridden get() called with: ['absent', 'hidden']
```

The subclass `OverridingDefs(dict)` stores only `{'hidden': int_schema(ref='hidden')}`; its `get` returns a schema for `'absent'` and `None` for `'hidden'`. The native build never calls `get` (empty call list), raises for the supplied key and resolves the hidden key — the stored contents. The former Python implementation (`ctx.definitions.get(schema_ref)`) does the opposite in both cases. Verdict: CONFIRMED.

Impact reasoning: only reachable when a caller hands `gather_schemas_for_cleaning` a `dict` subclass with a non-trivial `get`; pydantic's own caller (`_generate_schema.py`) passes a plain `dict`, and `collections.abc.Mapping` instances that are not `dict` subclasses are rejected by the `&Bound<PyDict>` signature anyway. Behavioural difference from the former implementation, not an everyday path.

## C2

Claim (branch `evalon/pydantic-s-7d6f1afb`): a labeled union choice that is a `tuple` subclass has its stored element 0 selected, bypassing an overridden `__getitem__`. Code: `schema_gather.rs` `ItemKind::UnionChoice => match item.cast::<PyTuple>() { Ok(tuple) => tuple.get_item(0)?, ... }` (`PyTuple::get_item` → `PyTuple_GetItem`, no `__getitem__` dispatch).

```sh
cd /home/ubuntu/wt-7d6f1afb && /opt/venv-7d6f1afb/bin/python /home/ubuntu/repos/pydantic/verify/repro/c2_union_choice_tuple_getitem.py --former
```

```console
--- native (branch build)
  collected keys: ['stored'] | identity: {'stored': 'STORED'}
  __getitem__ calls: [0]
--- former pure-Python (base a2c93547)
  collected keys: ['override'] | identity: {'override': 'OVERRIDE'}
  __getitem__ calls: [0, 0]
```

(The first `__getitem__` call in each run is the probe's own `assert choice[0] is OVERRIDE`; the gather itself made zero calls on the branch build and one call in the former implementation.) The branch collects the stored `definition-ref('stored')`; the former `iter_union_choices()` (`choice[0] if isinstance(choice, tuple)`) collects `definition-ref('override')`. Verdict: CONFIRMED.

Control on the audited branch (`Bound<PyAny>::get_item(0)` → `PyObject_GetItem`):

```sh
cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c2_union_choice_tuple_getitem.py
```

```console
--- native (branch build)
  collected keys: ['override'] | identity: {'override': 'OVERRIDE'}
  __getitem__ calls: [0, 0]
```

The eval fixture does not catch this: `test_eval_schema_gather_traversal.py::LabeledChoiceTuple` has no `__getitem__` override, and all 60 fixture tests pass on this branch (`60 passed`; `-k "LabeledChoice or sequence_and_metadata or all_schema_kinds"` → `19 passed, 2 deselected`).

Impact reasoning: core schemas are produced by pydantic's own `core_schema.union_schema`, which stores plain tuples; a tuple subclass with a lying `__getitem__` is contrived. Difference from the former implementation only.

## C3

Same mechanism and same run as C1 (the two claims describe the identical behaviour: supplied-by-`get` definition treated as missing, `None`-hidden stored definition still resolved). Audited branch.

```sh
cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c1_c3_definitions_get_override.py --former
```

```console
--- native (branch build)
  absent key (get supplies definition): MissingDefinitionError ('absent',)
  stored key hidden by get->None: RESOLVED -> {'hidden': True}
  overridden get() called with: []
--- former pure-Python (base a2c93547)
  absent key (get supplies definition): RESOLVED -> {'absent': True}
  stored key hidden by get->None: MissingDefinitionError ('hidden',)
  overridden get() called with: ['absent', 'hidden']
```

Part "supplied definition treated as missing": held (`MissingDefinitionError ('absent',)`). Part "hidden definition remains available": held (`RESOLVED -> {'hidden': True}`). Verdict: CONFIRMED. The fixture `test_eval_schema_gather_references.py` only uses plain dicts and passes (part of the `60 passed` run above), so it does not detect this.

Impact reasoning: as C1 — contrived caller input; pydantic passes a plain `dict`.

## C4

Claim (branch `evalon/pydantic-s-f22cc9d7`): the parent's deferred-discriminator metadata membership is evaluated before its child and serialization traversal. Code: `GatherContext::push_trailing_work` calls `has_deferred_discriminator(schema)` when the schema is *entered* (before children are pushed), and only the *append* is deferred via `Work::Deferred`.

```sh
cd /home/ubuntu/wt-f22cc9d7 && /opt/venv-f22cc9d7/bin/python /home/ubuntu/repos/pydantic/verify/repro/c4_metadata_contains_timing.py --former
```

```console
--- native (branch build)
  [non-dict metadata] __contains__ call order: ['parent', 'child', 'serializer']
  [non-dict metadata] deferred_discriminator_schemas: ['child', 'serializer']
  [dict-subclass metadata] __contains__ call order: ['child', 'serializer']
  [dict-subclass metadata] deferred_discriminator_schemas: ['child', 'serializer']
--- former pure-Python (base a2c93547)
  [non-dict metadata] __contains__ call order: ['child', 'serializer', 'parent']
  [non-dict metadata] deferred_discriminator_schemas: ['child', 'serializer', 'parent']
  [dict-subclass metadata] __contains__ call order: ['child', 'serializer', 'parent']
  [dict-subclass metadata] deferred_discriminator_schemas: ['child', 'serializer', 'parent']
```

Parent `typed_dict_schema` with one child field (`metadata.__contains__` records `'child'`, returns True) and a plain-serializer `serialization` schema (records `'serializer'`, returns True); the parent's metadata `__contains__` returns True only if both have already recorded. On the branch the parent's callback runs first (`['parent', 'child', 'serializer']`) and the parent is omitted; the former implementation runs it last and includes the parent. Verdict: CONFIRMED.

Additional observation (same run, dict-subclass variant): on this branch a `dict`-subclass metadata's `__contains__` is never called at all (`metadata.cast::<PyDict>()` succeeds → `PyDict_Contains`), so the parent is omitted for that reason too. The eval fixture catches this second defect but not the timing one:

```sh
cd /home/ubuntu/wt-f22cc9d7 && /opt/venv-f22cc9d7/bin/python -m pytest tests/test_eval_schema_gather_traversal.py -k test_sequence_and_metadata_protocol tests/test_eval_schema_gather_references.py -q -p no:cacheprovider -p no:pretty -rf
```

```console
>       assert [id(s) for s in result_meta['deferred_discriminator_schemas']] == [id(schema_meta)]
E       assert [] == [127333648141952]
tests/test_eval_schema_gather_traversal.py:390: AssertionError
```

`test_eval_schema_gather_references.py::test_metadata_evaluated_after_children_and_serializers` (plain-dict metadata, checks only output order) **passes** on this branch — the output order is preserved by deferring the append, so the fixture cannot see that `__contains__` ran early. Full fixture run on this branch: `32 failed, 28 passed` (the other failures are `Sequence __iter__ override bypassed`, `ReversedValuesDict values() bypassed`, and `test_missing_definition[...none-mapped]`/surrogate cases — unrelated to C4).

Control on the audited branch:

```sh
cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c4_metadata_contains_timing.py
```

```console
  [non-dict metadata] __contains__ call order: ['child', 'serializer', 'parent']
  [non-dict metadata] deferred_discriminator_schemas: ['child', 'serializer', 'parent']
  [dict-subclass metadata] __contains__ call order: ['child', 'serializer', 'parent']
  [dict-subclass metadata] deferred_discriminator_schemas: ['child', 'serializer', 'parent']
```

Impact reasoning: a schema is silently dropped from `deferred_discriminator_schemas` (so `_generate_schema` would never apply its discriminator) while every output-order check still passes. Pydantic's own `pydantic_internal_union_discriminator` metadata is a plain `dict` entry evaluated at schema-build time, so the trigger requires metadata whose membership is computed lazily — not an everyday input, but the failure mode is silent.

## C5

Claim (branch `evalon/pydantic-s-07335cde`): `MissingDefinitionError` changes the inherited `LookupError` `str()` for the same argument. Code: `schema_gather.rs` defines `fn __str__` returning `"Reference {repr} does not point to an existing definition"`.

```sh
cd /home/ubuntu/wt-07335cde && /opt/venv-07335cde/bin/python /home/ubuntu/repos/pydantic/verify/repro/c5_missing_definition_str.py --former
```

```console
--- native (branch build)
  constructed 'missing': str(MDE)="Reference 'missing' does not point to an existing definition" str(LookupError)='missing' equal=False
      repr(MDE)=MissingDefinitionError('missing')  repr(LookupError)=LookupError('missing')  args=('missing',)
  constructed 'ref\x00with_nul': str(MDE)="Reference 'ref\\x00with_nul' does not point to an existing definition" str(LookupError)='ref\x00with_nul' equal=False
  constructed 'ユニコード_ref': str(MDE)="Reference 'ユニコード_ref' does not point to an existing definition" str(LookupError)='ユニコード_ref' equal=False
  raised by gather: str="Reference 'missing' does not point to an existing definition" args=('missing',) equal_to_LookupError_str=False
--- former pure-Python (base a2c93547)
  constructed 'missing': str(MDE)='missing' str(LookupError)='missing' equal=True
      repr(MDE)=MissingDefinitionError('missing')  repr(LookupError)=LookupError('missing')  args=('missing',)
  constructed 'ref\x00with_nul': str(MDE)='ref\x00with_nul' str(LookupError)='ref\x00with_nul' equal=True
  constructed 'ユニコード_ref': str(MDE)='ユニコード_ref' str(LookupError)='ユニコード_ref' equal=True
  raised by gather: str='missing' args=('missing',) equal_to_LookupError_str=True
```

Both constructed and gather-raised instances produce different text from `LookupError(ref)`; `args` are unchanged. Verdict: CONFIRMED.

Control on the audited branch (no `__str__` override):

```sh
cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c5_missing_definition_str.py
```

```console
  constructed 'missing': str(MDE)='missing' str(LookupError)='missing' equal=True
  raised by gather: str='missing' args=('missing',) equal_to_LookupError_str=True
```

The eval fixture `test_eval_schema_gather_errors.py::test_missing_definition` checks `args`, `schema_reference` and constructor round-trip, not `str()`, so it does not measure this; on this branch it fails for an unrelated reason in the `none-mapped` cases (`TypeError: 'None' is not an instance of 'dict'` at `pydantic/_internal/_schema_gather.py:50`), full run `10 failed, 50 passed`.

Impact reasoning: anyone logging `str(e)` for a missing definition now sees a sentence instead of the bare reference; pydantic's only catcher (`_generate_schema.py:2868`) uses the exception object, not its text, so nothing in-repo breaks. A visible behaviour change versus the former `LookupError` semantics the task asked to preserve.
