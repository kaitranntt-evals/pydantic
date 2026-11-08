# Run (branch under test must be importable): cd <worktree> && <venv>/bin/python /home/ubuntu/repos/pydantic/verify/repro/c3_dataclass_args_order_probe.py
# Gathers a 'dataclass-args' schema whose `fields` iterator selects a reference depending on whether
# `computed_fields` has already been iterated; records iterable consumption order and child-visit order,
# and compares with the pre-change Python reference implementation (traversal order: computed_fields, then fields).
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

DEFINITIONS = {name: cs.int_schema(ref=name) for name in ('computed', 'fields_after_computed', 'fields_before_computed')}


class VisitMeta(dict):
    """Metadata whose `__contains__` records when the child schema is visited."""

    def __init__(self, name: str, events: list[str]) -> None:
        super().__init__()
        self.name, self.events = name, events

    def __contains__(self, key: object) -> bool:
        self.events.append(f'visit: {self.name}')
        return False


def computed_fields_iter(state: dict[str, bool], events: list[str]):
    events.append('consume: computed_fields iterated')
    state['computed_iterated'] = True
    yield cs.computed_field('c', {'type': 'definition-ref', 'schema_ref': 'computed', 'metadata': VisitMeta('computed', events)})


def fields_iter(state: dict[str, bool], events: list[str]):
    ref = 'fields_after_computed' if state['computed_iterated'] else 'fields_before_computed'
    events.append(f'consume: fields iterated -> selects {ref}')
    yield cs.dataclass_field('f', {'type': 'definition-ref', 'schema_ref': ref, 'metadata': VisitMeta(ref, events)})


def run(label: str, gather) -> tuple[list[str], list[str]]:
    events: list[str] = []
    state = {'computed_iterated': False}
    schema: Any = {
        'type': 'dataclass-args',
        'dataclass_name': 'DC',
        'computed_fields': computed_fields_iter(state, events),
        'fields': fields_iter(state, events),
    }
    result = gather(schema, DEFINITIONS)
    refs = list(result['collected_references'])
    print(f'--- {label}')
    for e in events:
        print(f'  event: {e}')
    print(f'  collected_references keys: {refs}')
    return events, refs


def main() -> int:
    native = run('native (branch under test)', native_gather)
    ref = run('reference Python implementation (a2c935478)', reference_gather)
    same = native[1] == ref[1]
    print(f'=> selected references {"IDENTICAL" if same else "DIFFER"} between native and reference')
    return 1 if not same else 0


if __name__ == '__main__':
    sys.exit(main())
