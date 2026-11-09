# Run (copy next to the eval fixtures in the claim-branch worktree): python -m pytest tests/c2_overlap_required_test.py -q -p no:cacheprovider
"""C2 repro: the fixture's rendezvous is skipped on evalon/pydantic-s-705bf332, so its stage 2 proves no overlap.

* ``test_fixture_stage_two_rendezvous_ran`` is stage 2 of ``test_threaded_calls_are_isolated`` (eval fixture
  ``tests/test_eval_schema_gather_lifecycle.py``) verbatim, plus one assertion that both workers actually met
  at the barrier. It fails wherever the fixture passes vacuously.
* ``test_overlap_forced_through_metadata_membership`` moves the rendezvous to the deferred-discriminator
  metadata membership check, which the gatherer has to perform from inside the native call, and asserts the same
  isolation properties. It distinguishes per-call state from state shared across calls.
"""

from __future__ import annotations

import concurrent.futures
import threading
from typing import Any

from pydantic_core import core_schema as cs

from pydantic._internal._schema_gather import gather_schemas_for_cleaning


def test_fixture_stage_two_rendezvous_ran() -> None:
    barrier = threading.Barrier(2)
    met: list[str] = []

    class OverlappingBarrierDict(dict):
        def values(self) -> Any:
            barrier.wait(timeout=5)
            met.append(threading.current_thread().name)
            return super().values()

    def overlapping_worker(name: str) -> dict[str, Any]:
        def_ref = cs.definition_reference_schema(name)
        fields = OverlappingBarrierDict({'f': cs.typed_dict_field(def_ref)})
        schema = cs.typed_dict_schema(fields)
        definitions = {name: cs.int_schema(ref=name)}
        return gather_schemas_for_cleaning(schema, definitions)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(overlapping_worker, 'thread_a')
        f2 = executor.submit(overlapping_worker, 'thread_b')
        res_a = f1.result(timeout=10)
        res_b = f2.result(timeout=10)
        assert list(res_a['collected_references'].keys()) == ['thread_a']
        assert list(res_b['collected_references'].keys()) == ['thread_b']
        assert res_a['collected_references']['thread_a']['schema_ref'] == 'thread_a'
        assert res_b['collected_references']['thread_b']['schema_ref'] == 'thread_b'

    # The only addition: the two in-flight gathers must really have met inside `values()`.
    assert len(set(met)) == 2, f'barrier rendezvous never ran (threads that reached it: {met}); no overlap was established'


def test_overlap_forced_through_metadata_membership() -> None:
    barrier = threading.Barrier(2)
    met: list[str] = []

    class RendezvousMetadata(dict):
        def __contains__(self, key: object) -> bool:
            barrier.wait(timeout=5)
            met.append(threading.current_thread().name)
            return super().__contains__(key)

    def overlapping_worker(name: str) -> dict[str, Any]:
        def_ref = cs.definition_reference_schema(name)
        schema = cs.typed_dict_schema({'f': cs.typed_dict_field(def_ref)})
        # The root's metadata is checked after its children, i.e. while this call's reference state is populated.
        schema['metadata'] = RendezvousMetadata()
        definitions = {name: cs.int_schema(ref=name)}
        return gather_schemas_for_cleaning(schema, definitions)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(overlapping_worker, 'thread_a')
        f2 = executor.submit(overlapping_worker, 'thread_b')
        res_a = f1.result(timeout=10)
        res_b = f2.result(timeout=10)

    assert len(set(met)) == 2, f'barrier rendezvous never ran (threads that reached it: {met})'
    assert list(res_a['collected_references'].keys()) == ['thread_a']
    assert list(res_b['collected_references'].keys()) == ['thread_b']
    assert res_a['collected_references']['thread_a']['schema_ref'] == 'thread_a'
    assert res_b['collected_references']['thread_b']['schema_ref'] == 'thread_b'
