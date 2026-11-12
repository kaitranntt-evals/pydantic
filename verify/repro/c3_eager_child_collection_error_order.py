# Run: /opt/venv/bin/python verify/repro/c3_eager_child_collection_error_order.py [module]
#   (from the repo root, after `maturin develop`; optional argument: module providing the gatherer,
#    default `pydantic._internal._schema_gather`)
"""C3: an earlier child holds an unresolved definition reference, a later sibling is malformed.

The pre-change Python walker traverses the earlier child first and raises MissingDefinitionError.
Exit status 0 = a structural/cast error won in at least one case (problem reproduced), 1 = otherwise.
"""
import importlib
import sys

mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else 'pydantic._internal._schema_gather')
MissingDefinitionError = mod.MissingDefinitionError

missing = lambda: {'type': 'definition-ref', 'schema_ref': 'missing'}  # noqa: E731
cases = {
    'lax-or-strict: lax_schema=<missing ref>, strict_schema absent': {'type': 'lax-or-strict', 'lax_schema': missing()},
    'union: choices=[<missing ref>, ()]': {'type': 'union', 'choices': [missing(), ()]},
    'union: choices=[<missing ref>, []] (list-valued child)': {'type': 'union', 'choices': [missing(), []]},
    'chain: steps=[<missing ref>, []] (list-valued child)': {'type': 'chain', 'steps': [missing(), []]},
    'tuple: items_schema=[<missing ref>, 1]': {'type': 'tuple', 'items_schema': [missing(), 1]},
    'json-or-python: json_schema=<missing ref>, python_schema absent': {'type': 'json-or-python', 'json_schema': missing()},
    'dict: keys_schema=<missing ref>, values_schema=[]': {'type': 'dict', 'keys_schema': missing(), 'values_schema': []},
    'arguments: [{schema: <missing ref>}, {}]': {'type': 'arguments', 'arguments_schema': [{'schema': missing()}, {}]},
    'control: lax-or-strict with only the missing ref problem': {
        'type': 'lax-or-strict', 'lax_schema': missing(), 'strict_schema': {'type': 'int'}},
}
other = 0
for label, schema in cases.items():
    try:
        mod.gather_schemas_for_cleaning(schema, {})
        got = 'no exception'
    except MissingDefinitionError as e:
        got = f'MissingDefinitionError({e.schema_reference!r})'
    except Exception as e:
        other += 1
        got = f'{type(e).__name__}: {e}'
    print(f'{label}\n    -> {got}')
print('RESULT:', f'{other} case(s) reported a later structural/cast error before MissingDefinitionError')
sys.exit(0 if other else 1)
