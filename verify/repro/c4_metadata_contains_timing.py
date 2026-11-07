# Run: python verify/repro/c4_metadata_contains_timing.py  (venv built from evalon/pydantic-s-f22cc9d7; add --former to also run the base commit's pure-Python implementation)
# ruff: noqa: T201, D101, D102, D103
"""C4 probe: is the parent's deferred-discriminator metadata membership evaluated after its child and serialization callbacks?"""

from __future__ import annotations

import importlib.util
import sys
from typing import Any

from pydantic_core import core_schema as cs

from pydantic._internal._schema_gather import gather_schemas_for_cleaning

KEY = 'pydantic_internal_union_discriminator'
LOG: list[str] = []


class RecordingMeta:
    """Non-dict metadata object: `__contains__` records the traversal order."""

    def __init__(self, name: str, *, member: bool | None = None) -> None:
        self.name = name
        self.member = member

    def __contains__(self, key: object) -> bool:
        LOG.append(self.name)
        if self.member is not None:
            return self.member
        # parent: member only once child + serializer callbacks already ran
        return 'child' in LOG and 'serializer' in LOG


class RecordingDictMeta(dict):
    """dict-subclass variant of the same callback."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name

    def __contains__(self, key: object) -> bool:
        LOG.append(self.name)
        return 'child' in LOG and 'serializer' in LOG


def build(parent_meta: Any) -> tuple[Any, Any, Any]:
    child = cs.str_schema(metadata=RecordingMeta('child', member=True))
    serializer = cs.plain_serializer_function_ser_schema(lambda v: v)
    serializer['metadata'] = RecordingMeta('serializer', member=True)
    parent = cs.typed_dict_schema({'f': cs.typed_dict_field(child)}, serialization=serializer, metadata=parent_meta)
    return parent, child, serializer


def probe(label: str, gather: Any) -> None:
    print(f'--- {label}')
    for variant, meta in (
        ('non-dict metadata', RecordingMeta('parent')),
        ('dict-subclass metadata', RecordingDictMeta('parent')),
    ):
        LOG.clear()
        parent, child, serializer = build(meta)
        res = gather(parent, {})
        names = {id(child): 'child', id(serializer): 'serializer', id(parent): 'parent'}
        print(f'  [{variant}] __contains__ call order: {LOG}')
        print(
            f'  [{variant}] deferred_discriminator_schemas: {[names.get(id(s), "?") for s in res["deferred_discriminator_schemas"]]}'
        )


probe('native (branch build)', gather_schemas_for_cleaning)
if '--former' in sys.argv:
    spec = importlib.util.spec_from_file_location('former_schema_gather', '/home/ubuntu/former_schema_gather.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    probe('former pure-Python (base a2c93547)', mod.gather_schemas_for_cleaning)
