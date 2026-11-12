# Run (claim branch evalon/pydantic-s-d2a5977c built into its own venv):
#   cd <worktree of the claim branch> && /opt/venv-d2a5977c/bin/python <path>/c4_wrapper_address_reuse.py
"""C4: a temporary (generator-produced) schema wrapper is released when completed while its address
stays in the visited cache; a later generating branch gets a distinct wrapper at that address, which is
then treated as already visited (child skipped / unrelated reference marked non-inlinable).

Exit status 0 = reproduced, 1 = not reproduced.
"""
import sys
import weakref

from pydantic._internal._schema_gather import MissingDefinitionError, gather_schemas_for_cleaning

N = 50


class Node(dict):
    """dict subclass so that it can be weak-referenced (lifetime tracing only)."""


# --- Part 1 (lifetime)
state = {}


def first_traced():
    s = Node(type='int')
    state['ref'] = weakref.ref(s)
    yield s


def second_traced():
    state['alive'] = state['ref']() is not None
    yield Node(type='str')


gather_schemas_for_cleaning(
    {'type': 'union', 'choices': [{'type': 'chain', 'steps': first_traced()}, {'type': 'chain', 'steps': second_traced()}]},
    {},
)
print('lifetime: completed first-branch wrapper still alive when the second generating branch starts:', state['alive'])

first_ids = set()
second = []


def first_branch(make):
    for i in range(N):
        s = make(i)
        first_ids.add(id(s))
        yield s


def second_branch(make):
    for i in range(N):
        s = make(i)
        second.append((i, id(s)))
        yield s


def schema(make_first, make_second):
    first_ids.clear()
    second.clear()
    return {
        'type': 'union',
        'choices': [
            {'type': 'chain', 'steps': first_branch(make_first)},
            {'type': 'chain', 'steps': second_branch(make_second)},
        ],
    }


# --- Part 2a: child skipped. Second branch wrappers each wrap a distinct definition-ref.
definitions = {f'r{i}': {'type': 'str'} for i in range(N)}
definitions['shared'] = {'type': 'int'}
res = gather_schemas_for_cleaning(
    schema(lambda i: {'type': 'int'}, lambda i: {'type': 'definition-ref', 'schema_ref': f'r{i}'}), definitions
)['collected_references']
reused = [i for i, a in second if a in first_ids]
skipped = [i for i, _ in second if f'r{i}' not in res]
print(f'skip: second-branch wrappers at a retained address: {len(reused)}/{N}; '
      f'their definition-refs missing from collected_references: {len(skipped)}/{N}; same set: {reused == skipped}')
skip_bug = bool(skipped) and reused == skipped

# --- Part 2b: missing definition silently accepted.
try:
    gather_schemas_for_cleaning(schema(lambda i: {'type': 'int'}, lambda i: {'type': 'definition-ref', 'schema_ref': 'nope'}), {})
    outcome = 'no exception'
except MissingDefinitionError as e:
    outcome = f'MissingDefinitionError({e.schema_reference!r})'
print(f'skip: {N} fresh refs to a missing definition in the second branch -> {outcome} '
      f'(reused addresses {sum(a in first_ids for _, a in second)}/{N})')

# --- Part 2c: unrelated reference marked non-inlinable. Each first-branch wrapper is a temporary `list`
# schema whose item is the single reference to definition `u{i}` (the definition-ref object itself stays
# alive in `collected_references`, the wrapper does not); second-branch wrappers are unrelated `int` schemas.
definitions = {f'u{i}': {'type': 'str'} for i in range(N)}
res = gather_schemas_for_cleaning(
    schema(lambda i: {'type': 'list', 'items_schema': {'type': 'definition-ref', 'schema_ref': f'u{i}'}}, lambda i: {'type': 'int'}),
    definitions,
)['collected_references']
non_inlinable = [k for k, v in res.items() if v is None]
print(f'non-inlinable: single-use references u0..u{N - 1} marked non-inlinable (None): {len(non_inlinable)}/{N} '
      f'(second-branch wrappers at a retained address: {sum(a in first_ids for _, a in second)}/{N})')
inline_bug = bool(non_inlinable)

# control: identical shapes held in lists
held = {
    'type': 'union',
    'choices': [
        {'type': 'chain', 'steps': [{'type': 'list', 'items_schema': {'type': 'definition-ref', 'schema_ref': f'u{i}'}} for i in range(N)]},
        {'type': 'chain', 'steps': [{'type': 'int'} for _ in range(N)]},
    ],
}
res = gather_schemas_for_cleaning(held, definitions)['collected_references']
print('control (list-held wrappers): non-inlinable', sum(v is None for v in res.values()), f'of {len(res)}')

print('RESULT:', 'REPRODUCED' if (skip_bug or inline_bug) else 'not reproduced', f'(skip={skip_bug}, non_inlinable={inline_bug})')
sys.exit(0 if (skip_bug or inline_bug) else 1)
