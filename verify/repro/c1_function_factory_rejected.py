# Run: /opt/venv-b140b048/bin/python verify/repro/c1_function_factory_rejected.py   (cwd = worktree of evalon/pydantic-s-b140b048, native ext built)
"""C1: the stub types `missing_definition_error` as `Callable[[Any], BaseException] | None`, the runtime only takes a class."""

from __future__ import annotations

import functools
import inspect
import re
import traceback
from pathlib import Path

import pydantic_core
from pydantic_core._pydantic_core import gather_schemas_for_cleaning

from pydantic._internal._schema_gather import MissingDefinitionError

stub = Path(pydantic_core.__file__).with_name('_pydantic_core.pyi').read_text()
print('--- stub signature ---')
print(re.search(r'def gather_schemas_for_cleaning\(.*?\) -> [^\n]*', stub, re.S).group(0))
print('--- runtime text signature ---')
print(gather_schemas_for_cleaning.__text_signature__, inspect.signature(gather_schemas_for_cleaning))

schema = {'type': 'definition-ref', 'schema_ref': 'missing'}


def function_factory(ref):
    return MissingDefinitionError(ref)


class CallableInstance:
    def __call__(self, ref):
        return MissingDefinitionError(ref)


candidates = {
    'class MissingDefinitionError': MissingDefinitionError,
    'def function_factory': function_factory,
    'lambda': lambda ref: MissingDefinitionError(ref),
    'functools.partial(MissingDefinitionError)': functools.partial(MissingDefinitionError),
    'callable instance': CallableInstance(),
    'None (default)': None,
}

failures = 0
for label, factory in candidates.items():
    try:
        gather_schemas_for_cleaning(schema, {}, missing_definition_error=factory)
    except BaseException as exc:  # noqa: BLE001
        print(f'{label:45} -> {type(exc).__name__}: {exc}')
        if isinstance(exc, TypeError):
            failures += 1
    else:
        print(f'{label:45} -> no exception')

print('--- full traceback for the function-valued factory ---')
try:
    gather_schemas_for_cleaning(schema, {}, missing_definition_error=function_factory)
except BaseException:  # noqa: BLE001
    traceback.print_exc()

print('--- factory on a schema with NO missing definition (argument conversion happens before traversal) ---')
try:
    print(gather_schemas_for_cleaning({'type': 'int'}, {}, missing_definition_error=function_factory))
except BaseException as exc:  # noqa: BLE001
    print(f'{type(exc).__name__}: {exc}')

print(f'RESULT: {failures} stub-permitted callables rejected with TypeError')
raise SystemExit(1 if failures else 0)
