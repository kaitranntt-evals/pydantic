## C1

Target branch: [evalon/pydantic-s-94fa2c73](https://github.com/kaitranntt-evals/pydantic-schema-gather-to-core/tree/evalon/pydantic-s-94fa2c73) at `0cc19d6ca21b75d58ebed367967261385253cee1` (worktree `../pyd-claim`), control: eval base `a2c935478b7f4d51d6d781d1c95339c8d69c05d0` (worktree `../pyd-base`).

Verdict: CONFIRMED (both parts held).

### Setup

```sh
cd /home/ubuntu/repos/pydantic
git remote add claims https://git-manager.itsdev.in/proxy/github.com/kaitranntt-evals/pydantic-schema-gather-to-core
git fetch claims evalon/pydantic-s-94fa2c73
git worktree add --detach ../pyd-claim claims/evalon/pydantic-s-94fa2c73
git worktree add --detach ../pyd-base a2c935478
uv venv /opt/venv-tools --python 3.13 && VIRTUAL_ENV=/opt/venv-tools uv pip install pyright==1.1.411 mypy==2.3.0 typing-extensions
# runtime build of the claim branch
cd ../pyd-claim
export VIRTUAL_ENV=/opt/venv-claim UV_PROJECT_ENVIRONMENT=/opt/venv-claim PATH=/opt/venv-claim/bin:$PATH
uv venv /opt/venv-claim --python 3.13 && uv pip install maturin==1.15.0 pytest==9.1.1 pytest-timeout==2.3.1
uv sync --frozen --all-packages --all-extras --group testing-extra
maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen
```

The probe is `verify/repro/c1_schemaerror_subclass.py` (`class Derived(SchemaError): pass` via the public `pydantic_core` import and via `pydantic_core._pydantic_core`), driven by `verify/repro/c1_run.sh`.

### Part typing_declaration — holds

Where the decorator went (the branch inserted the new class and function between the existing `@final` and `class SchemaError`):

```sh
git -C ../pyd-claim diff a2c935478 HEAD -- pydantic-core/python/pydantic_core/_pydantic_core.pyi
```

```diff
diff --git a/pydantic-core/python/pydantic_core/_pydantic_core.pyi b/pydantic-core/python/pydantic_core/_pydantic_core.pyi
index 12b8e4d49..9c4aa4a52 100644
--- a/pydantic-core/python/pydantic_core/_pydantic_core.pyi
+++ b/pydantic-core/python/pydantic_core/_pydantic_core.pyi
@@ -19,6 +19,8 @@ __all__ = [
     'Url',
     'MultiHostUrl',
     'SchemaError',
+    'SchemaGatherMissingDefinitionError',
+    'gather_schemas_for_cleaning',
     'ValidationError',
     'PydanticCustomError',
     'PydanticKnownError',
@@ -698,6 +700,21 @@ class MultiHostUrl(SupportsAllComparisons):
     ) -> Self: ...
 
 @final
+class SchemaGatherMissingDefinitionError(LookupError):
+    """A `'definition-ref'` schema was pointing to a non-existing definition.
+
+    The missing reference is the first argument.
+    """
+
+def gather_schemas_for_cleaning(schema: CoreSchema, definitions: dict[str, CoreSchema]) -> dict[str, Any]:
+    """Iteratively traverse a core schema and its definitions to gather the information needed for schema cleaning.
+
+    Returns a dict with the `'collected_references'` and `'deferred_discriminator_schemas'` keys.
+
+    Raises:
+        SchemaGatherMissingDefinitionError: If a `'definition-ref'` schema points to a missing definition.
+    """
+
 class SchemaError(Exception):
     """
     Information about errors that occur while building a [`SchemaValidator`][pydantic_core.SchemaValidator]
```

Type checkers on the claim branch plus runtime (`verify/repro/c1_run.sh ../pyd-claim /opt/venv-claim`, full output in `verify/logs/c1_claim_full.txt`):

```console
== declaration (/home/ubuntu/repos/pyd-claim)
701-
702-@final
703:class SchemaGatherMissingDefinitionError(LookupError):
--
716-    """
717-
718:class SchemaError(Exception):
== pyright
/tmp/tmp.HqmUsiyvBS/probe.py
  /tmp/tmp.HqmUsiyvBS/probe.py:3:27 - error: "_pydantic_core" is private and used outside of the module in which it is declared (reportPrivateUsage)
1 error, 0 warnings, 0 informations
WARNING: there is a new pyright version available (v1.1.411 -> v1.1.414).
Please install the new version or set PYRIGHT_PYTHON_FORCE_VERSION to `latest`

pyright exit=1
== mypy
Success: no issues found in 1 source file
mypy exit=0
== runtime
/home/ubuntu/repos/pyd-claim/pydantic-core/python/pydantic_core/__init__.py
Py_TPFLAGS_BASETYPE set: False
Traceback (most recent call last):
  File "/tmp/tmp.HqmUsiyvBS/probe.py", line 6, in <module>
    class Derived(SchemaError):
        pass
TypeError: type 'pydantic_core._pydantic_core.SchemaError' is not an acceptable base type
python exit=1
```

The only pyright diagnostic is `reportPrivateUsage` for the deliberate private-module import on line 3 (strict mode); neither subclass definition (lines 6 and 10) is reported, and mypy reports nothing.

Control, eval base declarations (`verify/repro/c1_run.sh ../pyd-base`, `verify/logs/c1_typecheck_pyd-base.txt`) — both checkers reject the same file:

```console
== declaration (/home/ubuntu/repos/pyd-base)
699-
700-@final
701:class SchemaError(Exception):
== pyright
/tmp/tmp.0e8HCaqklr/probe.py
  /tmp/tmp.0e8HCaqklr/probe.py:3:27 - error: "_pydantic_core" is private and used outside of the module in which it is declared (reportPrivateUsage)
  /tmp/tmp.0e8HCaqklr/probe.py:3:27 - warning: Import "pydantic_core._pydantic_core" could not be resolved from source (reportMissingModuleSource)
  /tmp/tmp.0e8HCaqklr/probe.py:6:15 - error: Base class "SchemaError" is marked final and cannot be subclassed (reportGeneralTypeIssues)
  /tmp/tmp.0e8HCaqklr/probe.py:10:21 - error: Base class "SchemaError" is marked final and cannot be subclassed (reportGeneralTypeIssues)
3 errors, 1 warning, 0 informations
WARNING: there is a new pyright version available (v1.1.411 -> v1.1.414).
Please install the new version or set PYRIGHT_PYTHON_FORCE_VERSION to `latest`

pyright exit=1
== mypy
probe.py:6: error: Cannot inherit from final class "SchemaError"  [misc]
probe.py:10: error: Cannot inherit from final class "SchemaError"  [misc]
Found 2 errors in 1 file (checked 1 source file)
mypy exit=1
```

### Part runtime_restriction — holds

From the run above against the claim branch's own native build: `Py_TPFLAGS_BASETYPE set: False` and
`TypeError: type 'pydantic_core._pydantic_core.SchemaError' is not an acceptable base type` (python exit=1).

Runtime class configuration is untouched by the branch (no `subclass` in the `#[pyclass]`):

```sh
git -C ../pyd-claim diff a2c935478 HEAD --stat -- pydantic-core/src/build_tools.rs   # prints nothing
grep -n -A1 'pyclass(extends=PyException' ../pyd-claim/pydantic-core/src/build_tools.rs
```

```console
56:#[pyclass(extends=PyException, module="pydantic_core._pydantic_core")]
57-pub struct SchemaError(SchemaErrorEnum);
```

### Impact reasoning

The branch regressed the stub: at the eval base `SchemaError` is `@final` and pyright/mypy reject subclassing; on the branch the `@final` now decorates the new `SchemaGatherMissingDefinitionError` and `SchemaError` is left undecorated. A consumer writing `class MySchemaError(SchemaError)` gets a clean type check and then a `TypeError` at import time of their module. Subclassing a library exception is an ordinary thing to try; the failure is loud and immediate at runtime, and the workaround is simply not to subclass. No runtime behavior of pydantic itself changes. The fix is a one-line stub edit (restore `@final` above `class SchemaError`).
