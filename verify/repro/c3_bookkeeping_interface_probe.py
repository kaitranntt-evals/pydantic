# Run: python verify/repro/c3_bookkeeping_interface_probe.py   (with the venv built from evalon/pydantic-s-705bf332; exits 1 if the claim holds)
"""Observe who allocates the traversal bookkeeping (visited spans, encountered references) for native gathering."""

from __future__ import annotations

import inspect
import sys

import pydantic_core._pydantic_core as core
from pydantic_core import core_schema as cs

import pydantic._internal._schema_gather as sg
from pydantic import BaseModel

natives = {n: getattr(core, n) for n in dir(core) if 'gather' in n or 'traverse' in n}
print('native gathering entry points exported by pydantic_core._pydantic_core:')
for name, func in natives.items():
    print(f'  {name}{getattr(func, "__text_signature__", None)}')

native_name = next((n for n in natives if getattr(sg, n, None) is natives[n]), None)
if native_name is None:
    print('the Python adapter does not bind a native entry point taking containers; inspect it manually')
    print(inspect.getsource(sg.gather_schemas_for_cleaning))
    sys.exit(0)
native = natives[native_name]
required = [p for p in inspect.signature(native).parameters.values() if p.default is p.empty]
print(f'required positional parameters of {native_name}: {[p.name for p in required]} ({len(required)})')

ref = cs.definition_reference_schema('leaf')
shared = cs.list_schema(ref)
schema = cs.tuple_schema([shared, shared])
definitions = {'leaf': cs.int_schema(ref='leaf')}

print('\n1. calling the native entry point with only the schema, the definitions and the error type:')
try:
    native(schema, definitions, sg.MissingDefinitionError)
    print('   accepted')
except TypeError as exc:
    print(f'   TypeError: {exc}')

print('\n2. calling it with the result containers but no traversal bookkeeping (visited=None, encountered_refs=None):')
try:
    native(schema, definitions, {}, [], None, None, sg.MissingDefinitionError)
    print('   accepted')
except TypeError as exc:
    print(f'   TypeError: {exc}')

print('\n3. tracing what the Python adapter passes for one gather_schemas_for_cleaning() call:')
contexts: list[sg.GatherContext] = []
calls: list[tuple] = []
original_context, original_native = sg.GatherContext, native


class RecordingContext(original_context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        contexts.append(self)


def recording_native(*args, **kwargs):
    calls.append((args, kwargs, [(type(a).__name__, len(a) if isinstance(a, (dict, list)) else None) for a in args]))
    return original_native(*args, **kwargs)


sg.GatherContext = RecordingContext
setattr(sg, native_name, recording_native)
try:
    result = sg.gather_schemas_for_cleaning(schema, definitions)
    n_single = len(calls)

    class Leaf(BaseModel):
        x: int

    class Tree(BaseModel):
        leaf: Leaf
        children: list[Tree] = []

    n_model = len(calls) - n_single
finally:
    sg.GatherContext = original_context
    setattr(sg, native_name, original_native)

args, kwargs, before = calls[0]
ctx = contexts[0]
print(f'   native call: {len(args)} positional, {len(kwargs)} keyword arguments')
print(f'   argument (type, len) on entry: {before}')
names = ['schema', 'definitions', 'collected_references', 'deferred_discriminator_schemas', 'visited', 'encountered_refs']
allocated_by_python = {
    'collected_references': args[2] is ctx.collected_references,
    'deferred_discriminator_schemas': args[3] is ctx.deferred_discriminator_schemas,
    'visited': args[4] is ctx.visited,
    'encountered_refs': args[5] is ctx.encountered_refs,
}
for name, same in allocated_by_python.items():
    print(f'   args[{names.index(name)}] is the Python-allocated GatherContext.{name}: {same}')
print(f'   after the native call, Python-owned visited = {ctx.visited == {} and "{}" or sorted(ctx.visited.values())}')
print(f'   after the native call, Python-owned encountered_refs = {ctx.encountered_refs}')
print(f"   returned collected_references is the Python-allocated dict: {result['collected_references'] is ctx.collected_references}")
print(f'   defining two BaseModel classes (real call site, GenerateSchema.clean_schema) made {n_model} more native call(s), '
      f'each with {sorted({len(c[0]) for c in calls[n_single:]})} positional args and Python-allocated containers: '
      f'{all(any(c[0][4] is x.visited and c[0][5] is x.encountered_refs for x in contexts) for c in calls[n_single:])}')

holds = len(required) == 7 and all(allocated_by_python.values()) and bool(ctx.visited) and bool(ctx.encountered_refs)
print(f'\nPython allocates and passes traversal bookkeeping as required native arguments: {holds}')
sys.exit(1 if holds else 0)
