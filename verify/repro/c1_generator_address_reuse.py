# Run: /opt/venv/bin/python verify/repro/c1_generator_address_reuse.py   (from the repo root, after `maturin develop`)
"""C1: a distinct generator-produced schema is skipped when it is allocated at the address of a
completed, already released generator-produced schema whose address is still in `visited`.

Exit status 0 = the stale-address skip was reproduced, 1 = not reproduced.
"""
import sys
import weakref

from pydantic._internal._schema_gather import MissingDefinitionError, gather_schemas_for_cleaning

N = 50


class Node(dict):
    """dict subclass so that it can be weak-referenced (lifetime tracing only)."""


# --- Part 1 (lifetime): is a completed generator-produced schema released before a later branch runs?
state = {}


def first_traced():
    s = Node(type='int')
    state['ref'] = weakref.ref(s)
    yield s


def second_traced():
    state['first_alive_when_second_branch_starts'] = state['ref']() is not None
    yield Node(type='str')


gather_schemas_for_cleaning(
    {
        'type': 'union',
        'choices': [{'type': 'chain', 'steps': first_traced()}, {'type': 'chain', 'steps': second_traced()}],
    },
    {},
)
print('lifetime: first-branch schema still alive when the second generator branch starts:',
      state['first_alive_when_second_branch_starts'])

# --- Part 2 (traversal): plain dicts, two independent generator branches.
first_ids = set()
second = []  # (index, address)


def first_branch():
    for _ in range(N):
        s = {'type': 'int'}
        first_ids.add(id(s))
        yield s


def second_branch(make):
    for i in range(N):
        s = make(i)
        second.append((i, id(s)))
        yield s


def schema(make):
    first_ids.clear()
    second.clear()
    return {
        'type': 'union',
        'choices': [{'type': 'chain', 'steps': first_branch()}, {'type': 'chain', 'steps': second_branch(make)}],
    }


# A: every second-branch schema is a distinct definition-ref to an existing definition.
definitions = {f'r{i}': {'type': 'str'} for i in range(N)}
result = gather_schemas_for_cleaning(schema(lambda i: {'type': 'definition-ref', 'schema_ref': f'r{i}'}), definitions)
reused = [i for i, addr in second if addr in first_ids]
collected = result['collected_references']
skipped = [i for i, _ in second if f'r{i}' not in collected]
print(f'A: second-branch schemas allocated at an address of a released first-branch schema: {len(reused)}/{N}')
print(f'A: second-branch definition-refs absent from collected_references (skipped): {len(skipped)}/{N}')
print(f'A: skipped == reused-address set: {skipped == reused}; refs at fresh addresses collected: '
      f'{all(f"r{i}" in collected for i, a in second if a not in first_ids)}')
a_bug = bool(skipped) and skipped == reused

# B: every second-branch schema references a MISSING definition -> must raise MissingDefinitionError.
try:
    gather_schemas_for_cleaning(schema(lambda i: {'type': 'definition-ref', 'schema_ref': 'missing'}), {})
    outcome = 'no exception'
except MissingDefinitionError as e:
    outcome = f'MissingDefinitionError({e.schema_reference!r})'
reused_b = [i for i, addr in second if addr in first_ids]
print(f'B: reused addresses: {len(reused_b)}/{N}; outcome for {N} refs to a missing definition: {outcome}')
b_bug = len(reused_b) == N and outcome == 'no exception'

# Control: same schemas held in lists (all objects alive, no address reuse).
held = {
    'type': 'union',
    'choices': [
        {'type': 'chain', 'steps': [{'type': 'int'} for _ in range(N)]},
        {'type': 'chain', 'steps': [{'type': 'definition-ref', 'schema_ref': f'r{i}'} for i in range(N)]},
    ],
}
print('control (list-held): collected', len(gather_schemas_for_cleaning(held, definitions)['collected_references']), f'of {N}')

print('RESULT:', 'STALE-ADDRESS SKIP REPRODUCED' if a_bug else 'not reproduced', f'(A={a_bug}, B={b_bug})')
sys.exit(0 if a_bug else 1)
