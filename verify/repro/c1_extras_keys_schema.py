# Run: /opt/venv/bin/python verify/repro/c1_extras_keys_schema.py   (from the repo root, after `maturin develop`)
"""C1: a definition referenced only from a model's `extras_keys_schema` is not seen by schema gathering."""
import dataclasses
import traceback
from enum import Enum

from pydantic_core import SchemaValidator, core_schema

from pydantic import BaseModel
from pydantic._internal._schema_gather import gather_schemas_for_cleaning

print('== part child_collection: direct gather of a model-fields schema')
key_ref = core_schema.definition_reference_schema('KeyDef')
val_ref = core_schema.definition_reference_schema('ValDef')
mf = core_schema.model_fields_schema(
    {}, extra_behavior='allow', extras_keys_schema=key_ref, extras_schema=val_ref
)
defs = {'KeyDef': core_schema.str_schema(max_length=3), 'ValDef': core_schema.int_schema()}
res = gather_schemas_for_cleaning(mf, defs)
print('collected_references keys:', sorted(res['collected_references']))
print('KeyDef collected:', 'KeyDef' in res['collected_references'])
# a *missing* definition used only by extras_keys_schema is not reported either:
res2 = gather_schemas_for_cleaning(
    core_schema.model_fields_schema({}, extra_behavior='allow', extras_keys_schema=key_ref), {}
)
print('gather with KeyDef missing from definitions ->', res2, '(no MissingDefinitionError)')


print('== part production_trigger: real models')


class Color(Enum):
    RED = 'red'
    BLUE = 'blue'


@dataclasses.dataclass(frozen=True)
class Key:
    x: int


class Sub(BaseModel, frozen=True):
    x: int


def find_refs(obj, out, seen):
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, dict):
        if obj.get('type') == 'definition-ref':
            out.append(obj['schema_ref'])
        for v in obj.values():
            find_refs(v, out, seen)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            find_refs(v, out, seen)


for name, key_tp, sample in [('Enum', Color, {'red': 1}), ('dataclass', Key, {Key(1): 1}), ('BaseModel', Sub, {Sub(x=1): 1})]:
    print(f'-- extra key type: {name}')
    try:

        class M(BaseModel, extra='allow'):
            __pydantic_extra__: dict[key_tp, int]

        cs = M.__pydantic_core_schema__
        eks = cs['schema'].get('extras_keys_schema')
        print('core schema type:', cs['type'], '| extras_keys_schema:', None if eks is None else {k: (v if k in ('type', 'schema_ref') else '...') for k, v in eks.items()})
        refs: list = []
        find_refs(cs, refs, set())
        print('definition-ref left in cleaned schema:', refs)
        print('validator class:', type(M.__pydantic_validator__).__name__)
        try:
            m = M.model_validate(sample)
            print('validate OK, extra:', m.__pydantic_extra__)
        except Exception as e:
            print('validate FAILED:', type(e).__name__, str(e)[:300])
        try:
            SchemaValidator(cs)
            print('SchemaValidator(core_schema) built OK')
        except Exception as e:
            print('SchemaValidator(core_schema) FAILED:', type(e).__name__, str(e)[:300])
    except Exception as e:
        print('class creation FAILED:', type(e).__name__, str(e)[:400])
        traceback.print_exc(limit=3)

print('== control: same dataclass as the extra *value* type (extras_schema edge is traversed)')


class Ok(BaseModel, extra='allow'):
    __pydantic_extra__: dict[str, Key]


print('Ok built; validate:', Ok.model_validate({'a': {'x': 1}}).__pydantic_extra__)

print('== what GenerateSchema hands to schema cleaning (before clean_schema)')
from pydantic._internal import _generate_schema as gs

orig_finalize = gs._Definitions.finalize_schema


def spy(self, schema):
    print('schema passed to finalize_schema:', {k: v for k, v in schema.items() if k in ('type', 'schema_ref')})
    for ref, d in self._definitions.items():
        inner = d.get('schema', {})
        if d.get('type') == 'model' and 'extras_keys_schema' in inner:
            print(f'definition {ref!r} -> model-fields extras_keys_schema (pre-clean):', inner['extras_keys_schema'])
    print('pre-clean definitions:', sorted(self._definitions))
    from pydantic._internal._schema_gather import gather_schemas_for_cleaning as g

    print('gather collected_references keys:', sorted(g(schema, self._definitions)['collected_references']))
    out = orig_finalize(self, schema)
    print('post-clean type:', out['type'], '| extras_keys_schema:', out['schema']['extras_keys_schema'])
    return out


gs._Definitions.finalize_schema = spy
try:

    class M2(BaseModel, extra='allow'):
        __pydantic_extra__: dict[Key, int]
except Exception as e:
    print('class creation FAILED:', type(e).__name__, str(e)[:200])
