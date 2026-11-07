# Run: python verify/repro/c1_c3_definitions_get_override.py   (any venv with the branch's native build; add --former to also run the base commit's pure-Python implementation from /home/ubuntu/former_schema_gather.py)
# ruff: noqa: T201, D101, D102, D103
"""C1/C3 probe: does definition-ref resolution honor a dict subclass's overridden `get`?"""

from __future__ import annotations

import importlib.util
import sys
from typing import Any

from pydantic_core import core_schema as cs

from pydantic._internal._schema_gather import MissingDefinitionError, gather_schemas_for_cleaning


def load_former() -> Any:
    spec = importlib.util.spec_from_file_location('former_schema_gather', '/home/ubuntu/former_schema_gather.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


SUPPLIED = cs.int_schema(ref='absent')


class OverridingDefs(dict):
    """`get` supplies a definition for the absent key 'absent' and hides stored key 'hidden' with None."""

    calls: list[str] = []

    def get(self, key: Any, default: Any = None) -> Any:
        OverridingDefs.calls.append(key)
        if key == 'absent':
            return SUPPLIED
        if key == 'hidden':
            return None
        return super().get(key, default)


def probe(label: str, gather: Any, exc: type[Exception]) -> None:
    print(f'--- {label}')
    OverridingDefs.calls.clear()
    defs = OverridingDefs({'hidden': cs.int_schema(ref='hidden')})

    absent_ref = cs.definition_reference_schema('absent')
    try:
        res = gather(cs.list_schema(absent_ref), defs)
        print(
            '  absent key (get supplies definition): RESOLVED ->',
            {k: (v is absent_ref) for k, v in res['collected_references'].items()},
        )
    except exc as e:
        print('  absent key (get supplies definition): MissingDefinitionError', e.args)

    hidden_ref = cs.definition_reference_schema('hidden')
    try:
        res = gather(cs.list_schema(hidden_ref), defs)
        print(
            '  stored key hidden by get->None: RESOLVED ->',
            {k: (v is hidden_ref) for k, v in res['collected_references'].items()},
        )
    except exc as e:
        print('  stored key hidden by get->None: MissingDefinitionError', e.args)
    print('  overridden get() called with:', OverridingDefs.calls)


probe('native (branch build)', gather_schemas_for_cleaning, MissingDefinitionError)
if '--former' in sys.argv:
    former = load_former()
    probe('former pure-Python (base a2c93547)', former.gather_schemas_for_cleaning, former.MissingDefinitionError)
