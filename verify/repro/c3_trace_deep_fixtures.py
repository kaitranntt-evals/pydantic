"""Line-trace the deep regression fixtures: prints every source line each test body executes, so any
iterative teardown loop (or its absence) is observable. Run from repo root of the audited branch:
    python verify/repro/c3_trace_deep_fixtures.py
"""
import gc, sys, importlib.util, pathlib

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

root = pathlib.Path.cwd()
core_mod = load(root / 'pydantic-core/tests/test_schema_gather.py', 'core_sg')
internal_mod = load(root / 'tests/test_internal.py', 'internal')

def run_traced(fn):
    lines = []
    code = fn.__code__
    def tracer(frame, event, arg):
        if frame.f_code is code and event == 'line':
            lines.append(frame.f_lineno)
        return tracer
    gc.collect()
    before = len(gc.get_objects())
    sys.settrace(tracer)
    try:
        fn()
    finally:
        sys.settrace(None)
    gc.collect()
    after = len(gc.get_objects())
    src_lines = open(code.co_filename).read().splitlines()
    print(f'\n### {code.co_filename}::{fn.__name__} (tracked objects before={before} after={after})')
    seen = set()
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            print(f'  L{ln}: {src_lines[ln-1].strip()}')
    print(f'  distinct lines executed: {len(seen)}; total line events: {len(lines)}')

run_traced(core_mod.test_deeply_nested_schema)
run_traced(internal_mod.test_gather_schemas_for_cleaning_deeply_nested_schema)
run_traced(internal_mod.test_clean_schema_deeply_nested_schema)
