# Run: /opt/venv-41fd/bin/python verify/repro/c2_c4_missing_children.py   (inside a checkout of evalon/pydantic-s-41fd7c4c built with `maturin develop`)
"""C2/C4: missing required child keys in arguments / arguments-v3 / lax-or-strict / json-or-python schemas."""
import inspect

import pydantic._internal._schema_gather as sg
from pydantic._internal._schema_gather import gather_schemas_for_cleaning

print('schema_gather module:', sg.__file__)
print('pure-Python traverse_schema present:', hasattr(sg, 'traverse_schema'))


def probe(label, schema):
    try:
        res = gather_schemas_for_cleaning(schema, {})
        print(f'{label:55} -> RETURNED {res}')
    except BaseException as e:
        print(f'{label:55} -> RAISED {type(e).__name__}({", ".join(map(repr, e.args))})')


print('== C2: arguments / arguments-v3')
probe("{'type': 'arguments'}", {'type': 'arguments'})
probe("{'type': 'arguments-v3'}", {'type': 'arguments-v3'})
probe("control {'type': 'arguments', 'arguments_schema': []}", {'type': 'arguments', 'arguments_schema': []})
probe("control {'type': 'arguments-v3', 'arguments_schema': []}", {'type': 'arguments-v3', 'arguments_schema': []})
probe("control {'type': 'call'} (required arguments_schema)", {'type': 'call'})

print('== C4: lax-or-strict / json-or-python, one required child omitted at a time')
I = {'type': 'int'}
probe('lax-or-strict without lax_schema', {'type': 'lax-or-strict', 'strict_schema': I})
probe('lax-or-strict without strict_schema', {'type': 'lax-or-strict', 'lax_schema': I})
probe('json-or-python without json_schema', {'type': 'json-or-python', 'python_schema': I})
probe('json-or-python without python_schema', {'type': 'json-or-python', 'json_schema': I})
probe('control lax-or-strict complete', {'type': 'lax-or-strict', 'lax_schema': I, 'strict_schema': I})
probe('control json-or-python complete', {'type': 'json-or-python', 'json_schema': I, 'python_schema': I})
