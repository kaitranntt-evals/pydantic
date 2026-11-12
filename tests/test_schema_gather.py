"""Regression coverage for deep core schema gathering.

A dataclass or TypedDict model nested thousands of levels deep used to raise
``RecursionError`` while the core schema was gathered for cleaning.
"""

from __future__ import annotations

from typing import Any

from pydantic_core import core_schema as cs

from pydantic._internal._schema_gather import gather_schemas_for_cleaning

DEPTH = 2_500


def test_deeply_nested_schema() -> None:
    schema: Any = cs.definition_reference_schema('deep')
    for _ in range(DEPTH):
        schema = cs.nullable_schema(schema)

    result = gather_schemas_for_cleaning(schema, {'deep': cs.int_schema(ref='deep')})

    assert list(result['collected_references']) == ['deep']
    assert result['deferred_discriminator_schemas'] == []
