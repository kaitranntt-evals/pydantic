# Run: /opt/venv-00346963/bin/python verify/repro/c3_lazy_chain_address_reuse.py [native|reference] [depth]   (cwd = worktree of evalon/pydantic-s-00346963, native ext built; needs reference_schema_gather.py next to it)
"""C3: lazily generated single-child chain -- ancestor lifetime and address reuse during native gathering.

Every node is `{'type': 'chain', 'steps': LazySteps(...)}`. `LazySteps.__iter__` builds the single child on demand and
keeps no reference to it, so nothing but the gatherer itself can keep a generated node alive. The innermost child is
`{'type': 'definition-ref', 'schema_ref': 'terminal'}`.

`reference_schema_gather.py` is the pre-change pure-Python module (git show a2c935478:pydantic/_internal/_schema_gather.py).
"""

from __future__ import annotations

import sys
import weakref
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import reference_schema_gather as reference  # noqa: E402

from pydantic._internal import _schema_gather as native  # noqa: E402

impl_name = sys.argv[1] if len(sys.argv) > 1 else 'native'
DEPTH = int(sys.argv[2]) if len(sys.argv) > 2 else 8
impl = {'native': native, 'reference': reference}[impl_name]
DEFS = {'terminal': {'type': 'int', 'ref': 'terminal'}}


class Node(dict):
    """dict subclass: accepted as a schema, weak-referenceable, and reports its own deallocation."""

    depth: int
    events: list[str]

    def __del__(self) -> None:
        self.events.append(f'free   depth={self.depth}')


class LazySteps:
    """`steps` container whose single child schema only exists once iterated."""

    def __init__(self, depth: int, trace: Trace) -> None:
        self.depth = depth  # depth of the node owning this container
        self.trace = trace

    def __iter__(self) -> Any:
        t = self.trace
        t.events.append(f'visit  depth={self.depth} (its steps are being iterated)')
        child_depth = self.depth + 1
        if child_depth > t.max_depth:
            child: Any = {'type': 'definition-ref', 'schema_ref': 'terminal'}
            t.events.append(f'create terminal definition-ref id={id(child):#x}')
        else:
            child = t.make(child_depth)
        yield child


class Trace:
    def __init__(self, max_depth: int, tracked: bool) -> None:
        self.max_depth = max_depth
        self.tracked = tracked  # True: Node (lifetime tracing); False: plain dict (address tracing)
        self.events: list[str] = []
        self.ids: dict[int, int] = {}  # depth -> id() at creation
        self.refs: dict[int, weakref.ref[Any]] = {}

    def make(self, depth: int) -> Any:
        if self.tracked:
            node: Any = Node(type='chain', steps=LazySteps(depth, self))
            node.depth = depth
            node.events = self.events
            self.refs[depth] = weakref.ref(node)
            alive = [d for d, r in self.refs.items() if d < depth and r() is not None]
            dead = [d for d, r in self.refs.items() if d < depth and r() is None]
            extra = f' ancestors alive={alive} freed={dead}'
        else:
            node = {'type': 'chain', 'steps': LazySteps(depth, self)}
            extra = ''
        same = [d for d, i in self.ids.items() if i == id(node)]
        self.ids[depth] = id(node)
        reuse = f' <-- SAME ADDRESS AS ANCESTOR depth={same}' if same else ''
        self.events.append(f'create depth={depth} id={id(node):#x}{extra}{reuse}')
        return node


def run(tracked: bool) -> bool:
    trace = Trace(DEPTH, tracked)
    root = trace.make(0)  # the only node the caller holds a reference to
    try:
        result = impl.gather_schemas_for_cleaning(root, DEFS)
    except BaseException as exc:  # noqa: BLE001
        trace.events.append(f'RAISED {type(exc).__name__}: {exc}')
        result = {'collected_references': {}}
    trace.events.append('gather returned')
    for e in trace.events:
        print('   ', e)
    refs = result['collected_references']
    print(f'    collected_references = {refs}')
    present = 'terminal' in refs
    print(f"    terminal reference present: {present}")
    return present


print(f'=== impl={impl_name} depth={DEPTH}: lifetime trace (dict-subclass nodes with __del__ / weakref) ===')
ok_tracked = run(True)
print(f'=== impl={impl_name} depth={DEPTH}: address trace (plain dict nodes) ===')
ok_plain = run(False)
print(f'RESULT impl={impl_name}: terminal present (subclass nodes)={ok_tracked}, (plain dict nodes)={ok_plain}')
raise SystemExit(0 if ok_tracked and ok_plain else 1)
