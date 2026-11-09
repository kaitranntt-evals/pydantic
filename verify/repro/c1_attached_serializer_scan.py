# Run (from the claim-branch worktree): PYTHONPATH=<this dir> python -m pytest -p c1_attached_serializer_scan <test files> -q -s -p no:cacheprovider
"""pytest plugin: record, per test, what every schema handed to the gatherer contains behind attached serializers.

It wraps the Python adapter (``gather_schemas_for_cleaning``, ``traverse_schema``, ``traverse_definition_ref``)
and the native delegate (any ``pydantic_core._pydantic_core`` builtin whose name contains ``gather`` or
``traverse``) before test modules are imported, then walks each (schema, definitions) input in pure Python.

For every node that carries a ``serialization`` attachment S it classifies S:

* ``direct``: S itself is a ``definition-ref`` or carries the deferred-discriminator metadata key;
* ``combined``: S has a ``schema`` or ``return_schema`` field whose subtree contains a ``definition-ref``
  or a node carrying the deferred-discriminator metadata key (the path claim C1 is about);
* ``other``: neither.
"""

from __future__ import annotations

import collections

import pydantic_core._pydantic_core as core

MARKER = 'pydantic_internal_union_discriminator'
_current = {'nodeid': None}
_stats: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)


def _children(node):
    if isinstance(node, dict):
        for key, value in dict.items(node):
            if key == 'metadata':
                continue
            yield key, value
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield None, value


def _interesting(node) -> bool:
    return isinstance(node, dict) and (
        dict.get(node, 'type') == 'definition-ref' or (isinstance(dict.get(node, 'metadata'), dict) and MARKER in node['metadata'])
    )


def _subtree_has_interesting(root) -> bool:
    seen, stack = set(), [root]
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if _interesting(node):
            return True
        stack.extend(value for _key, value in _children(node))
    return False


def _scan(schema, definitions=None) -> None:
    counter = _stats[_current['nodeid']]
    counter['gather_calls'] += 1
    # `definitions` maps reference names to schemas: it is not itself a schema node, so only its values are roots
    # (otherwise a definition that happens to be named 'serialization' would be miscounted as an attachment).
    seen, stack = set(), [schema, *(dict.values(definitions) if isinstance(definitions, dict) else [])]
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, dict) and isinstance(dict.get(node, 'serialization'), dict):
            attached = node['serialization']
            counter['serialization_attachments'] += 1
            combined = [
                field
                for field in ('schema', 'return_schema')
                if field in attached and _subtree_has_interesting(attached[field])
            ]
            if combined:
                counter['combined'] += 1
                for field in combined:
                    counter[f'combined_via_{field}'] += 1
            elif _interesting(attached):
                counter['direct'] += 1
            else:
                counter['other'] += 1
        stack.extend(value for _key, value in _children(node))


def _wrap(func, picker):
    def wrapper(*args, **kwargs):
        try:
            _scan(*picker(args, kwargs))
        except Exception as exc:  # the scan must never change a test outcome
            _stats[_current['nodeid']][f'scan_error_{type(exc).__name__}'] += 1
        return func(*args, **kwargs)

    wrapper.__wrapped__ = func
    return wrapper


_native_names = [
    name
    for name, value in vars(core).items()
    if type(value).__name__ == 'builtin_function_or_method' and ('gather' in name or 'traverse' in name)
]
for _name in _native_names:
    # native delegates take (schema, definitions, ...) positionally on both audited branches
    setattr(core, _name, _wrap(getattr(core, _name), lambda a, k: a[:2]))

import pydantic._internal._schema_gather as sg  # noqa: E402  (imported after the native delegate is wrapped)

sg.gather_schemas_for_cleaning = _wrap(sg.gather_schemas_for_cleaning, lambda a, k: a[:2])
for _name in ('traverse_schema', 'traverse_definition_ref'):
    if hasattr(sg, _name):
        setattr(sg, _name, _wrap(getattr(sg, _name), lambda a, k: (a[0], getattr(a[1], 'definitions', {}))))


def pytest_runtest_setup(item):
    _current['nodeid'] = item.nodeid


def pytest_terminal_summary(terminalreporter):
    write = terminalreporter.write_line
    write(f'[c1-scan] wrapped native delegates: {_native_names}')
    total = collections.Counter()
    tests_with_calls = 0
    for nodeid, counter in sorted(_stats.items(), key=lambda kv: str(kv[0])):
        if not counter['gather_calls']:
            continue
        tests_with_calls += 1
        total.update(counter)
        if counter['serialization_attachments']:
            write(f'[c1-scan] {nodeid}: {dict(counter)}')
    write(f'[c1-scan] tests that invoked the gatherer: {tests_with_calls}')
    write(f'[c1-scan] TOTAL: {dict(total)}')
    write(f"[c1-scan] attachments reaching a definition-ref/discriminator through schema|return_schema: {total['combined']}")
