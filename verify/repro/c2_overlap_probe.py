# Run (from the claim-branch worktree, eval fixture copied byte-exact to tests/): C2_MODE=trace|serialize [C2_WARMUP=1] PYTHONPATH=<this dir> python -m pytest -p c2_overlap_probe tests/test_eval_schema_gather_lifecycle.py -k test_threaded_calls_are_isolated -q -s -p no:cacheprovider
"""pytest plugin: observe (C2_MODE=trace) or forbid (C2_MODE=serialize) overlap of schema-gathering invocations.

It never edits the fixture. Before collection it rebinds, inside ``pydantic._internal._schema_gather``:

* the Python adapter ``gather_schemas_for_cleaning`` (the fixture imports this name afterwards), and
* the native entry point the adapter calls, when the adapter binds it as a module global
  (``_traverse_schema`` on evalon/pydantic-s-705bf332),

with wrappers that record enter/exit timestamps per thread. In ``serialize`` mode the adapter wrapper also
holds one process-wide lock for the whole call, so two gather invocations (and therefore the two native
invocations inside them) can never be in flight at the same time. ``threading.Barrier.wait`` is counted
so the report shows whether the fixture's ``OverlappingBarrierDict.values()`` rendezvous ever ran.
"""

from __future__ import annotations

import os
import threading
import time

import pydantic._internal._schema_gather as sg

MODE = os.environ.get('C2_MODE', 'trace')
assert MODE in ('trace', 'serialize'), MODE

if os.environ.get('C2_WARMUP') == '1':
    # One single-threaded gather of a typed-dict schema before any test runs. PyO3's `intern!` detaches from the
    # interpreter (releases the GIL) the first time each interned-string site is initialised; warming those sites
    # removes that one-off, incidental release from the fixture's stage 2 (see verify/evidence.md#c2).
    from pydantic_core import core_schema as _cs

    sg.gather_schemas_for_cleaning(
        _cs.typed_dict_schema({'f': _cs.typed_dict_field(_cs.definition_reference_schema('w'))}),
        {'w': _cs.int_schema(ref='w')},
    )

_lock = threading.Lock()
_events_lock = threading.Lock()
_intervals: dict[str, list[tuple[int, int, str, str]]] = {'adapter': [], 'native': []}
_barrier_waits: list[str] = []


def _wrap(level: str, func, serialize: bool):
    def wrapper(*args, **kwargs):
        if serialize:
            _lock.acquire()
        start = time.perf_counter_ns()
        outcome = 'ok'
        try:
            return func(*args, **kwargs)
        except BaseException as exc:
            outcome = type(exc).__name__
            raise
        finally:
            end = time.perf_counter_ns()
            with _events_lock:
                _intervals[level].append((start, end, threading.current_thread().name, outcome))
            if serialize:
                _lock.release()

    wrapper.__wrapped__ = func
    return wrapper


_native_name = next(
    (
        name
        for name, value in vars(sg).items()
        if type(value).__name__ == 'builtin_function_or_method'
        and getattr(value, '__module__', '') == 'pydantic_core._pydantic_core'
    ),
    None,
)
if _native_name is not None:
    setattr(sg, _native_name, _wrap('native', getattr(sg, _native_name), False))
sg.gather_schemas_for_cleaning = _wrap('adapter', sg.gather_schemas_for_cleaning, MODE == 'serialize')

_orig_barrier_wait = threading.Barrier.wait


def _counting_wait(self, timeout=None):
    with _events_lock:
        _barrier_waits.append(threading.current_thread().name)
    return _orig_barrier_wait(self, timeout)


threading.Barrier.wait = _counting_wait


def _max_concurrency(intervals) -> int:
    points = sorted([(s, 1) for s, _e, _t, _o in intervals] + [(e, -1) for _s, e, _t, _o in intervals])
    current = best = 0
    for _, delta in points:
        current += delta
        best = max(best, current)
    return best


def pytest_runtest_logreport(report):
    if report.when != 'call':
        return
    with _events_lock:
        snapshot = {level: list(values) for level, values in _intervals.items()}
        waits = list(_barrier_waits)
        for values in _intervals.values():
            values.clear()
        _barrier_waits.clear()
    print(f'\n[c2-probe] mode={MODE} native_entry={_native_name} test={report.nodeid} outcome={report.outcome}')
    for level, values in snapshot.items():
        if not values:
            continue
        print(
            f'[c2-probe]   {level}: calls={len(values)} threads={len({t for _s, _e, t, _o in values})} '
            f'max_simultaneous_in_flight={_max_concurrency(values)} '
            f'outcomes={sorted({o for _s, _e, _t, o in values})}'
        )
        tail = sorted(values)[-2:]
        base = tail[0][0]
        for start, end, thread, outcome in tail:
            print(
                f'[c2-probe]     last-two {level} call on {thread}: enter=+{(start - base) / 1e3:.1f}us '
                f'exit=+{(end - base) / 1e3:.1f}us ({outcome})'
            )
    print(f'[c2-probe]   threading.Barrier.wait calls={len(waits)} threads={sorted(set(waits))}')
    print(
        f'[c2-probe] RESULT outcome={report.outcome} '
        f'gathers_in_flight_together={_max_concurrency(snapshot["native"] or snapshot["adapter"])} '
        f'barrier_waits={len(waits)} warmup={os.environ.get("C2_WARMUP", "0")}'
    )
