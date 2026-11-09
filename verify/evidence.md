## Setup (shared by all claims)

Each claim targets its own branch of [kaitranntt-evals/pydantic-schema-gather-to-core](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core); each got its own worktree, venv and native build.

```sh
cd /home/ubuntu/repos/pydantic
git fetch origin pydantic-schema-gather-to-core-perfect
git checkout -b verify/pydantic-schema-gather-to-core-v-6d46b697 origin/pydantic-schema-gather-to-core-perfect
git remote add claims https://git-manager.itsdev.in/proxy/github.com/kaitranntt-evals/pydantic-schema-gather-to-core
git fetch claims evalon/pydantic-s-b140b048 evalon/pydantic-s-3f54c6e9 evalon/pydantic-s-00346963
for n in b140b048 3f54c6e9 00346963; do
  git worktree add --detach ../wt-$n claims/evalon/pydantic-s-$n
  ( cd ../wt-$n
    sudo mkdir -p /opt/venv-$n && sudo chown -R "$(whoami):$(whoami)" /opt/venv-$n
    export PATH="/opt/venv-$n/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH" VIRTUAL_ENV=/opt/venv-$n UV_PROJECT_ENVIRONMENT=/opt/venv-$n
    uv venv /opt/venv-$n --python 3.13
    uv pip install maturin==1.15.0 pytest==9.1.1 pytest-timeout==2.3.1
    uv sync --frozen --all-packages --all-extras --group testing-extra
    maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen )
done
# control implementation = the pre-change pure-Python module
git show a2c935478:pydantic/_internal/_schema_gather.py > verify/repro/reference_schema_gather.py
# eval fixtures: unzip eval_tests.zip to ~/eval_tests, copy tests/test_eval_*.py byte-exact into <worktree>/tests/ for a run, delete afterwards
```

Worktree HEADs: `wt-b140b048` = `a8a40653c`, `wt-3f54c6e9` = `5e04613cc`, `wt-00346963` = `40b210d19`. Python 3.13, `maturin develop` dev profile.

## C1

Branch: [evalon/pydantic-s-b140b048](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-b140b048) (`a8a40653c`). Verdict: **CONFIRMED**.

Naming drift: there is no `_schema_gather.pyi` on the branch; the only delivered stub for the native entry point is `pydantic-core/python/pydantic_core/_pydantic_core.pyi`, and the entry point is `pydantic_core._pydantic_core.gather_schemas_for_cleaning`.

Runtime signature in `pydantic-core/src/schema_gather.rs` (read, then exercised below):

```rust
#[pyfunction(signature = (schema, definitions, *, missing_definition_error = None))]
pub fn gather_schemas_for_cleaning<'py>(
    py: Python<'py>,
    schema: Bound<'py, PyAny>,
    definitions: Bound<'py, PyAny>,
    missing_definition_error: Option<Bound<'py, PyType>>,
```

Runtime probe ([verify/repro/c1_function_factory_rejected.py](repro/c1_function_factory_rejected.py)); it prints the stub signature from the installed `.pyi`, then calls the native entry point on `{'type': 'definition-ref', 'schema_ref': 'missing'}` with an empty definitions mapping and several factories:

```sh
cd /home/ubuntu/repos/wt-b140b048
/opt/venv-b140b048/bin/python /home/ubuntu/repos/pydantic/verify/repro/c1_function_factory_rejected.py
```

```console
Traceback (most recent call last):
  File "/home/ubuntu/repos/pydantic/verify/repro/c1_function_factory_rejected.py", line 57, in <module>
    gather_schemas_for_cleaning(schema, {}, missing_definition_error=function_factory)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: 'function' object is not an instance of 'type'
while processing 'missing_definition_error'
--- stub signature ---
def gather_schemas_for_cleaning(
    schema: CoreSchema,
    definitions: Mapping[Any, CoreSchema],
    *,
    missing_definition_error: Callable[[Any], BaseException] | None = None,
) -> dict[str, Any]:
--- runtime text signature ---
(schema, definitions, *, missing_definition_error=None) (schema, definitions, *, missing_definition_error=None)
class MissingDefinitionError                  -> MissingDefinitionError: missing
def function_factory                          -> TypeError: 'function' object is not an instance of 'type'
lambda                                        -> TypeError: 'function' object is not an instance of 'type'
functools.partial(MissingDefinitionError)     -> TypeError: 'partial' object is not an instance of 'type'
callable instance                             -> TypeError: 'CallableInstance' object is not an instance of 'type'
None (default)                                -> KeyError: 'missing'
--- full traceback for the function-valued factory ---
--- factory on a schema with NO missing definition (argument conversion happens before traversal) ---
TypeError: 'function' object is not an instance of 'type'
RESULT: 4 stub-permitted callables rejected with TypeError
exit=1
```

(The traceback at the top is the stderr part of the "full traceback" step.) The class and the `None` default work; a plain function, a lambda, a `functools.partial` and a callable instance, all of which satisfy `Callable[[Any], BaseException]`, fail in argument conversion with `TypeError` before any traversal starts (it also fails for `{'type': 'int'}`, where no definition is missing).

That the stub really permits a function was checked with a type checker against the branch's stub ([verify/repro/c1_stub_typecheck.py](repro/c1_stub_typecheck.py)); only the deliberate non-callable control (`42`) is flagged, the function and lambda calls are accepted:

```sh
cd /home/ubuntu/repos/wt-b140b048
uvx pyright --pythonpath /opt/venv-b140b048/bin/python /home/ubuntu/repos/pydantic/verify/repro/c1_stub_typecheck.py
```

```console
verify/repro/c1_stub_typecheck.py
  verify/repro/c1_stub_typecheck.py:15:75 - error: Argument of type "Literal[42]" cannot be assigned to parameter "missing_definition_error" of type "((Any) -> BaseException) | None" in function "gather_schemas_for_cleaning"
    Type "Literal[42]" is not assignable to type "((Any) -> BaseException) | None"
      Type "Literal[42]" is not assignable to type "(Any) -> BaseException"
      "Literal[42]" is not assignable to "None" (reportArgumentType)
1 error, 0 warnings, 0 informations
```

Checks do not see this: all six eval fixture files pass on this branch, and none of them calls the native entry point with a non-class factory.

```sh
cd /home/ubuntu/repos/wt-b140b048 && cp ~/eval_tests/tests/test_eval_*.py tests/
/opt/venv-b140b048/bin/python -m pytest tests/test_eval_schema_gather_native.py tests/test_eval_schema_gather_depth.py tests/test_eval_schema_gather_references.py tests/test_eval_schema_gather_traversal.py tests/test_eval_schema_gather_errors.py tests/test_eval_schema_gather_lifecycle.py -q -p no:cacheprovider -p no:pretty | tail -n 1
```

```console
81 passed in 0.90s
```

Impact reasoning: Pydantic's own wrapper (`pydantic/_internal/_schema_gather.py`) always passes the `MissingDefinitionError` class, so schema cleaning inside Pydantic is unaffected and the task's required interface works. The defect is a stub/runtime contract mismatch on the new `pydantic_core` function: code that type-checks cleanly against the shipped stub (function, lambda, partial) raises `TypeError: 'function' object is not an instance of 'type'` on every call, including calls where nothing is missing. Workaround: pass an exception class. The stub's own docstring says "The exception type to raise", so the annotation, not the runtime, is the likely outlier.

## C2

Branch: [evalon/pydantic-s-3f54c6e9](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-3f54c6e9) (`5e04613cc`). Verdict: **CONFIRMED**.

Naming drift: `collect_child_schemas` / `children_values_required` do not exist on this branch; the equivalent is the `"tagged-union"` arm of `push_children` in `pydantic-core/src/schema_gather.rs`:

```rust
"tagged-union" => {
    let choices: Bound<'_, PyDict> = schema.get_as_req(intern!(py, "choices"))?;
    stack.extend(choices.iter().map(|(_, choice)| Frame::Visit(choice)));
}
```

The pre-change Python does `for v in schema['choices'].values(): traverse_schema(v, context)`.

Probe ([verify/repro/c2_tagged_union_choices_mapping.py](repro/c2_tagged_union_choices_mapping.py)): a `tagged-union` schema whose `choices` is, in turn, a plain dict (control), a dict subclass whose `values()` reverses the stored children, a dict subclass whose `values()` returns a different child, a `collections.UserDict`, and a `types.MappingProxyType`. Each child is a `definition-ref` carrying the deferred-discriminator metadata, so both result fields show which children were traversed and in what order. Every case is run through the pre-change Python module and through `pydantic._internal._schema_gather.gather_schemas_for_cleaning` on the branch:

```sh
cd /home/ubuntu/repos/wt-3f54c6e9
/opt/venv-3f54c6e9/bin/python /home/ubuntu/repos/pydantic/verify/repro/c2_tagged_union_choices_mapping.py
```

```console
[plain dict (control)]
    values() returns : ['a', 'b']
    reference python : refs=['a', 'b'] deferred=['a', 'b']
    native (branch)  : refs=['a', 'b'] deferred=['a', 'b']
    -> OK
[dict subclass, values() reversed]
    values() returns : ['b', 'a']
    reference python : refs=['b', 'a'] deferred=['b', 'a']
    native (branch)  : refs=['a', 'b'] deferred=['a', 'b']
    -> MISMATCH
[dict subclass, values() replaced]
    values() returns : ['c']
    reference python : refs=['c'] deferred=['c']
    native (branch)  : refs=['a', 'b'] deferred=['a', 'b']
    -> MISMATCH
[collections.UserDict]
    values() returns : ['a', 'b']
    reference python : refs=['a', 'b'] deferred=['a', 'b']
    native (branch)  : RAISED TypeError: 'UserDict' object is not an instance of 'dict'
    -> MISMATCH
[types.MappingProxyType]
    values() returns : ['a', 'b']
    reference python : refs=['a', 'b'] deferred=['a', 'b']
    native (branch)  : RAISED TypeError: 'mappingproxy' object is not an instance of 'dict'
    -> MISMATCH
RESULT: 4 of 4 non-plain mappings mishandled
exit=1
```

Both halves of the claim hold: the dict subclass is accepted but its `values()` is bypassed (stored order `a, b` instead of `b, a`; stored children `a, b` instead of the returned `c`), and `UserDict` / `MappingProxyType` are rejected with `TypeError`.

The eval fixture exercising the same protocol on typed-dict `fields` also fails on this branch:

```sh
cd /home/ubuntu/repos/wt-3f54c6e9 && cp ~/eval_tests/tests/test_eval_*.py tests/
/opt/venv-3f54c6e9/bin/python -m pytest tests/test_eval_schema_gather_traversal.py -k test_mapping_values_protocol -q -p no:cacheprovider -p no:pretty -p no:sugar --tb=short
```

```console
tests/test_eval_schema_gather_traversal.py:271: in test_mapping_values_protocol
    assert list(result_rev['collected_references'].keys()) == ['b', 'a'], 'ReversedValuesDict values() bypassed'
E   AssertionError: ReversedValuesDict values() bypassed
E   assert ['a', 'b'] == ['b', 'a']
FAILED tests/test_eval_schema_gather_traversal.py::test_mapping_values_protocol
1 failed, 20 deselected in 0.24s
```

Impact reasoning: this is a behavior change against the pre-change gatherer, which accepted anything with `.values()` and traversed exactly what it returned. How ordinary is it? Schemas generated by Pydantic use plain dicts for `choices`, and on this branch `SchemaValidator` itself rejects non-dict choices, so only code calling the gatherer directly with hand-built schemas is affected:

```sh
cd /home/ubuntu/repos/wt-3f54c6e9
/opt/venv-3f54c6e9/bin/python - <<'PY'
from collections import UserDict
from types import MappingProxyType
from pydantic_core import SchemaValidator
class R(dict):
    def values(self): return reversed(tuple(super().values()))
mk = lambda: {'a': {'type':'typed-dict','fields':{'kind':{'type':'typed-dict-field','schema':{'type':'str'}}}}}
for name, c in [('dict', mk()), ('dict subclass', R(mk())), ('UserDict', UserDict(mk())), ('MappingProxyType', MappingProxyType(mk()))]:
    try:
        v = SchemaValidator({'type':'tagged-union','discriminator':'kind','choices': c})
        print(f'SchemaValidator choices={name}: accepted ->', v.validate_python({'kind':'a'}))
    except Exception as e:
        print(f'SchemaValidator choices={name}: {type(e).__name__}: {str(e)[:120]}')
PY
```

```console
SchemaValidator choices=dict: accepted -> {'kind': 'a'}
SchemaValidator choices=dict subclass: accepted -> {'kind': 'a'}
SchemaValidator choices=UserDict: SchemaError: Error building "tagged-union" validator:
  TypeError: 'UserDict' object is not an instance of 'dict'
SchemaValidator choices=MappingProxyType: SchemaError: Error building "tagged-union" validator:
  TypeError: 'mappingproxy' object is not an instance of 'dict'
```

The dict-subclass case is the quiet one: no error, just a different traversal (wrong order of `collected_references` / `deferred_discriminator_schemas`, or references collected for children `values()` never returned and none for the ones it did). Workaround: pass a plain `dict`.

## C3

Branch: [evalon/pydantic-s-00346963](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-00346963) (`40b210d19`). Verdict: **CONFIRMED** (both parts).

Ownership in `pydantic-core/src/schema_gather.rs` (read, then traced below): the work stack owns pending children (`Task::Visit(Bound<'py, PyAny>)`), but the marker left for a schema under traversal carries only its address, and `visit` drops its `schema` handle on return:

```rust
enum Task<'py> {
    Visit(Bound<'py, PyAny>),
    DeferDiscriminator(Bound<'py, PyDict>),
    Finish { schema_id: usize, start: usize },
}
// visit():
let schema_id = schema.as_ptr() as usize;
if let Some(&(start, end)) = self.visited.get(&schema_id) { /* mark span non-inlinable */ return Ok(()); }
self.visited.insert(schema_id, (start, None));
```

Probe ([verify/repro/c3_lazy_chain_address_reuse.py](repro/c3_lazy_chain_address_reuse.py)): the caller holds only the root. Every node is `{'type': 'chain', 'steps': LazySteps(...)}`; `LazySteps.__iter__` builds the single child when iterated and keeps no reference, so only the gatherer can keep a generated node alive. The innermost child is `{'type': 'definition-ref', 'schema_ref': 'terminal'}` with `'terminal'` present in the definitions. The trace logs node creation with `id()`, the moment a node is traversed (its `steps` get iterated), and deallocation. It runs twice: with dict-subclass nodes (`__del__` + weakrefs, for lifetimes) and with plain dict nodes (addresses only).

```sh
cd /home/ubuntu/repos/wt-00346963
/opt/venv-00346963/bin/python /home/ubuntu/repos/pydantic/verify/repro/c3_lazy_chain_address_reuse.py native 8
```

```console
=== impl=native depth=8: lifetime trace (dict-subclass nodes with __del__ / weakref) ===
    create depth=0 id=0x7459e2d2ab20 ancestors alive=[] freed=[]
    visit  depth=0 (its steps are being iterated)
    create depth=1 id=0x7459e2d2abc0 ancestors alive=[0] freed=[]
    visit  depth=1 (its steps are being iterated)
    create depth=2 id=0x7459e2d2ac60 ancestors alive=[0, 1] freed=[]
    free   depth=1
    visit  depth=2 (its steps are being iterated)
    create depth=3 id=0x7459e2d2abc0 ancestors alive=[0, 2] freed=[1] <-- SAME ADDRESS AS ANCESTOR depth=[1]
    free   depth=2
    free   depth=3
    gather returned
    collected_references = {}
    terminal reference present: False
=== impl=native depth=8: address trace (plain dict nodes) ===
    create depth=0 id=0x7459e2d23a80
    visit  depth=0 (its steps are being iterated)
    create depth=1 id=0x7459e2d0a9c0
    visit  depth=1 (its steps are being iterated)
    create depth=2 id=0x7459e2d34980
    visit  depth=2 (its steps are being iterated)
    create depth=3 id=0x7459e2d0a9c0 <-- SAME ADDRESS AS ANCESTOR depth=[1]
    gather returned
    collected_references = {}
    terminal reference present: False
RESULT impl=native: terminal present (subclass nodes)=False, (plain dict nodes)=False
exit=1
```

### ancestor_lifetime — CONFIRMED

`free   depth=1` is logged right after depth 1 was traversed and before depth 2 is traversed; when depth 3 is created the weakref census reads `ancestors alive=[0, 2] freed=[1]`. Depth 1 is an ancestor whose descendants (2, 3, …, terminal) are still pending, and its `Finish` marker is still on the stack. Only the root (held by the caller) and the node whose `visit` is running stay alive.

### address_reuse_trigger — CONFIRMED

In both runs the depth-3 node is created at the address of the freed depth-1 ancestor (`<-- SAME ADDRESS AS ANCESTOR depth=[1]`). There is no `visit  depth=3` line afterwards: its `steps` are never iterated, so depths 4..8 and the terminal `definition-ref` are never even created; gathering returns normally with `collected_references = {}` and no exception. Five further runs at depth 50 gave the same result every time:

```sh
for i in 1 2 3 4 5; do /opt/venv-00346963/bin/python /home/ubuntu/repos/pydantic/verify/repro/c3_lazy_chain_address_reuse.py native 50 | tail -n 1; done
```

```console
RESULT impl=native: terminal present (subclass nodes)=False, (plain dict nodes)=False
RESULT impl=native: terminal present (subclass nodes)=False, (plain dict nodes)=False
RESULT impl=native: terminal present (subclass nodes)=False, (plain dict nodes)=False
RESULT impl=native: terminal present (subclass nodes)=False, (plain dict nodes)=False
RESULT impl=native: terminal present (subclass nodes)=False, (plain dict nodes)=False
```

Control, same probe against the pre-change pure-Python gatherer (ancestors are held by the Python call stack; no address is reused; terminal collected):

```sh
/opt/venv-00346963/bin/python /home/ubuntu/repos/pydantic/verify/repro/c3_lazy_chain_address_reuse.py reference 8
```

```console
=== impl=reference depth=8: lifetime trace (dict-subclass nodes with __del__ / weakref) ===
    create depth=0 id=0x7d4849552b70 ancestors alive=[] freed=[]
    visit  depth=0 (its steps are being iterated)
    create depth=1 id=0x7d4849552c10 ancestors alive=[0] freed=[]
    visit  depth=1 (its steps are being iterated)
    create depth=2 id=0x7d4849552cb0 ancestors alive=[0, 1] freed=[]
    visit  depth=2 (its steps are being iterated)
    create depth=3 id=0x7d4849552d50 ancestors alive=[0, 1, 2] freed=[]
    visit  depth=3 (its steps are being iterated)
    create depth=4 id=0x7d4849552df0 ancestors alive=[0, 1, 2, 3] freed=[]
    visit  depth=4 (its steps are being iterated)
    create depth=5 id=0x7d4849552e90 ancestors alive=[0, 1, 2, 3, 4] freed=[]
    visit  depth=5 (its steps are being iterated)
    create depth=6 id=0x7d4849552f30 ancestors alive=[0, 1, 2, 3, 4, 5] freed=[]
    visit  depth=6 (its steps are being iterated)
    create depth=7 id=0x7d4849552fd0 ancestors alive=[0, 1, 2, 3, 4, 5, 6] freed=[]
    visit  depth=7 (its steps are being iterated)
    create depth=8 id=0x7d4849553070 ancestors alive=[0, 1, 2, 3, 4, 5, 6, 7] freed=[]
    visit  depth=8 (its steps are being iterated)
    create terminal definition-ref id=0x7d484955c9c0
    free   depth=8
    free   depth=7
    free   depth=6
    free   depth=5
    free   depth=4
    free   depth=3
    free   depth=2
    free   depth=1
    gather returned
    collected_references = {'terminal': {'type': 'definition-ref', 'schema_ref': 'terminal'}}
    terminal reference present: True
=== impl=reference depth=8: address trace (plain dict nodes) ===
    create depth=0 id=0x7d484955d100
    visit  depth=0 (its steps are being iterated)
    create depth=1 id=0x7d484954b980
    visit  depth=1 (its steps are being iterated)
    create depth=2 id=0x7d4849531b40
    visit  depth=2 (its steps are being iterated)
    create depth=3 id=0x7d4849532940
    visit  depth=3 (its steps are being iterated)
    create depth=4 id=0x7d484955d140
    visit  depth=4 (its steps are being iterated)
    create depth=5 id=0x7d484955d080
    visit  depth=5 (its steps are being iterated)
    create depth=6 id=0x7d484955c840
    visit  depth=6 (its steps are being iterated)
    create depth=7 id=0x7d484955c880
    visit  depth=7 (its steps are being iterated)
    create depth=8 id=0x7d484955c8c0
    visit  depth=8 (its steps are being iterated)
    create terminal definition-ref id=0x7d484955c940
    gather returned
    collected_references = {'terminal': {'type': 'definition-ref', 'schema_ref': 'terminal'}}
    terminal reference present: True
RESULT impl=reference: terminal present (subclass nodes)=True, (plain dict nodes)=True
exit=0
```

Causal check by mutation ([verify/instrumentation/c3_finish_keeps_schema_alive.patch](instrumentation/c3_finish_keeps_schema_alive.patch)): make `Task::Finish` own the schema it marks, rebuild, re-run. Nothing else changes; the ancestors now stay alive, no address is reused, and the terminal reference is collected. The patch was reverted and the extension rebuilt afterwards; the outputs above are from the unmodified branch.

```diff
diff --git a/pydantic-core/src/schema_gather.rs b/pydantic-core/src/schema_gather.rs
index 442fa6584..5aef4e888 100644
--- a/pydantic-core/src/schema_gather.rs
+++ b/pydantic-core/src/schema_gather.rs
@@ -17,7 +17,12 @@ enum Task<'py> {
     /// Register a schema as having the discriminator application deferred.
     DeferDiscriminator(Bound<'py, PyDict>),
     /// Mark the traversal of the schema with the given ID as completed.
-    Finish { schema_id: usize, start: usize },
+    Finish {
+        schema_id: usize,
+        start: usize,
+        // verify instrumentation: keep the schema alive until its traversal is finished
+        _keep_alive: Bound<'py, PyAny>,
+    },
 }
 
 struct Gatherer<'py> {
@@ -42,7 +47,7 @@ impl<'py> Gatherer<'py> {
             match task {
                 Task::Visit(schema) => self.visit(schema)?,
                 Task::DeferDiscriminator(schema) => self.deferred_discriminator_schemas.append(schema)?,
-                Task::Finish { schema_id, start } => {
+                Task::Finish { schema_id, start, .. } => {
                     self.visited
                         .insert(schema_id, (start, Some(self.encountered_refs.len())));
                 }
@@ -76,7 +81,11 @@ impl<'py> Gatherer<'py> {
             .and_then(|s| s.to_str().ok())
             .unwrap_or_default();
 
-        self.stack.push(Task::Finish { schema_id, start });
+        self.stack.push(Task::Finish {
+            schema_id,
+            start,
+            _keep_alive: schema.clone().into_any(),
+        });
 
         if schema_type == "definition-ref" {
             return self.visit_definition_ref(schema);
```

```sh
cd /home/ubuntu/repos/wt-00346963
git apply /home/ubuntu/repos/pydantic/verify/instrumentation/c3_finish_keeps_schema_alive.patch
maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
/opt/venv-00346963/bin/python /home/ubuntu/repos/pydantic/verify/repro/c3_lazy_chain_address_reuse.py native 4
git checkout -- pydantic-core/src/schema_gather.rs && maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
```

```console
=== impl=native depth=4: lifetime trace (dict-subclass nodes with __del__ / weakref) ===
    create depth=0 id=0x7484fcd4ebc0 ancestors alive=[] freed=[]
    visit  depth=0 (its steps are being iterated)
    create depth=1 id=0x7484fcd4ec60 ancestors alive=[0] freed=[]
    visit  depth=1 (its steps are being iterated)
    create depth=2 id=0x7484fcd4ed00 ancestors alive=[0, 1] freed=[]
    visit  depth=2 (its steps are being iterated)
    create depth=3 id=0x7484fcd4eda0 ancestors alive=[0, 1, 2] freed=[]
    visit  depth=3 (its steps are being iterated)
    create depth=4 id=0x7484fcd4ee40 ancestors alive=[0, 1, 2, 3] freed=[]
    visit  depth=4 (its steps are being iterated)
    create terminal definition-ref id=0x7484fcd58680
    free   depth=4
    free   depth=3
    free   depth=2
    free   depth=1
    gather returned
    collected_references = {'terminal': {'type': 'definition-ref', 'schema_ref': 'terminal'}}
    terminal reference present: True
=== impl=native depth=4: address trace (plain dict nodes) ===
    create depth=0 id=0x7484fcd58e00
    visit  depth=0 (its steps are being iterated)
    create depth=1 id=0x7484fcd2d840
    visit  depth=1 (its steps are being iterated)
    create depth=2 id=0x7484fcd2e640
    visit  depth=2 (its steps are being iterated)
    create depth=3 id=0x7484fcd58580
    visit  depth=3 (its steps are being iterated)
    create depth=4 id=0x7484fcd585c0
    visit  depth=4 (its steps are being iterated)
    create terminal definition-ref id=0x7484fcd58600
    gather returned
    collected_references = {'terminal': {'type': 'definition-ref', 'schema_ref': 'terminal'}}
    terminal reference present: True
RESULT impl=native: terminal present (subclass nodes)=True, (plain dict nodes)=True
exit=0
```

Checks do not see this: the eval fixtures contain no lazily generated nested schema (`test_iterables` uses a generator over an externally held `definition-ref`). On this branch the traversal and lifecycle fixture files give `19 failed, 5 passed`; all 19 failures are the unrelated `values()` / `__iter__` protocol assertions (`test_mapping_values_protocol`, 18 × `test_sequence_and_metadata_protocol`), and `test_all_schema_kinds`, `test_iterables` and the three lifecycle tests pass.

```sh
cd /home/ubuntu/repos/wt-00346963 && cp ~/eval_tests/tests/test_eval_*.py tests/
/opt/venv-00346963/bin/python -m pytest tests/test_eval_schema_gather_traversal.py tests/test_eval_schema_gather_lifecycle.py -q -p no:cacheprovider -p no:pretty --tb=no | tail -n 1
/opt/venv-00346963/bin/python -m pytest tests/test_eval_schema_gather_traversal.py tests/test_eval_schema_gather_lifecycle.py -q -p no:cacheprovider -p no:pretty --tb=no -k "test_iterables or test_all_schema_kinds or lifecycle" | tail -n 1
```

```console
19 failed, 5 passed in 0.33s
5 passed, 19 deselected in 0.12s
```

Scope observation, not part of the claim ([verify/instrumentation/c3_extra_finished_sibling_address_reuse.py](instrumentation/c3_extra_finished_sibling_address_reuse.py)): a lazily generated schema can also land on the address of an already *finished* and freed sibling and be skipped through its closed span. The pre-change Python gatherer does exactly the same, so that case is inherited behavior, not something this branch introduced; only the active-ancestor case above is new.

```sh
cd /home/ubuntu/repos/wt-00346963
/opt/venv-00346963/bin/python /home/ubuntu/repos/pydantic/verify/instrumentation/c3_extra_finished_sibling_address_reuse.py native
/opt/venv-00346963/bin/python /home/ubuntu/repos/pydantic/verify/instrumentation/c3_extra_finished_sibling_address_reuse.py reference
```

```console
create branch A id=0x72c412329700
create branch B id=0x72c412343f40
create definition-ref ref_A id=0x72c412343f00
create definition-ref ref_B id=0x72c412329700
collected_references = {'ref_A': None}
RESULT: WRONG (expected ref_A and ref_B both collected and inlinable)
exit=1
create branch A id=0x7ab252b31300
create definition-ref ref_A id=0x7ab252b313c0
create branch B id=0x7ab252b4bb80
create definition-ref ref_B id=0x7ab252b31300
collected_references = {'ref_A': None}
RESULT: WRONG (expected ref_A and ref_B both collected and inlinable)
exit=1
```

Impact reasoning: the result is silently wrong rather than an error: gathering returns successfully with the terminal reference (and everything below the third lazily generated level) missing, so a caller would neither inline nor validate that reference and a missing definition under it would not raise `MissingDefinitionError`. The pre-change gatherer handles the same input correctly. The trigger is narrow: it needs child schemas that exist only while being iterated (a custom iterable/mapping building schema dicts on the fly, nested at least three levels with no other owner). Schemas generated by Pydantic are plain dict/list trees fully owned by the root, where every ancestor is kept alive by its parent, so ordinary model building does not hit this. Workaround: materialize the schema tree (keep references to generated children) before gathering.
