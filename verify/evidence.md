Audit of `pydantic-schema-gather-to-core-perfect` (and the claim-target branches) — observations only.

## Environment used for every section

`/opt/venv` did not exist in this session's VM, so it was recreated with the commands of the eval's `startup.sh` (the checkout-altering `git reset` skipped). One checkout and one venv per branch:

| Checkout | Revision | venv |
|---|---|---|
| `/home/ubuntu/repos/pydantic` | `origin/pydantic-schema-gather-to-core-perfect` | `/opt/venv` |
| `/home/ubuntu/repos/pyd-41fd` | `evalon/pydantic-s-41fd7c4c` (f9125535d) from `kaitranntt-evals/pydantic-schema-gather-to-core` | `/opt/venv-41fd` |
| `/home/ubuntu/repos/pyd-e635` | `evalon/pydantic-s-e6353b87` (4779c9070), same repo | not built (stubs only) |
| `/home/ubuntu/repos/pyd-base` | eval base `a2c935478` (control) | `/opt/venv-base` |

```sh
cd /home/ubuntu/repos/pydantic
git remote add claims https://git-manager.itsdev.in/proxy/github.com/kaitranntt-evals/pydantic-schema-gather-to-core
git fetch claims evalon/pydantic-s-41fd7c4c evalon/pydantic-s-e6353b87
git worktree add --detach ../pyd-41fd claims/evalon/pydantic-s-41fd7c4c
git worktree add --detach ../pyd-e635 claims/evalon/pydantic-s-e6353b87
git worktree add --detach ../pyd-base a2c935478b7f4d51d6d781d1c95339c8d69c05d0
# per checkout <dir>/<venv>:
sudo mkdir -p <venv> && sudo chown -R "$(whoami)" <venv> && cd <dir>
export VIRTUAL_ENV=<venv> UV_PROJECT_ENVIRONMENT=<venv>
uv venv <venv> --python 3.13
uv pip install maturin==1.15.0 pytest==9.1.1 pytest-timeout==2.3.1
uv sync --frozen --all-packages --all-extras --group testing-extra
<venv>/bin/maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
```

Eval fixtures (byte-exact from `eval_tests.zip`, copied to `tests/`, not committed): 84 passed on the audited branch; on `evalon/pydantic-s-41fd7c4c` 50 passed / 34 failed.

## C1

Claim: schema cleaning leaves definitions referenced only by a model's `extras_keys_schema` unresolved. Target: `pydantic-schema-gather-to-core-perfect`.

Source facts (context, not the evidence): `collect_child_schemas` in `pydantic-core/src/schema_gather.rs` handles `"model-fields" | "typed-dict"` with `extras_schema`, `computed_fields`, `fields` only; `GenerateSchema._model_schema` (`pydantic/_internal/_generate_schema.py`) sets `extras_keys_schema = self.generate_schema(extra_keys_type)` when the `__pydantic_extra__` key type is not `str`; `ModelFieldsValidator::build` (`pydantic-core/src/validators/model_fields.rs:74`) builds a validator from it.

```sh
cd /home/ubuntu/repos/pydantic
/opt/venv/bin/python verify/repro/c1_extras_keys_schema.py 2>&1 | grep -v "^  \|^Traceback\|^pydantic_core._pydantic_core.SchemaError"
```

```console
== part child_collection: direct gather of a model-fields schema
collected_references keys: ['ValDef']
KeyDef collected: False
gather with KeyDef missing from definitions -> {'collected_references': {}, 'deferred_discriminator_schemas': []} (no MissingDefinitionError)
== part production_trigger: real models
-- extra key type: Enum
core schema type: model | extras_keys_schema: {'type': 'enum', 'cls': '...', 'members': '...', 'ref': '...', 'metadata': '...'}
definition-ref left in cleaned schema: []
validator class: SchemaValidator
validate FAILED: TypeError 'Color' object is not an instance of 'str'
SchemaValidator(core_schema) built OK
-- extra key type: dataclass
class creation FAILED: SchemaError Definitions error: definition `__main__.Key:712569712` was never filled
-- extra key type: BaseModel
class creation FAILED: SchemaError Definitions error: definition `__main__.Sub:713790704` was never filled
== control: same dataclass as the extra *value* type (extras_schema edge is traversed)
Ok built; validate: {'a': Key(x=1)}
== what GenerateSchema hands to schema cleaning (before clean_schema)
schema passed to finalize_schema: {'type': 'definition-ref', 'schema_ref': '__main__.M2:714091664'}
definition '__main__.M2:714091664' -> model-fields extras_keys_schema (pre-clean): {'type': 'definition-ref', 'schema_ref': '__main__.Key:712569712'}
pre-clean definitions: ['__main__.Key:712569712', '__main__.M2:714091664']
gather collected_references keys: ['__main__.M2:714091664']
post-clean type: model | extras_keys_schema: {'type': 'definition-ref', 'schema_ref': '__main__.Key:712569712'}
class creation FAILED: SchemaError Definitions error: definition `__main__.Key:712569712` was never filled
```

Reading of the output, per part:

- *child_collection* — holds. A direct gather of a `model-fields` schema with both `extras_schema` and `extras_keys_schema` references collects only `ValDef`; `KeyDef` is never visited, and a `KeyDef` missing from `definitions` raises no `MissingDefinitionError`.
- *production_trigger* — holds. `class M(BaseModel, extra='allow'): __pydantic_extra__: dict[Key, int]` (frozen dataclass or frozen `BaseModel` as key type) reaches `_Definitions.finalize_schema` with `extras_keys_schema == {'type': 'definition-ref', ...}`; gather collects only the model's own reference, the cleaned schema still carries the `definition-ref` with the `Key` definition dropped, and validator construction fails with `SchemaError: Definitions error: definition ... was never filled`, so the class statement itself raises. An `Enum` key type does not trigger it (its schema is generated inline, no `definition-ref`). The same dataclass as the extra *value* type (`dict[str, Key]`) works.

Control on the eval base `a2c935478` (pure-Python gather), same script up to the model part:

```sh
cd /home/ubuntu/repos/pyd-base
/opt/venv-base/bin/python ../pydantic/verify/repro/c1_extras_keys_schema.py 2>&1 | grep -v "^  \|^Traceback\|^pydantic_core._pydantic_core.SchemaError"
```

```console
### base a2c935478 (control)
== part child_collection: direct gather of a model-fields schema
collected_references keys: ['ValDef']
KeyDef collected: False
gather with KeyDef missing from definitions -> {'collected_references': {}, 'deferred_discriminator_schemas': []} (no MissingDefinitionError)
== part production_trigger: real models
-- extra key type: Enum
core schema type: model | extras_keys_schema: {'type': 'enum', 'cls': '...', 'members': '...', 'ref': '...', 'metadata': '...'}
definition-ref left in cleaned schema: []
validator class: SchemaValidator
validate FAILED: TypeError 'Color' object is not an instance of 'str'
SchemaValidator(core_schema) built OK
-- extra key type: dataclass
class creation FAILED: SchemaError Definitions error: definition `__main__.Key:1012320880` was never filled
-- extra key type: BaseModel
class creation FAILED: SchemaError Definitions error: definition `__main__.Sub:1012803344` was never filled
```

Impact reasoning: the behaviour is identical at the eval base, so the Rust port preserved an existing gap rather than introducing one. A user hits it only with a non-`str`, referenceable key type on `__pydantic_extra__` (dataclass, model, and other types whose schema carries a `ref`); the failure is loud (class definition raises `SchemaError`), with no workaround short of a key type that is generated inline. None of the eval fixtures mention `extras_keys_schema` (`grep -rn extras_keys_schema` over the extracted archive returns nothing), and all 84 pass on this branch.

## C2

Claim: gathering accepts `arguments` / `arguments-v3` schemas without `arguments_schema`. Target: `evalon/pydantic-s-41fd7c4c`.

```sh
cd /home/ubuntu/repos/pyd-41fd
/opt/venv-41fd/bin/python ../pydantic/verify/repro/c2_c4_missing_children.py
```

```console
### evalon/pydantic-s-41fd7c4c (f9125535d)
schema_gather module: /home/ubuntu/repos/pyd-41fd/pydantic/_internal/_schema_gather.py
pure-Python traverse_schema present: False
== C2: arguments / arguments-v3
{'type': 'arguments'}                                   -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
{'type': 'arguments-v3'}                                -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
control {'type': 'arguments', 'arguments_schema': []}   -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
control {'type': 'arguments-v3', 'arguments_schema': []} -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
control {'type': 'call'} (required arguments_schema)    -> RAISED KeyError('arguments_schema')
== C4: lax-or-strict / json-or-python, one required child omitted at a time
lax-or-strict without lax_schema                        -> RAISED KeyError('lax_schema/strict_schema')
lax-or-strict without strict_schema                     -> RAISED KeyError('lax_schema/strict_schema')
json-or-python without json_schema                      -> RAISED KeyError('json_schema/python_schema')
json-or-python without python_schema                    -> RAISED KeyError('json_schema/python_schema')
control lax-or-strict complete                          -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
control json-or-python complete                         -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
```

Both `{'type': 'arguments'}` and `{'type': 'arguments-v3'}` return successfully; the explicit-empty controls return the same result, and `call` (whose `arguments_schema` is looked up with `ok_or_else(missing_key)`) still raises. `push_arguments` in that branch's `pydantic-core/src/schema_gather.rs` wraps the lookup in `if let Some(args) = schema.get_item("arguments_schema")?`.

Controls — eval base (pure Python, `for s in schema['arguments_schema']`) and the audited `-perfect` branch both raise:

```console
### base a2c935478 (pure-Python gather, control)
schema_gather module: /home/ubuntu/repos/pyd-base/pydantic/_internal/_schema_gather.py
pure-Python traverse_schema present: True
== C2: arguments / arguments-v3
{'type': 'arguments'}                                   -> RAISED KeyError('arguments_schema')
{'type': 'arguments-v3'}                                -> RAISED KeyError('arguments_schema')
control {'type': 'arguments', 'arguments_schema': []}   -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
control {'type': 'arguments-v3', 'arguments_schema': []} -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
control {'type': 'call'} (required arguments_schema)    -> RAISED KeyError('arguments_schema')
```

```console
### pydantic-schema-gather-to-core-perfect (control)
schema_gather module: /home/ubuntu/repos/pydantic/pydantic/_internal/_schema_gather.py
pure-Python traverse_schema present: False
== C2: arguments / arguments-v3
{'type': 'arguments'}                                   -> RAISED KeyError('arguments_schema')
{'type': 'arguments-v3'}                                -> RAISED KeyError('arguments_schema')
control {'type': 'arguments', 'arguments_schema': []}   -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
control {'type': 'arguments-v3', 'arguments_schema': []} -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
control {'type': 'call'} (required arguments_schema)    -> RAISED KeyError('arguments_schema')
```

Fixture coverage: `tests/test_eval_schema_gather_errors.py` on this branch — 26 passed, 13 failed, and all 13 failures are the `test_surrogate_*` / `test_multiple_distinct_surrogate_references` cases (`UnicodeEncodeError ... surrogates not allowed`); nothing in it fails on the missing `arguments_schema`.

```sh
cd /home/ubuntu/repos/pyd-41fd && cp ~/fx/tests/test_eval_*.py tests/
/opt/venv-41fd/bin/python -m pytest tests/test_eval_schema_gather_errors.py -q -p no:cacheprovider -p no:sugar -o addopts="" -rf --tb=line
```

Impact reasoning: only malformed schemas are affected — a schema `pydantic-core` itself would reject at validator build — so no well-formed model changes behaviour; the difference is that the previous `KeyError` during cleaning is silently swallowed.

## C3

Claim: the delivered stubs no longer mark `Some` as final. Target: `evalon/pydantic-s-e6353b87`.

```sh
uv venv /opt/venv-tools --python 3.13
VIRTUAL_ENV=/opt/venv-tools uv pip install pyright==1.1.411 mypy==2.3.0 typing-extensions
cd /home/ubuntu/repos/pydantic && bash verify/repro/c3_run.sh
```

```console
===== stubs from /home/ubuntu/repos/pyd-e635 (4779c9070)
68-    """The list of core schemas having the discriminator application deferred."""
69-
70:class Some(Generic[_T]):
 * Install prebuilt node (26.13.1) ..... done.
0 errors, 0 warnings, 0 informations
WARNING: there is a new pyright version available (v1.1.411 -> v1.1.414).
Please install the new version or set PYRIGHT_PYTHON_FORCE_VERSION to `latest`

pyright exit=0
/home/ubuntu/repos/pyd-e635/pydantic-core/python/pydantic_core/core_schema.py:4734: error: "object" has no attribute "__name__"; maybe "__ne__" or "__new__"?  [attr-defined]
Found 1 error in 1 file (checked 1 source file)
mypy exit=1
===== stubs from /home/ubuntu/repos/pyd-base (a2c935478)
46-
47-@final
48:class Some(Generic[_T]):
/tmp/tmp.AzxmdMxusE/c3_some_subclass.py
  /tmp/tmp.AzxmdMxusE/c3_some_subclass.py:5:14 - error: Base class "Some[int]" is marked final and cannot be subclassed (reportGeneralTypeIssues)
1 error, 0 warnings, 0 informations
WARNING: there is a new pyright version available (v1.1.411 -> v1.1.414).
Please install the new version or set PYRIGHT_PYTHON_FORCE_VERSION to `latest`

pyright exit=1
/home/ubuntu/repos/pyd-base/pydantic-core/python/pydantic_core/core_schema.py:4734: error: "object" has no attribute "__name__"; maybe "__ne__" or "__new__"?  [attr-defined]
c3_some_subclass.py:5: error: Cannot inherit from final class "Some"  [misc]
Found 2 errors in 2 files (checked 1 source file)
mypy exit=1
```

On the claim branch the `@final` decorator that preceded `class Some` now decorates the inserted `class GatherResult(TypedDict)`; `class Some(Generic[_T])` is left undecorated. pyright reports 0 errors for `class MySome(Some[int])`; mypy reports only an unrelated error in `core_schema.py:4734` that also appears with the base stubs. With the base stubs both checkers reject the subclass (`marked final and cannot be subclassed` / `Cannot inherit from final class "Some"`).

Runtime remains non-subclassable (the Rust class is unchanged), so the stub now disagrees with the extension:

```sh
/opt/venv/bin/python -c "
from pydantic_core import Some
try:
    class X(Some): pass
    print('runtime subclass OK')
except TypeError as e: print('runtime:', e)"
```

```console
runtime: type 'pydantic_core._pydantic_core.Some' is not an acceptable base type
```

## C4

Claim: a combined child-key label is reported instead of the exact missing key for `lax-or-strict` / `json-or-python`. Target: `evalon/pydantic-s-41fd7c4c`.

```sh
cd /home/ubuntu/repos/pyd-41fd
/opt/venv-41fd/bin/python ../pydantic/verify/repro/c2_c4_missing_children.py
```

```console
### evalon/pydantic-s-41fd7c4c (f9125535d)
== C4: lax-or-strict / json-or-python, one required child omitted at a time
lax-or-strict without lax_schema                        -> RAISED KeyError('lax_schema/strict_schema')
lax-or-strict without strict_schema                     -> RAISED KeyError('lax_schema/strict_schema')
json-or-python without json_schema                      -> RAISED KeyError('json_schema/python_schema')
json-or-python without python_schema                    -> RAISED KeyError('json_schema/python_schema')
control lax-or-strict complete                          -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
control json-or-python complete                         -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
```

All four omissions raise `KeyError` whose argument is the pair label (`'lax_schema/strict_schema'`, `'json_schema/python_schema'`), whichever key is absent. Controls — eval base and the audited `-perfect` branch name the exact key:

```console
### base a2c935478 (pure-Python gather, control)
== C4: lax-or-strict / json-or-python, one required child omitted at a time
lax-or-strict without lax_schema                        -> RAISED KeyError('lax_schema')
lax-or-strict without strict_schema                     -> RAISED KeyError('strict_schema')
json-or-python without json_schema                      -> RAISED KeyError('json_schema')
json-or-python without python_schema                    -> RAISED KeyError('python_schema')
control lax-or-strict complete                          -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
control json-or-python complete                         -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
```

```console
### pydantic-schema-gather-to-core-perfect (control)
== C4: lax-or-strict / json-or-python, one required child omitted at a time
lax-or-strict without lax_schema                        -> RAISED KeyError('lax_schema')
lax-or-strict without strict_schema                     -> RAISED KeyError('strict_schema')
json-or-python without json_schema                      -> RAISED KeyError('json_schema')
json-or-python without python_schema                    -> RAISED KeyError('python_schema')
control lax-or-strict complete                          -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
control json-or-python complete                         -> RETURNED {'collected_references': {}, 'deferred_discriminator_schemas': []}
```

Fixture coverage: same run as in C2 — `tests/test_eval_schema_gather_errors.py` on this branch has 13 failures, all surrogate-reference tests; none concerns the key label.

Impact reasoning: exception type is preserved (`KeyError`), only `e.args[0]` differs, and only for malformed schemas; code or tests comparing the key name see a different value.

## C5

Claim: `cargo test` from `pydantic-core` does not complete successfully in the solution's provided environment. Target: `pydantic-schema-gather-to-core-perfect`.

Environment as produced by `startup.sh` (which exports `VIRTUAL_ENV=/opt/venv`; `uv venv --python 3.13` resolved to a uv-managed CPython 3.13.18 because the VM's system Python is 3.10):

```sh
cd /home/ubuntu/repos/pydantic/pydantic-core
VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH cargo test
```

```console
$ cd pydantic-core && VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH cargo test
    Finished `test` profile [unoptimized + debuginfo] target(s) in 11.41s
     Running unittests src/lib.rs (target/debug/deps/_pydantic_core-f2e1cf6c33a04555)

running 1 test

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

     Running tests/test.rs (target/debug/deps/test-413e3b7290da75fd)
/home/ubuntu/repos/pydantic/pydantic-core/target/debug/deps/test-413e3b7290da75fd: error while loading shared libraries: libpython3.13.so.1.0: cannot open shared object file: No such file or directory
error: test failed, to rerun pass `--test test`

Caused by:
  process didn't exit successfully: `/home/ubuntu/repos/pydantic/pydantic-core/target/debug/deps/test-413e3b7290da75fd` (exit status: 127)
note: test exited abnormally; to see the full output pass --no-capture to the harness.
exit=127
```

```sh
ldd target/debug/deps/test-413e3b7290da75fd | grep python
```

```console
	libpython3.13.so.1.0 => not found
```

The lib unit-test binary runs (1 passed), then the `tests/test.rs` integration binary cannot load `libpython3.13.so.1.0`; `cargo test` exits 127 and the 3 integration tests and doc-tests never run.

Without the venv on `PATH` the build picks the system Python 3.10 and fails at link time:

```sh
cd /home/ubuntu/repos/pydantic/pydantic-core && cargo test
```

```console
  = note: rust-lld: error: unable to find library -lpython3.10
error: could not compile `pydantic-core` (lib test) due to 1 previous error
exit=101
```

Control 1 — same command with the interpreter's `LIBDIR` on the loader path passes:

```console
$ cd pydantic-core && VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH LD_LIBRARY_PATH=/home/ubuntu/.local/share/uv/python/cpython-3.13.18-linux-x86_64-gnu/lib cargo test
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.03s
     Running unittests src/lib.rs (target/debug/deps/_pydantic_core-f2e1cf6c33a04555)
running 1 test
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
     Running tests/test.rs (target/debug/deps/test-413e3b7290da75fd)
running 3 tests
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.04s
   Doc-tests _pydantic_core
running 0 tests
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
exit=0
```

Control 2 — the eval base commit fails the same way, so the failure is not caused by the solution's changes:

```console
$ (base a2c935478) cd pydantic-core && VIRTUAL_ENV=/opt/venv-base PATH=/opt/venv-base/bin:$PATH cargo test
    Finished `test` profile [unoptimized + debuginfo] target(s) in 12.09s
     Running unittests src/lib.rs (target/debug/deps/_pydantic_core-f2e1cf6c33a04555)
running 1 test
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
     Running tests/test.rs (target/debug/deps/test-413e3b7290da75fd)
/home/ubuntu/repos/pyd-base/pydantic-core/target/debug/deps/test-413e3b7290da75fd: error while loading shared libraries: libpython3.13.so.1.0: cannot open shared object file: No such file or directory
error: test failed, to rerun pass `--test test`
Caused by:
  process didn't exit successfully: `/home/ubuntu/repos/pyd-base/pydantic-core/target/debug/deps/test-413e3b7290da75fd` (exit status: 127)
note: test exited abnormally; to see the full output pass --no-capture to the harness.
exit=127
```

Impact reasoning: the claim's criterion (nonzero exit) is met, but the cause is the interpreter's shared library not being on the loader path of this recreated environment; it is identical at the base commit, and all Rust tests pass (1 + 3) once `LD_LIBRARY_PATH` is set. The original eval VM image was not available, so an image whose Python 3.13 ships `libpython3.13.so.1.0` on the default loader path would behave differently. Upstream CI (`core-test-os`, `.github/workflows/ci.yml:466`) runs `cargo test` after `setup-uv` on GitHub runners.
