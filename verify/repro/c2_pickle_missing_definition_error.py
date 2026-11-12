# Run: /opt/venv/bin/python verify/repro/c2_pickle_missing_definition_error.py   (from the repo root, after `maturin develop`)
"""C2: MissingDefinitionError declares a module that cannot be imported, so pickle cannot restore it.

Exit status 0 = round trip fails (problem reproduced), 1 = round trip works.
"""
import copy
import importlib
import pickle
import sys

from pydantic._internal._schema_gather import MissingDefinitionError, gather_schemas_for_cleaning

print('__module__ =', MissingDefinitionError.__module__, '| __qualname__ =', MissingDefinitionError.__qualname__)
print('declared module in sys.modules:', MissingDefinitionError.__module__ in sys.modules)
try:
    importlib.import_module(MissingDefinitionError.__module__)
    print('import of declared module: OK')
except Exception as e:
    print(f'import of declared module: {type(e).__name__}: {e}')

try:
    gather_schemas_for_cleaning({'type': 'definition-ref', 'schema_ref': 'missing'}, {})
except MissingDefinitionError as e:
    exc = e
print('instance:', repr(exc), 'args =', exc.args, 'schema_reference =', exc.schema_reference)

failed = False
for proto in range(pickle.HIGHEST_PROTOCOL + 1):
    try:
        restored = pickle.loads(pickle.dumps(exc, protocol=proto))
        print(f'protocol {proto}: restored {type(restored) is MissingDefinitionError} args={restored.args} '
              f'schema_reference={restored.schema_reference!r}')
    except Exception as e:
        failed = True
        print(f'protocol {proto}: {type(e).__name__}: {e}')
try:
    c = copy.copy(exc)
    print('copy.copy:', type(c) is MissingDefinitionError, c.args)
except Exception as e:
    print(f'copy.copy: {type(e).__name__}: {e}')
print('RESULT:', 'PICKLE ROUND TRIP FAILS' if failed else 'pickle round trip works')
sys.exit(0 if failed else 1)
