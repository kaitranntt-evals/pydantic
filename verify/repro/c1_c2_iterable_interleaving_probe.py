# Run: cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c1_c2_iterable_interleaving_probe.py
# Compares the native gather (pydantic._internal._schema_gather) with the pre-change Python reference
# implementation (verify/repro/reference_schema_gather.py, copied from a2c935478) on child iterables whose
# later items depend on mutable state mutated by an earlier child's metadata `__contains__` callback.
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from pydantic_core import core_schema as cs

from pydantic._internal._schema_gather import gather_schemas_for_cleaning as native_gather

_ref_path = Path(__file__).with_name('reference_schema_gather.py')
_spec = importlib.util.spec_from_file_location('reference_schema_gather', _ref_path)
_ref_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _ref_mod
assert _spec.loader is not None
_spec.loader.exec_module(_ref_mod)
reference_gather = _ref_mod.gather_schemas_for_cleaning

DEFINITIONS = {name: cs.int_schema(ref=name) for name in ('first', 'after_callback', 'before_callback')}


class Meta(dict):
    """Metadata mapping whose `__contains__` is a callback that mutates shared state."""

    def __init__(self, name: str, state: dict[str, Any], events: list[str], deferred: bool) -> None:
        super().__init__()
        self.name, self.state, self.events, self.deferred = name, state, events, deferred

    def __contains__(self, key: object) -> bool:
        self.events.append(f'metadata.__contains__({self.name})')
        self.state['callbacks'] += 1
        return key == 'pydantic_internal_union_discriminator' and self.deferred


def make_children(state: dict[str, Any], events: list[str]):
    """Yield child 1, then a child 2 whose reference and deferral depend on whether child 1's callback ran."""
    events.append('iter: yield child1(first)')
    yield {'type': 'definition-ref', 'schema_ref': 'first', 'metadata': Meta('child1', state, events, True)}
    ran = state['callbacks'] > 0
    ref = 'after_callback' if ran else 'before_callback'
    events.append(f'iter: yield child2({ref}, deferred={ran})')
    yield {'type': 'definition-ref', 'schema_ref': ref, 'metadata': Meta('child2', state, events, ran)}
    events.append('iter: exhausted')


class StatefulIterable:
    """C2: a non-generator iterable (custom `__iter__`/`__next__`) with the same state dependence."""

    def __init__(self, state: dict[str, Any], events: list[str]) -> None:
        self._gen = make_children(state, events)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._gen)


def run(label: str, gather, make_iterable) -> tuple[list[str], list[str], list[str]]:
    events: list[str] = []
    state = {'callbacks': 0}
    schema: Any = {'type': 'tuple', 'items_schema': make_iterable(state, events)}
    result = gather(schema, DEFINITIONS)
    refs = list(result['collected_references'])
    deferred = [s['schema_ref'] for s in result['deferred_discriminator_schemas']]
    print(f'--- {label}')
    for e in events:
        print(f'  event: {e}')
    print(f'  collected_references keys: {refs}')
    print(f'  deferred_discriminator_schemas: {deferred}')
    return events, refs, deferred


def main() -> int:
    differs = False
    for claim, make_iterable in (('C1 generator', make_children), ('C2 StatefulIterable', StatefulIterable)):
        native = run(f'{claim} / native (branch under audit)', native_gather, make_iterable)
        ref = run(f'{claim} / reference Python implementation (a2c935478)', reference_gather, make_iterable)
        same = native[1:] == ref[1:]
        print(f'  => {claim}: results {"IDENTICAL" if same else "DIFFER"} between native and reference')
        differs |= not same
    return 1 if differs else 0


if __name__ == '__main__':
    sys.exit(main())
