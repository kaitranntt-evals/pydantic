# Run: /opt/venv-3f54c6e9/bin/python verify/repro/c2_tagged_union_choices_mapping.py   (cwd = worktree of evalon/pydantic-s-3f54c6e9, native ext built; needs reference_schema_gather.py next to it)
"""C2: tagged-union `choices` given as dict subclass with overridden values(), UserDict, MappingProxyType.

`reference_schema_gather.py` is the pre-change pure-Python module (git show a2c935478:pydantic/_internal/_schema_gather.py),
which does `for v in schema['choices'].values()`.
"""

from __future__ import annotations

import sys
from collections import UserDict
from pathlib import Path
from types import MappingProxyType
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import reference_schema_gather as reference  # noqa: E402

from pydantic._internal import _schema_gather as native  # noqa: E402


class ReversedValuesDict(dict):
    """values() yields the stored children in reverse order."""

    def values(self) -> Any:
        return reversed(tuple(super().values()))


class ReplacedValuesDict(dict):
    """values() yields children that are not the stored ones."""

    replacement: list[Any]

    def values(self) -> Any:
        return iter(self.replacement)


def ref(name: str) -> dict[str, Any]:
    return {
        'type': 'definition-ref',
        'schema_ref': name,
        'metadata': {'pydantic_internal_union_discriminator': f'disc_{name}'},
    }


DEFS = {n: {'type': 'int', 'ref': n} for n in 'abc'}


def cases() -> dict[str, tuple[Any, list[str]]]:
    """name -> (choices mapping, refs returned by its Python values())."""
    replaced = ReplacedValuesDict({'x': ref('a'), 'y': ref('b')})
    replaced.replacement = [ref('c')]
    out = {
        'plain dict (control)': {'x': ref('a'), 'y': ref('b')},
        'dict subclass, values() reversed': ReversedValuesDict({'x': ref('a'), 'y': ref('b')}),
        'dict subclass, values() replaced': replaced,
        'collections.UserDict': UserDict({'x': ref('a'), 'y': ref('b')}),
        'types.MappingProxyType': MappingProxyType({'x': ref('a'), 'y': ref('b')}),
    }
    return {k: (v, [c['schema_ref'] for c in v.values()]) for k, v in out.items()}


def run(mod: Any, choices: Any) -> str:
    schema = {'type': 'tagged-union', 'discriminator': 'kind', 'choices': choices}
    try:
        res = mod.gather_schemas_for_cleaning(schema, DEFS)
    except BaseException as exc:  # noqa: BLE001
        return f'RAISED {type(exc).__name__}: {exc}'
    return (
        f'refs={list(res["collected_references"])} '
        f'deferred={[s["schema_ref"] for s in res["deferred_discriminator_schemas"]]}'
    )


bad = 0
for name, (choices, expected) in cases().items():
    want = f'refs={expected} deferred={expected}'
    got_ref = run(reference, choices)
    got_native = run(native, choices)
    ok = got_native == want
    bad += not ok
    print(f'[{name}]')
    print(f'    values() returns : {expected}')
    print(f'    reference python : {got_ref}')
    print(f'    native (branch)  : {got_native}')
    print(f'    -> {"OK" if ok else "MISMATCH"}')

print(f'RESULT: {bad} of {len(cases()) - 1} non-plain mappings mishandled')
raise SystemExit(1 if bad else 0)
