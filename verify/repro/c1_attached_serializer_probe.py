# Run: python verify/repro/c1_attached_serializer_probe.py   (with the claim branch's venv; exits 1 if any identity is lost)
"""Behaviour probe for the path claim C1 says is untested: a definition reference / deferred discriminator that is
only reachable through the `schema` or `return_schema` field of a serializer attached via `serialization`."""

from __future__ import annotations

import sys

from pydantic_core import core_schema as cs

from pydantic import BaseModel, field_serializer
from pydantic._internal._schema_gather import gather_schemas_for_cleaning

MARKER = {'pydantic_internal_union_discriminator': 'kind'}
failures = 0


def check(label: str, condition: bool) -> None:
    global failures
    failures += not condition
    print(f'{"ok  " if condition else "LOST"} {label}')


# 1. definition-ref behind an attached plain serializer's return_schema
ref = cs.definition_reference_schema('target')
schema = cs.int_schema(serialization=cs.plain_serializer_function_ser_schema(lambda v: v, return_schema=ref))
result = gather_schemas_for_cleaning(schema, {'target': cs.str_schema(ref='target')})
check('plain serializer return_schema -> definition-ref collected by identity', result['collected_references'].get('target') is ref)

# 2. deferred discriminator behind an attached plain serializer's return_schema
disc = cs.int_schema(metadata=dict(MARKER))
schema = cs.int_schema(serialization=cs.plain_serializer_function_ser_schema(lambda v: v, return_schema=disc))
result = gather_schemas_for_cleaning(schema, {})
check('plain serializer return_schema -> deferred discriminator collected by identity', [id(s) for s in result['deferred_discriminator_schemas']] == [id(disc)])

# 3. definition-ref behind an attached wrap serializer's schema, and another behind its return_schema
ref_schema, ref_return = cs.definition_reference_schema('s'), cs.definition_reference_schema('r')
schema = cs.int_schema(
    serialization=cs.wrap_serializer_function_ser_schema(lambda v, h: h(v), schema=ref_schema, return_schema=ref_return)
)
result = gather_schemas_for_cleaning(schema, {'s': cs.str_schema(ref='s'), 'r': cs.str_schema(ref='r')})
check('wrap serializer schema -> definition-ref collected by identity', result['collected_references'].get('s') is ref_schema)
check('wrap serializer return_schema -> definition-ref collected by identity', result['collected_references'].get('r') is ref_return)

# 4. deferred discriminators behind an attached wrap serializer's schema / return_schema
disc_schema, disc_return = cs.int_schema(metadata=dict(MARKER)), cs.int_schema(metadata=dict(MARKER))
schema = cs.int_schema(
    serialization=cs.wrap_serializer_function_ser_schema(lambda v, h: h(v), schema=disc_schema, return_schema=disc_return)
)
result = gather_schemas_for_cleaning(schema, {})
ids = [id(s) for s in result['deferred_discriminator_schemas']]
check('wrap serializer schema -> deferred discriminator collected by identity', id(disc_schema) in ids)
check('wrap serializer return_schema -> deferred discriminator collected by identity', id(disc_return) in ids)


# 5. the everyday shape of the same path: a field serializer whose return annotation is another model
class Inner(BaseModel):
    x: int


try:

    class Outer(BaseModel):
        a: int

        @field_serializer('a')
        def ser_a(self, value: int) -> Inner:
            return Inner(x=value)

    dumped = Outer(a=1).model_dump()
    check(f'model with @field_serializer returning another model builds and dumps: {dumped}', dumped == {'a': {'x': 1}})
except Exception as exc:
    check(f'model with @field_serializer returning another model: {type(exc).__name__}: {str(exc).splitlines()[0][:160]}', False)

print(f'failures={failures}')
sys.exit(1 if failures else 0)
