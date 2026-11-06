"""Probe for C1/C2. Run on the evalon/pydantic-s-4aec16e5 checkout after `maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen`: `python verify/repro/c1_c2_dict_list_subclass_probe.py`"""
from pydantic_core import core_schema as cs
from pydantic._internal._schema_gather import gather_schemas_for_cleaning


class ReversedValuesDict(dict):
    def values(self):
        return reversed(list(super().values()))


class SwappedList(list):
    """list whose __iter__ yields different child schemas from its stored elements."""
    def __init__(self, stored, yielded):
        super().__init__(stored)
        self._yielded = yielded
    def __iter__(self):
        return iter(self._yielded)


def defs(*names):
    return {n: cs.int_schema(ref=n) for n in names}

# C1: typed_dict fields in a dict subclass, storage order a,b ; values() order b,a
fields = ReversedValuesDict({'f_a': cs.typed_dict_field(cs.definition_reference_schema('a')),
                             'f_b': cs.typed_dict_field(cs.definition_reference_schema('b'))})
print('C1 storage order  :', list(dict.keys(fields)))
print('C1 values() order :', [list(v['schema']['schema_ref'])[0] for v in fields.values()])
r = gather_schemas_for_cleaning(cs.typed_dict_schema(fields), defs('a', 'b'))
print('C1 collected order:', list(r['collected_references']))

# C2: list subclass, stored elements reference 'stored', __iter__ yields 'yielded'
items = SwappedList([cs.definition_reference_schema('stored')], [cs.definition_reference_schema('yielded')])
print('C2 list(stored)   :', [x['schema_ref'] for x in list.__iter__(items)])
print('C2 iter(yielded)  :', [x['schema_ref'] for x in items])
r = gather_schemas_for_cleaning(cs.tuple_schema(items), defs('stored', 'yielded'))
print('C2 collected      :', list(r['collected_references']))
r = gather_schemas_for_cleaning(cs.union_schema(SwappedList([cs.definition_reference_schema('stored')], [cs.definition_reference_schema('yielded')])), defs('stored', 'yielded'))
print('C2 union collected:', list(r['collected_references']))
