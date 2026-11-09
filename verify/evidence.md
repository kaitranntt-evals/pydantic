# Evidence — run v-67b2a9d6

Observations only; verdict reasoning that depends on them is in each section's last paragraph.

## Setup (shared by all sections)

```sh
cd /home/ubuntu/repos/pydantic
git fetch origin pydantic-schema-gather-to-core-perfect
git checkout -b verify/pydantic-schema-gather-to-core-v-67b2a9d6 origin/pydantic-schema-gather-to-core-perfect   # 585c99449
git remote add evalrepo https://git-manager.itsdev.in/proxy/github.com/kaitranntt-evals/pydantic-schema-gather-to-core
git fetch evalrepo evalon/pydantic-s-45c07a40 evalon/pydantic-s-705bf332
git worktree add --detach ../pyd-45c07a40 evalrepo/evalon/pydantic-s-45c07a40   # 020c29525
git worktree add --detach ../pyd-705bf332 evalrepo/evalon/pydantic-s-705bf332   # f68cf37db
# one venv + native build per checkout (startup.sh recipe): /opt/venv (audited branch), /opt/venv-45c07a40, /opt/venv-705bf332
uv venv /opt/venv-<name> --python 3.13
VIRTUAL_ENV=/opt/venv-<name> UV_PROJECT_ENVIRONMENT=/opt/venv-<name> uv pip install maturin==1.15.0 pytest==9.1.1 pytest-timeout==2.3.1
VIRTUAL_ENV=/opt/venv-<name> UV_PROJECT_ENVIRONMENT=/opt/venv-<name> uv sync --frozen --all-packages --all-extras --group testing-extra
PATH=/opt/venv-<name>/bin:$PATH maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
# eval fixtures, byte-exact from eval_tests.zip
cp <zip>/tests/test_eval_schema_gather_*.py <checkout>/tests/ ; cp <zip>/tests/schema_gather_test_runner.py /tmp/
```

Python is CPython 3.13.18 with the GIL enabled (`sys._is_gil_enabled() -> True`, `Py_GIL_DISABLED 0`). Builds are the debug profile `maturin develop` produces.
Raw outputs are under `verify/logs/`, probes under `verify/repro/`, mutation patches under `verify/instrumentation/`. No production file is changed on this branch; mutations were applied only inside the throw-away worktrees and reverted (`git checkout -- <file>` + rebuild).

## C1

Target: `evalon/pydantic-s-45c07a40` (020c29525), worktree `/home/ubuntu/repos/pyd-45c07a40`, venv `/opt/venv-45c07a40`.

### What the added/changed gathering tests are

```console
$ git diff --stat a2c935478 HEAD -- tests pydantic-core/tests
 pydantic-core/tests/test_schema_gather.py | 180 ++++++++++++++++++++++++++++++
 tests/test_internal.py                    | 110 ++++++++++++++++++
 2 files changed, 290 insertions(+)
$ git diff a2c935478 HEAD -- tests/test_internal.py | grep '^+def test'
+def test_gather_deep_schema() -> None:
+def test_clean_deep_schema() -> None:
+def test_gather_missing_definition_error(definitions) -> None:
+def test_gather_incremental_context() -> None:
+def test_gather_traversal_helpers() -> None:
```

Every place those tests build a `serialization` attachment (text of `pydantic-core/tests/test_schema_gather.py`; `tests/test_internal.py` builds none):

```python
# test_child_traversal: the attachment IS the definition-ref (direct); `function-plain`/`function-wrap`/`model`
# parametrisations put `schema`/`return_schema` on the top-level (unattached) schema
schema = {'type': schema_type, **replace(fields)}
schema['serialization'] = replace('serialization')
# test_repeated_reference_skips_serialization_and_metadata: direct definition-ref attachments
first['serialization'] = {'type': 'definition-ref', 'schema_ref': 'b'}
'serialization': {'type': 'definition-ref', 'schema_ref': 'missing'},
# test_deep_traversal[serialization]: 10,000 nullable schemas chained through `serialization` only
schema = {'type': 'nullable', nesting: schema}
# test_missing_reference_order_and_unreachable_definitions: direct definition-ref attachment, only the error is asserted
'serialization': {'type': 'definition-ref', 'schema_ref': 'serialization'},
```

### Dynamic scan of every schema those tests hand to the gatherer

`verify/repro/c1_attached_serializer_scan.py` is a pytest plugin that wraps the adapter and the native delegate `_gather_schemas`, walks each input, and classifies every `serialization` attachment: `direct` (the attachment itself is a definition-ref / carries the discriminator key), `combined` (a definition-ref or discriminator is inside the attachment's `schema` or `return_schema`), `other`. Counts are per wrapper level, so a call through the adapter is seen twice.

```sh
cd /home/ubuntu/repos/pyd-45c07a40 && export PATH=/opt/venv-45c07a40/bin:$PATH P=/home/ubuntu/repos/pydantic/verify/repro
PYTHONPATH=$P python -m pytest -p c1_attached_serializer_scan tests/test_internal.py -k "test_gather_deep_schema or test_clean_deep_schema or test_gather_missing_definition_error or test_gather_incremental_context or test_gather_traversal_helpers" -q -s -p no:cacheprovider
(cd pydantic-core && PYTHONPATH=$P python -m pytest -p c1_attached_serializer_scan tests/test_schema_gather.py -q -s -p no:cacheprovider)
PYTHONPATH=$P python -m pytest -p c1_attached_serializer_scan tests/test_eval_schema_gather_references.py tests/test_eval_schema_gather_traversal.py -q -s -p no:cacheprovider
```

Output (`verify/logs/c1_scan.log`; the 35 `test_child_traversal[...]` lines are elided here, each reads `{'gather_calls': 1, 'serialization_attachments': 1, 'direct': 1}`):

```console
### added tests in tests/test_internal.py (-k "test_gather_deep_schema or test_clean_deep_schema or test_gather_missing_definition_error or test_gather_incremental_context or test_gather_traversal_helpers")
[c1-scan] wrapped native delegates: ['_gather_schemas']
[c1-scan] tests that invoked the gatherer: 6
[c1-scan] TOTAL: {'gather_calls': 18}
[c1-scan] attachments reaching a definition-ref/discriminator through schema|return_schema: 0
         6 passed
        37 deselected
### pydantic-core/tests/test_schema_gather.py (new file)
[c1-scan] wrapped native delegates: ['_gather_schemas']
[c1-scan] tests/test_schema_gather.py::test_deep_traversal[serialization]: {'gather_calls': 1, 'serialization_attachments': 10000, 'other': 9999, 'direct': 1}
[c1-scan] tests/test_schema_gather.py::test_missing_reference_order_and_unreachable_definitions: {'gather_calls': 2, 'serialization_attachments': 1, 'direct': 1}
[c1-scan] tests/test_schema_gather.py::test_repeated_reference_skips_serialization_and_metadata[False]: {'gather_calls': 1, 'serialization_attachments': 2, 'direct': 2}
[c1-scan] tests/test_schema_gather.py::test_repeated_reference_skips_serialization_and_metadata[True]: {'gather_calls': 1, 'serialization_attachments': 1, 'direct': 1}
[c1-scan] tests that invoked the gatherer: 46
[c1-scan] TOTAL: {'gather_calls': 47, 'serialization_attachments': 10039, 'direct': 40, 'other': 9999}
[c1-scan] attachments reaching a definition-ref/discriminator through schema|return_schema: 0
        46 passed
### positive control for the scanner: eval fixtures tests/test_eval_schema_gather_references.py tests/test_eval_schema_gather_traversal.py
[c1-scan] wrapped native delegates: ['_gather_schemas']
[c1-scan] tests/test_eval_schema_gather_references.py::test_definition_ref_serialization_and_metadata: {'gather_calls': 4, 'serialization_attachments': 4, 'combined': 4, 'combined_via_return_schema': 4}
[c1-scan] tests/test_eval_schema_gather_references.py::test_metadata_evaluated_after_children_and_serializers: {'gather_calls': 2, 'serialization_attachments': 2, 'combined': 2, 'combined_via_return_schema': 2}
[c1-scan] tests/test_eval_schema_gather_traversal.py::test_all_schema_kinds: {'gather_calls': 2, 'serialization_attachments': 6, 'combined': 6, 'combined_via_return_schema': 6, 'combined_via_schema': 2}
[c1-scan] tests/test_eval_schema_gather_traversal.py::test_metadata_membership_callbacks_follow_post_order: {'gather_calls': 2, 'serialization_attachments': 2, 'combined': 2, 'combined_via_return_schema': 2}
[c1-scan] tests that invoked the gatherer: 31
[c1-scan] TOTAL: {'gather_calls': 210, 'serialization_attachments': 14, 'combined': 14, 'combined_via_return_schema': 14, 'combined_via_schema': 2}
[c1-scan] attachments reaching a definition-ref/discriminator through schema|return_schema: 14
```

So the branch's tests contain 0 attachments of the combined kind, while the scanner does see them (14) in the eval fixtures that build that path.

### Mutation: stop traversing `schema`/`return_schema` of attached serializers

`verify/instrumentation/c1_skip_attached_serializer_children.patch` (applies to `pydantic-core/src/schema_gather.rs` on 020c29525): remember the object reached through each `serialization` key and, when that object is visited, skip its `return_schema` (`function-plain`), `return_schema` + `schema` (`function-wrap`) and `schema` (default arm). Nothing else changes.

```sh
cd /home/ubuntu/repos/pyd-45c07a40
# unmutated baseline
python -m pytest tests/test_internal.py -q -p no:cacheprovider
(cd pydantic-core && python -m pytest tests/test_schema_gather.py -q -p no:cacheprovider)
python -m pytest tests/test_eval_schema_gather_references.py tests/test_eval_schema_gather_traversal.py -q -p no:cacheprovider -k "test_definition_ref_serialization_and_metadata or test_metadata_evaluated_after_children_and_serializers or test_all_schema_kinds or test_metadata_membership_callbacks_follow_post_order"
python /home/ubuntu/repos/pydantic/verify/repro/c1_attached_serializer_probe.py
# mutant
git apply /home/ubuntu/repos/pydantic/verify/instrumentation/c1_skip_attached_serializer_children.patch
maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
# ... same four commands ...
git checkout -- pydantic-core/src/schema_gather.rs && maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
```

Unmutated (`verify/logs/c1_unmutated.log`):

```console
### [unmutated] branch's own tests: tests/test_internal.py
.........xx................................                              [100%]
Results (0.53s):
        41 passed
         2 xfailed
### [unmutated] branch's own tests: pydantic-core/tests/test_schema_gather.py
..............................................                           [100%]
Results (0.10s):
        46 passed
### [unmutated] eval fixtures that build the combined path
         4 passed
        28 deselected
### [unmutated] behaviour probe
ok   plain serializer return_schema -> definition-ref collected by identity
ok   plain serializer return_schema -> deferred discriminator collected by identity
ok   wrap serializer schema -> definition-ref collected by identity
ok   wrap serializer return_schema -> definition-ref collected by identity
ok   wrap serializer schema -> deferred discriminator collected by identity
ok   wrap serializer return_schema -> deferred discriminator collected by identity
ok   model with @field_serializer returning another model builds and dumps: {'a': {'x': 1}}
failures=0
probe exit=0
```

Mutated (`verify/logs/c1_mutated.log`):

```console
### [mutated] branch's own tests: tests/test_internal.py
.........xx................................                              [100%]
Results (0.51s):
        41 passed
         2 xfailed
### [mutated] branch's own tests: pydantic-core/tests/test_schema_gather.py
..............................................                           [100%]
Results (0.58s):
        46 passed
### [mutated] eval fixtures that build the combined path
E       assert [128816642564800] == [128816642826...8816642564800]
E         
E         At index 0 diff: 128816642564800 != 128816642826816
E         Right contains one more item: 128816642564800
E         Use -v to get more diff
E       assert [128816634557...8816634423872] == [128816634557...8816634423872]
E         
E         At index 1 diff: 128816634550720 != 128816634545344
E         Right contains one more item: 128816634423872
E         Use -v to get more diff
E       AssertionError: assert ['typed_extra...or_item', ...] == ['typed_extra...or_item', ...]
E         
E         At index 42 diff: 'nullable_inner' != 'plain_ser_return'
E         Right contains 4 more items, first extra item: 'dataclass_inner'
E         Use -v to get more diff
E       AssertionError: Metadata membership order incorrect
E       assert ['child', 'se...er', 'parent'] == ['child', 'se...er', 'parent']
E         
E         At index 1 diff: 'serializer' != 'ser_return'
E         Right contains one more item: 'parent'
E         Use -v to get more diff
         4 failed
        28 deselected
### [mutated] behaviour probe
LOST plain serializer return_schema -> definition-ref collected by identity
LOST plain serializer return_schema -> deferred discriminator collected by identity
LOST wrap serializer schema -> definition-ref collected by identity
LOST wrap serializer return_schema -> definition-ref collected by identity
LOST wrap serializer schema -> deferred discriminator collected by identity
LOST wrap serializer return_schema -> deferred discriminator collected by identity
LOST model with @field_serializer returning another model: SchemaError: Definitions error: definition `__main__.Inner:1089316160` was never filled
failures=7
probe exit=1
```

Mutated build against the task's guideline suites and a wider pre-existing slice (`verify/logs/c1_mutated_wider.log`):

```console
### [mutated] task-guideline suite: tests/types/unions/test_discriminated_union.py tests/test_forward_ref.py tests/test_internal.py
.x........x..........xx................................                  [100%]
Results (1.53s):
       188 passed
        11 xfailed
### [mutated] task-guideline suite: pydantic-core/tests -k 'not test_docs'
      5779 passed
       126 skipped
        64 deselected
         8 xfailed
### [mutated] wider pre-existing suite (not part of the added/changed tests): tests/test_serialize.py tests/test_computed_fields.py tests/test_generics.py
         4 failed
       243 passed
         5 skipped
         6 xfailed
### [mutated] the 4 failures above, by error line (python -m pytest tests/test_serialize.py tests/test_computed_fields.py tests/test_generics.py -q -rf | grep "^E  +pydantic_core")
E       pydantic_core._pydantic_core.SchemaError: Definitions error: definition `tests.test_serialize.test_forward_ref_for_serializers.<locals>.OtherModel:406185232` was never filled
E       pydantic_core._pydantic_core.SchemaError: Definitions error: definition `tests.test_serialize.test_forward_ref_for_serializers.<locals>.OtherModel:407071824` was never filled
E       pydantic_core._pydantic_core.SchemaError: Definitions error: definition `tests.test_serialize.test_forward_ref_for_serializers.<locals>.OtherModel:407082160` was never filled
E       pydantic_core._pydantic_core.SchemaError: Definitions error: definition `tests.test_serialize.test_forward_ref_for_serializers.<locals>.OtherModel:407098656` was never filled
```

After reverting and rebuilding, the probe is back to `failures=0`.

Reading: with collection through an attached serializer's `schema`/`return_schema` removed, all of the branch's gathering tests (41 passed + 2 xfailed in `tests/test_internal.py`, 46 passed in `pydantic-core/tests/test_schema_gather.py`) and both guideline suites stay green; the regression is observable (7 probe checks lost, a `@field_serializer` returning another model raises `SchemaError ... was never filled`) and is caught by the 4 eval fixtures that build that path and, end to end rather than by identity, by the pre-existing unchanged `tests/test_serialize.py::test_forward_ref_for_serializers`.

## C2

Target: `evalon/pydantic-s-705bf332` (f68cf37db), worktree `/home/ubuntu/repos/pyd-705bf332`, venv `/opt/venv-705bf332`. Control: audited branch `pydantic-schema-gather-to-core-perfect` (585c99449), `/home/ubuntu/repos/pydantic`, venv `/opt/venv`.

The branch adds no threaded test of its own, so "the concurrent-isolation test" is the eval fixture `tests/test_eval_schema_gather_lifecycle.py::test_threaded_calls_are_isolated` (used byte-exact):

```console
$ cd /home/ubuntu/repos/pyd-705bf332 && grep -ciE "thread|barrier|concurrent" tests/test_internal.py pydantic-core/tests/test_schema_gather.py
tests/test_internal.py:0
pydantic-core/tests/test_schema_gather.py:0
```

Synchronisation and assertions of the fixture's overlap stage (text):

```python
barrier = threading.Barrier(2)

class OverlappingBarrierDict(dict):
    def values(self) -> Any:
        barrier.wait(timeout=5)
        return super().values()
...
fields = OverlappingBarrierDict({'f': cs.typed_dict_field(def_ref)})
schema = cs.typed_dict_schema(fields)
...
assert list(res_a['collected_references'].keys()) == ['thread_a']
assert list(res_b['collected_references'].keys()) == ['thread_b']
assert res_a['collected_references']['thread_a']['schema_ref'] == 'thread_a'
assert res_b['collected_references']['thread_b']['schema_ref'] == 'thread_b'
```

The only thing that would force two gathers to be in flight together is `barrier.wait` inside `values()`; nothing asserts it ran. On this branch the native code iterates the mapping without calling `values()` (`pydantic-core/src/schema_gather.rs`):

```rust
fn push_values<'py>(work: &mut Vec<Work<'py>>, items: Bound<'py, PyDict>) -> PyResult<()> {
    for (_, value) in items.iter() {
```

### Probe: trace, and forbid, overlap without touching the fixture

`verify/repro/c2_overlap_probe.py` is a pytest plugin that rebinds, before collection, the adapter `gather_schemas_for_cleaning` and the native entry `_traverse_schema` inside `pydantic._internal._schema_gather` with wrappers recording enter/exit per thread, and counts `threading.Barrier.wait` calls. `C2_MODE=serialize` additionally holds one process-wide lock around every adapter call, so two gathers can never be in flight together (the controlled non-overlapping execution). `C2_WARMUP=1` performs one single-threaded typed-dict gather first (explained below).

```sh
cd /home/ubuntu/repos/pyd-705bf332 && export PATH=/opt/venv-705bf332/bin:$PATH P=/home/ubuntu/repos/pydantic/verify/repro
python -m pytest tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated -q -p no:cacheprovider     # x20
C2_MODE=trace     PYTHONPATH=$P python -m pytest -p c2_overlap_probe tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated -q -s -p no:cacheprovider
C2_MODE=serialize PYTHONPATH=$P python -m pytest -p c2_overlap_probe tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated -q -s -p no:cacheprovider
cp $P/c2_overlap_required_test.py tests/ && python -m pytest tests/c2_overlap_required_test.py -q -p no:cacheprovider -rA
```

`evalon/pydantic-s-705bf332`, unmutated (`verify/logs/c2_705bf332_unmutated.log`):

```console
### [705bf332 unmutated] eval fixture, unmodified: pytest tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated  (x20)
runs=20 passed=20 failed=0
### [705bf332 unmutated] eval fixture under the probe, C2_MODE=trace
[c2-probe] mode=trace native_entry=_traverse_schema test=tests/test_eval_schema_gather_lifecycle.py::test_threaded_calls_are_isolated outcome=passed
[c2-probe]   adapter: calls=22 threads=5 max_simultaneous_in_flight=1 outcomes=['ok']
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+43.4us (ok)
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+80.9us exit=+94.6us (ok)
[c2-probe]   native: calls=22 threads=5 max_simultaneous_in_flight=1 outcomes=['ok']
[c2-probe]     last-two native call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+39.0us (ok)
[c2-probe]     last-two native call on ThreadPoolExecutor-1_0: enter=+80.2us exit=+91.4us (ok)
[c2-probe]   threading.Barrier.wait calls=0 threads=[]
         1 passed
### [705bf332 unmutated] eval fixture under the probe, C2_MODE=serialize
[c2-probe] mode=serialize native_entry=_traverse_schema test=tests/test_eval_schema_gather_lifecycle.py::test_threaded_calls_are_isolated outcome=passed
[c2-probe]   adapter: calls=22 threads=5 max_simultaneous_in_flight=1 outcomes=['ok']
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+44.5us (ok)
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+82.7us exit=+96.3us (ok)
[c2-probe]   native: calls=22 threads=5 max_simultaneous_in_flight=1 outcomes=['ok']
[c2-probe]     last-two native call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+39.9us (ok)
[c2-probe]     last-two native call on ThreadPoolExecutor-1_0: enter=+81.9us exit=+93.0us (ok)
[c2-probe]   threading.Barrier.wait calls=0 threads=[]
         1 passed
### [705bf332 unmutated] verify/repro/c2_overlap_required_test.py
E       AssertionError: barrier rendezvous never ran (threads that reached it: []); no overlap was established
E       assert 0 == 2
E        +  where 0 = len(set())
E        +    where set() = set([])
         1 failed
         1 passed
```

The two "overlapping" workers ran one after the other on the same pool thread (`ThreadPoolExecutor-1_0`), the barrier was never waited on, and the test passed; it also passed with overlap made impossible. The single failure in the last block is `test_fixture_stage_two_rendezvous_ran` (the fixture's stage 2 verbatim plus `assert len(set(met)) == 2`).

Same commands on the control branch (`verify/logs/c2_control_perfect.log`) — there the rendezvous runs, two gathers are in flight together, and the non-overlapping probe cannot complete:

```console
### [control: pydantic-schema-gather-to-core-perfect] eval fixture, unmodified: pytest tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated  (x5)
runs=5 passed=5 failed=0
### [control: pydantic-schema-gather-to-core-perfect] eval fixture under the probe, C2_MODE=trace
[c2-probe] mode=trace native_entry=None test=tests/test_eval_schema_gather_lifecycle.py::test_threaded_calls_are_isolated outcome=passed
[c2-probe]   adapter: calls=22 threads=6 max_simultaneous_in_flight=2 outcomes=['ok']
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+229.8us (ok)
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_1: enter=+111.5us exit=+148.0us (ok)
[c2-probe]   threading.Barrier.wait calls=2 threads=['ThreadPoolExecutor-1_0', 'ThreadPoolExecutor-1_1']
         1 passed
### [control: pydantic-schema-gather-to-core-perfect] eval fixture under the probe, C2_MODE=serialize
[c2-probe] mode=serialize native_entry=None test=tests/test_eval_schema_gather_lifecycle.py::test_threaded_calls_are_isolated outcome=failed
[c2-probe]   adapter: calls=22 threads=6 max_simultaneous_in_flight=1 outcomes=['BrokenBarrierError', 'ok']
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+5000306.8us (BrokenBarrierError)
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_1: enter=+5000614.2us exit=+5000746.1us (BrokenBarrierError)
[c2-probe]   threading.Barrier.wait calls=2 threads=['ThreadPoolExecutor-1_0', 'ThreadPoolExecutor-1_1']
E           threading.BrokenBarrierError
         1 failed
### [control: pydantic-schema-gather-to-core-perfect] verify/repro/c2_overlap_required_test.py
         2 passed
```

### How often does a natural run on the claim branch contain any overlap?

```sh
for i in $(seq 30); do C2_MODE=trace C2_WARMUP=0 PYTHONPATH=$P python -m pytest -p c2_overlap_probe tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated -q -s -p no:cacheprovider | grep "RESULT"; done | sort | uniq -c
# and again with C2_WARMUP=1
```

`verify/logs/c2_705bf332_unmutated_repeat.log`:

```console
### [705bf332 unmutated] 30 fresh processes: C2_MODE=trace C2_WARMUP=0 python -m pytest -p c2_overlap_probe tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated -q -s
     21 [c2-probe] RESULT outcome=passed gathers_in_flight_together=1 barrier_waits=0 warmup=0
      9 [c2-probe] RESULT outcome=passed gathers_in_flight_together=2 barrier_waits=0 warmup=0
### [705bf332 unmutated] 30 fresh processes: C2_MODE=trace C2_WARMUP=1 python -m pytest -p c2_overlap_probe tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated -q -s
     30 [c2-probe] RESULT outcome=passed gathers_in_flight_together=1 barrier_waits=0 warmup=1
```

21 of 30 fresh-process runs passed with at most one gather in flight at any time; 9 of 30 had two in flight, never via the barrier (`barrier_waits=0` in all 60 runs). After one warm-up gather the overlap disappears (30/30 with one in flight). The 9 are therefore incidental: they need a first-use, one-off release of the interpreter inside the native call (PyO3 0.29.2 `src/sync.rs`: `Interned::get` -> `PyOnceLock::get_or_init` -> `init_once_lock_py_attached`, which does `SuspendAttach::new()` — detaches from the interpreter — before the first initialisation of each `intern!` site; the typed-dict arm's sites are first used in stage 2. The source matches the warm-up result; the release itself was not traced in a debugger), and whether the second worker is scheduled inside that window.

### What that lets through: state shared across native invocations

`verify/instrumentation/c2_native_shared_scratch_state.patch` (on f68cf37db): `_traverse_schema` does its work in one process-wide scratch state (seeded from, and copied back to, the caller's containers). Sequential behaviour is unchanged; two invocations in flight together clobber each other.

```sh
git apply /home/ubuntu/repos/pydantic/verify/instrumentation/c2_native_shared_scratch_state.patch && maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
# same four commands as above (fixture x30), then the 30-run repeats with C2_WARMUP=0 and 1
git checkout -- pydantic-core/src/schema_gather.rs && maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
```

`verify/logs/c2_705bf332_native_shared_scratch_mutant.log`:

```console
### [705bf332 + native shared-scratch mutant] eval fixture, unmodified: pytest tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated  (x30)
runs=30 passed=17 failed=13
### [705bf332 + native shared-scratch mutant] eval fixture under the probe, C2_MODE=trace
[c2-probe] mode=trace native_entry=_traverse_schema test=tests/test_eval_schema_gather_lifecycle.py::test_threaded_calls_are_isolated outcome=failed
[c2-probe]   adapter: calls=22 threads=6 max_simultaneous_in_flight=2 outcomes=['ok']
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+192.5us (ok)
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_1: enter=+96.2us exit=+241.7us (ok)
[c2-probe]   native: calls=22 threads=6 max_simultaneous_in_flight=2 outcomes=['ok']
[c2-probe]     last-two native call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+185.7us (ok)
[c2-probe]     last-two native call on ThreadPoolExecutor-1_1: enter=+95.8us exit=+236.9us (ok)
[c2-probe]   threading.Barrier.wait calls=0 threads=[]
E           AssertionError: assert ['thread_a', 'thread_b'] == ['thread_b']
E             
E             At index 0 diff: 'thread_a' != 'thread_b'
E             Left contains one more item: 'thread_b'
E             Use -v to get more diff
         1 failed
### [705bf332 + native shared-scratch mutant] eval fixture under the probe, C2_MODE=serialize
[c2-probe] mode=serialize native_entry=_traverse_schema test=tests/test_eval_schema_gather_lifecycle.py::test_threaded_calls_are_isolated outcome=passed
[c2-probe]   adapter: calls=22 threads=5 max_simultaneous_in_flight=1 outcomes=['ok']
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+150.2us (ok)
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+167.9us exit=+189.9us (ok)
[c2-probe]   native: calls=22 threads=5 max_simultaneous_in_flight=1 outcomes=['ok']
[c2-probe]     last-two native call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+143.4us (ok)
[c2-probe]     last-two native call on ThreadPoolExecutor-1_0: enter=+166.7us exit=+184.9us (ok)
[c2-probe]   threading.Barrier.wait calls=0 threads=[]
         1 passed
### [705bf332 + native shared-scratch mutant] verify/repro/c2_overlap_required_test.py
E           AssertionError: assert ['thread_b'] == ['thread_a']
E             
E             At index 0 diff: 'thread_b' != 'thread_a'
E             Use -v to get more diff
E       AssertionError: assert ['thread_b'] == ['thread_a']
E         
E         At index 0 diff: 'thread_b' != 'thread_a'
E         Use -v to get more diff
         2 failed
```

`verify/logs/c2_705bf332_native_shared_scratch_mutant_repeat.log`:

```console
### [705bf332 + native shared-scratch mutant] 30 fresh processes: C2_MODE=trace C2_WARMUP=0 python -m pytest -p c2_overlap_probe tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated -q -s
     11 [c2-probe] RESULT outcome=failed gathers_in_flight_together=2 barrier_waits=0 warmup=0
     19 [c2-probe] RESULT outcome=passed gathers_in_flight_together=1 barrier_waits=0 warmup=0
### [705bf332 + native shared-scratch mutant] 30 fresh processes: C2_MODE=trace C2_WARMUP=1 python -m pytest -p c2_overlap_probe tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated -q -s
     30 [c2-probe] RESULT outcome=passed gathers_in_flight_together=1 barrier_waits=0 warmup=1
```

The shared-state mutant passes the unmodified fixture in 17 of 30 runs (19 of 30 under the trace probe), exactly the runs in which no two gathers happened to be in flight together, and in 30 of 30 runs after a warm-up gather; `test_overlap_forced_through_metadata_membership` (rendezvous in the metadata membership check, plus an assertion that it ran) fails it every time and passes on the unmutated branch and on the control branch.

A second, Python-only mutant (`verify/instrumentation/c2_python_adapter_shared_context.patch`: the adapter reuses one module-level `GatherContext`) behaves the same way — `verify/logs/c2_705bf332_python_adapter_shared_context_mutant.log`:

```console
### [705bf332 + shared-state mutant] eval fixture, unmodified: pytest tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated  (x20)
runs=20 passed=12 failed=8
### [705bf332 + shared-state mutant] eval fixture under the probe, C2_MODE=trace
[c2-probe] mode=trace native_entry=_traverse_schema test=tests/test_eval_schema_gather_lifecycle.py::test_threaded_calls_are_isolated outcome=passed
[c2-probe]   adapter: calls=22 threads=5 max_simultaneous_in_flight=1 outcomes=['ok']
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+65.0us (ok)
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+114.3us exit=+130.4us (ok)
[c2-probe]   native: calls=22 threads=5 max_simultaneous_in_flight=1 outcomes=['ok']
[c2-probe]     last-two native call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+58.1us (ok)
[c2-probe]     last-two native call on ThreadPoolExecutor-1_0: enter=+113.0us exit=+125.9us (ok)
[c2-probe]   threading.Barrier.wait calls=0 threads=[]
         1 passed
### [705bf332 + shared-state mutant] eval fixture under the probe, C2_MODE=serialize
[c2-probe] mode=serialize native_entry=_traverse_schema test=tests/test_eval_schema_gather_lifecycle.py::test_threaded_calls_are_isolated outcome=passed
[c2-probe]   adapter: calls=22 threads=6 max_simultaneous_in_flight=1 outcomes=['ok']
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+350.2us (ok)
[c2-probe]     last-two adapter call on ThreadPoolExecutor-1_1: enter=+380.4us exit=+409.1us (ok)
[c2-probe]   native: calls=22 threads=6 max_simultaneous_in_flight=1 outcomes=['ok']
[c2-probe]     last-two native call on ThreadPoolExecutor-1_0: enter=+0.0us exit=+339.7us (ok)
[c2-probe]     last-two native call on ThreadPoolExecutor-1_1: enter=+381.5us exit=+404.5us (ok)
[c2-probe]   threading.Barrier.wait calls=0 threads=[]
         1 passed
### [705bf332 + shared-state mutant] verify/repro/c2_overlap_required_test.py
E       AssertionError: barrier rendezvous never ran (threads that reached it: []); no overlap was established
E       assert 0 == 2
E        +  where 0 = len(set())
E        +    where set() = set([])
E       AssertionError: assert ['thread_b'] == ['thread_a']
E         
E         At index 0 diff: 'thread_b' != 'thread_a'
E         Use -v to get more diff
         2 failed
```

Reading: on this branch successful completion of the test carries no evidence of overlap (barrier never reached; passes when overlap is forbidden; in 21/30 natural runs nothing overlapped), and an implementation with cross-invocation shared state passes it in the majority of runs.

## C3

Target: `evalon/pydantic-s-705bf332` (f68cf37db), worktree `/home/ubuntu/repos/pyd-705bf332`, venv `/opt/venv-705bf332`.

Adapter and native signature (text, `pydantic/_internal/_schema_gather.py` and `pydantic-core/src/schema_gather.rs`):

```python
def traverse_schema(schema: AllSchemas, context: GatherContext) -> None:
    _traverse_schema(
        schema,
        context.definitions,
        context.collected_references,
        context.deferred_discriminator_schemas,
        context.visited,
        context.encountered_refs,
        MissingDefinitionError,
    )

def gather_schemas_for_cleaning(schema: CoreSchema, definitions: dict[str, CoreSchema]) -> GatherResult:
    context = GatherContext(definitions)      # dataclass: visited = {}, encountered_refs = [] allocated here
    traverse_schema(schema, context)
```

```rust
#[pyfunction]
pub fn _traverse_schema<'py>(
    schema: Bound<'py, PyDict>,
    definitions: &Bound<'py, PyDict>,
    collected_references: &Bound<'py, PyDict>,
    deferred_discriminator_schemas: &Bound<'py, PyList>,
    visited: &Bound<'py, PyDict>,
    encountered_refs: &Bound<'py, PyList>,
    missing_definition_error: &Bound<'py, PyType>,
) -> PyResult<()> {
```

Runtime probes (`verify/logs/c3_probe.log`):

```sh
cd /home/ubuntu/repos/pyd-705bf332 && /opt/venv-705bf332/bin/python /home/ubuntu/repos/pydantic/verify/repro/c3_bookkeeping_interface_probe.py
# cost comparison: same script in each checkout's venv
cd /home/ubuntu/repos/<checkout> && /opt/<venv>/bin/python /home/ubuntu/repos/pydantic/verify/repro/c3_bookkeeping_cost_probe.py
```

```console
### 705bf332: python verify/repro/c3_bookkeeping_interface_probe.py
native gathering entry points exported by pydantic_core._pydantic_core:
  _traverse_schema(schema, definitions, collected_references, deferred_discriminator_schemas, visited, encountered_refs, missing_definition_error)
required positional parameters of _traverse_schema: ['schema', 'definitions', 'collected_references', 'deferred_discriminator_schemas', 'visited', 'encountered_refs', 'missing_definition_error'] (7)

1. calling the native entry point with only the schema, the definitions and the error type:
   TypeError: _traverse_schema() missing 4 required positional arguments: 'deferred_discriminator_schemas', 'visited', 'encountered_refs', and 'missing_definition_error'

2. calling it with the result containers but no traversal bookkeeping (visited=None, encountered_refs=None):
   TypeError: 'None' is not an instance of 'dict'

3. tracing what the Python adapter passes for one gather_schemas_for_cleaning() call:
   native call: 7 positional, 0 keyword arguments
   argument (type, len) on entry: [('dict', 2), ('dict', 1), ('dict', 0), ('list', 0), ('dict', 0), ('list', 0), ('type', None)]
   args[2] is the Python-allocated GatherContext.collected_references: True
   args[3] is the Python-allocated GatherContext.deferred_discriminator_schemas: True
   args[4] is the Python-allocated GatherContext.visited: True
   args[5] is the Python-allocated GatherContext.encountered_refs: True
   after the native call, Python-owned visited = [(0, 1), (0, 1), (0, 1), (1, 1)]
   after the native call, Python-owned encountered_refs = ['leaf']
   returned collected_references is the Python-allocated dict: True
   defining two BaseModel classes (real call site, GenerateSchema.clean_schema) made 2 more native call(s), each with [7] positional args and Python-allocated containers: True

Python allocates and passes traversal bookkeeping as required native arguments: True
exit=1
### pyd-705bf332 (f68cf37db): python verify/repro/c3_bookkeeping_cost_probe.py
nodes=~101k collected=1000 best_of_5=143.5 ms python_heap_peak_during_call=18.92 MB
### pyd-45c07a40 (020c29525): python verify/repro/c3_bookkeeping_cost_probe.py
nodes=~101k collected=1000 best_of_5=80.8 ms python_heap_peak_during_call=0.04 MB
### pydantic (585c99449): python verify/repro/c3_bookkeeping_cost_probe.py
nodes=~101k collected=1000 best_of_5=82.4 ms python_heap_peak_during_call=0.04 MB
```

Reading: the only native gathering entry point requires seven positional arguments; four of them are containers allocated by Python's `GatherContext`, including the traversal bookkeeping `visited` and `encountered_refs`; the native call cannot run without them (`TypeError`), writes its per-node spans into the Python dict, and the real call site (`GenerateSchema.clean_schema` during model definition) uses the same seven-argument call. On a ~101k-node schema that bookkeeping shows up as 18.92 MB of Python-heap allocations during one call versus 0.04 MB on the two branches that keep it native (`evalon/pydantic-s-45c07a40`, `pydantic-schema-gather-to-core-perfect`), and 143.5 ms versus 80.8/82.4 ms (debug builds; ratio only).
