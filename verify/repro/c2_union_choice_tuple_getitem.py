# Run: python verify/repro/c2_union_choice_tuple_getitem.py  (venv built from evalon/pydantic-s-7d6f1afb; add --former to also run the base commit's pure-Python implementation)
# ruff: noqa: T201, D101, D102, D103
"""C2 probe: does gathering a labeled union choice (tuple subclass) honor an overridden `__getitem__`?"""

from __future__ import annotations

import importlib.util
import sys
from typing import Any

from pydantic_core import core_schema as cs

from pydantic._internal._schema_gather import gather_schemas_for_cleaning

STORED = cs.definition_reference_schema('stored')
OVERRIDE = cs.definition_reference_schema('override')
DEFS = {'stored': cs.int_schema(ref='stored'), 'override': cs.str_schema(ref='override')}


class LabeledChoiceTuple(tuple):
    calls: list[Any] = []

    def __getitem__(self, index: Any) -> Any:
        LabeledChoiceTuple.calls.append(index)
        if index == 0:
            return OVERRIDE
        return super().__getitem__(index)


def probe(label: str, gather: Any) -> None:
    print(f'--- {label}')
    LabeledChoiceTuple.calls.clear()
    choice = LabeledChoiceTuple((STORED, 'label'))
    assert tuple.__getitem__(choice, 0) is STORED and choice[0] is OVERRIDE
    res = gather(cs.union_schema([choice]), DEFS)
    collected = res['collected_references']
    print(
        '  collected keys:',
        list(collected),
        '| identity:',
        {k: ('STORED' if v is STORED else 'OVERRIDE' if v is OVERRIDE else v) for k, v in collected.items()},
    )
    print('  __getitem__ calls:', LabeledChoiceTuple.calls)


probe('native (branch build)', gather_schemas_for_cleaning)
if '--former' in sys.argv:
    spec = importlib.util.spec_from_file_location('former_schema_gather', '/home/ubuntu/former_schema_gather.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    probe('former pure-Python (base a2c93547)', mod.gather_schemas_for_cleaning)
