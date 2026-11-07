# Run: python verify/repro/c5_missing_definition_str.py  (venv built from evalon/pydantic-s-07335cde; add --former to also run the base commit's pure-Python class)
"""C5 probe: does str()/repr() of MissingDefinitionError match LookupError for the same argument?"""

from __future__ import annotations

import importlib.util
import sys

from pydantic_core import core_schema as cs

from pydantic._internal._schema_gather import MissingDefinitionError, gather_schemas_for_cleaning


def show(label: str, exc_cls: type, gather) -> None:
    print(f'--- {label}')
    for ref in ('missing', 'ref\x00with_nul', 'ユニコード_ref'):
        mine = exc_cls(ref)
        base = LookupError(ref)
        print(f'  constructed {ref!r}: str(MDE)={str(mine)!r} str(LookupError)={str(base)!r} equal={str(mine) == str(base)}')
        print(f'      repr(MDE)={mine!r}  repr(LookupError)={base!r}  args={mine.args!r}')
    try:
        gather(cs.definition_reference_schema('missing'), {})
    except exc_cls as e:
        print(f'  raised by gather: str={str(e)!r} args={e.args!r} equal_to_LookupError_str={str(e) == str(LookupError(*e.args))}')


show('native (branch build)', MissingDefinitionError, gather_schemas_for_cleaning)
if '--former' in sys.argv:
    spec = importlib.util.spec_from_file_location('former_schema_gather', '/home/ubuntu/former_schema_gather.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    show('former pure-Python (base a2c93547)', mod.MissingDefinitionError, mod.gather_schemas_for_cleaning)
