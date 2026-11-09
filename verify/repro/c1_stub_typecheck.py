# Run: cd <worktree of evalon/pydantic-s-b140b048> && /opt/venv-b140b048/bin/pyright verify/repro/c1_stub_typecheck.py  (expect 0 errors: the stub permits a function)
from typing import Any

from pydantic_core._pydantic_core import gather_schemas_for_cleaning


def function_factory(ref: Any) -> LookupError:
    return LookupError(ref)


gather_schemas_for_cleaning({'type': 'int'}, {}, missing_definition_error=function_factory)
gather_schemas_for_cleaning({'type': 'int'}, {}, missing_definition_error=lambda ref: KeyError(ref))
gather_schemas_for_cleaning({'type': 'int'}, {}, missing_definition_error=KeyError)
# Control: a non-callable must be flagged by the type checker, proving the stub is what is being checked.
gather_schemas_for_cleaning({'type': 'int'}, {}, missing_definition_error=42)  # expected error
