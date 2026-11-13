# Run: verify/repro/c1_run.sh <worktree-of-branch> <venv-with-that-branch's-pydantic_core-built>  (type-checks this file with pyright+mypy, then executes it)
from pydantic_core import SchemaError
from pydantic_core import _pydantic_core


class Derived(SchemaError):
    pass


class DerivedDirect(_pydantic_core.SchemaError):
    pass


print('subclass definitions executed without error:', Derived.__mro__)
