# Run: /opt/venv-00346963/bin/python verify/instrumentation/c3_extra_finished_sibling_address_reuse.py [native|reference]   (cwd = worktree of evalon/pydantic-s-00346963; needs ../repro/reference_schema_gather.py)
"""C3 follow-up (not a claim part): stale `visited` ids of *finished* lazily generated schemas.

root = chain[ lazy(A), lazy(B) ]; A and B are lazily built chains whose single lazily built step is a definition-ref to
'ref_A' / 'ref_B'. Expected (reference python): both references collected and inlinable.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / 'repro'))
import reference_schema_gather as reference  # noqa: E402

from pydantic._internal import _schema_gather as native  # noqa: E402

impl = {'native': native, 'reference': reference}[sys.argv[1] if len(sys.argv) > 1 else 'native']
log: list[str] = []


class LazyRef:
    def __init__(self, name: str) -> None:
        self.name = name

    def __iter__(self) -> Any:
        child = {'type': 'definition-ref', 'schema_ref': f'ref_{self.name}'}
        log.append(f'create definition-ref ref_{self.name} id={id(child):#x}')
        yield child


class LazyBranches:
    def __iter__(self) -> Any:
        for name in 'AB':
            node = {'type': 'chain', 'steps': LazyRef(name)}
            log.append(f'create branch {name} id={id(node):#x}')
            yield node


root = {'type': 'chain', 'steps': LazyBranches()}
defs = {f'ref_{n}': {'type': 'int', 'ref': f'ref_{n}'} for n in 'AB'}
res = impl.gather_schemas_for_cleaning(root, defs)['collected_references']
print('\n'.join(log))
print('collected_references =', res)
ok = set(res) == {'ref_A', 'ref_B'} and all(v is not None for v in res.values())
print('RESULT:', 'OK' if ok else 'WRONG (expected ref_A and ref_B both collected and inlinable)')
raise SystemExit(0 if ok else 1)
