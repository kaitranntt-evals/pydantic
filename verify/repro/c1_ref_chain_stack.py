# Run: <venv>/bin/python verify/repro/c1_ref_chain_stack.py measure|crash N|control N   (from a checkout whose pydantic-core is built)
"""C1 probe: native stack use of schema gathering over a chain of directly linked definition references.

definitions = {'r0': ref(r1), 'r1': ref(r2), ..., 'r{N-1}': int}, root = ref(r0).

`measure`: `definitions` is a dict subclass, so the gatherer looks targets up through the Python-level `.get()`.
Inside that callback we read the calling thread's native stack pointer from /proc/thread-self/syscall
(field 8) -- i.e. how deep the native stack is at the moment the k-th reference is being processed.
`crash N`: plain dicts, chain of N references, through the public pydantic._internal._schema_gather API.
`control N`: N nested nullable wrappers (no reference chain), same API.
"""
import sys

from pydantic._internal._schema_gather import gather_schemas_for_cleaning


def chain(n):
    defs = {f'r{i}': {'type': 'definition-ref', 'schema_ref': f'r{i + 1}'} for i in range(n - 1)}
    defs[f'r{n - 1}'] = {'type': 'int'}
    return {'type': 'definition-ref', 'schema_ref': 'r0'}, defs


def native_sp():
    with open('/proc/thread-self/syscall') as f:
        return int(f.read().split()[7], 16)


class ProbeDefs(dict):
    def __init__(self, *a):
        super().__init__(*a)
        self.sps = []

    def get(self, key, default=None):
        self.sps.append(native_sp())
        return super().get(key, default)


mode = sys.argv[1]
if mode == 'measure':
    for n in (1, 10, 100, 1000, 2000, 4000):
        root, defs = chain(n)
        defs = ProbeDefs(defs)
        res = gather_schemas_for_cleaning(root, defs)
        assert len(res['collected_references']) == n
        used = defs.sps[0] - defs.sps[-1]
        print(f'chain={n:5d} lookups={len(defs.sps):5d} native stack growth first->last lookup = {used:8d} bytes'
              f' ({used / max(n - 1, 1):.1f} bytes/ref)', flush=True)
elif mode == 'crash':
    n = int(sys.argv[2])
    root, defs = chain(n)
    res = gather_schemas_for_cleaning(root, defs)
    print(f'chain={n} OK collected={len(res["collected_references"])}', flush=True)
elif mode == 'control':
    n = int(sys.argv[2])
    s = {'type': 'int'}
    for _ in range(n):
        s = {'type': 'nullable', 'schema': s}
    res = gather_schemas_for_cleaning(s, {})
    print(f'nullable depth={n} OK', flush=True)
    import os
    os._exit(0)  # skip recursive dealloc of the nested dicts
