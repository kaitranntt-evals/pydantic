# Run: python verify/repro/c3_bookkeeping_cost_probe.py   (same script in each branch's venv; prints best-of-5 wall time and the bookkeeping left in Python)
"""Size/time of gathering a 100k-node schema. Debug-profile (`maturin develop`) builds: compare ratios, not absolutes."""

from __future__ import annotations

import time
import tracemalloc

from pydantic_core import core_schema as cs

import pydantic._internal._schema_gather as sg

definitions = {f'd{i}': cs.int_schema(ref=f'd{i}') for i in range(1000)}


def build():
    fields = {}
    for i in range(1000):
        node = cs.definition_reference_schema(f'd{i}')
        for _ in range(98):
            node = cs.nullable_schema(node)
        fields[f'f{i}'] = cs.typed_dict_field(node)
    return cs.typed_dict_schema(fields)


schema = build()
best = min(
    (lambda t0: (sg.gather_schemas_for_cleaning(schema, definitions), time.perf_counter() - t0)[1])(time.perf_counter())
    for _ in range(5)
)
tracemalloc.start()
result = sg.gather_schemas_for_cleaning(schema, definitions)
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
print(f'nodes=~101k collected={len(result["collected_references"])} best_of_5={best * 1e3:.1f} ms '
      f'python_heap_peak_during_call={peak / 1e6:.2f} MB')
