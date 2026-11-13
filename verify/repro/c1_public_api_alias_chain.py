# Run: <venv>/bin/python verify/repro/c1_public_api_alias_chain.py N   (from a checkout whose pydantic-core is built)
"""C1 through the public API only: a chain of N PEP 695-style type aliases A0 = A1, A1 = A2, ..., A{N-1} = int.

Each alias becomes a definition whose schema is a bare 'definition-ref' to the next alias, i.e. the
"directly linked definition references" shape, with no hand-built core schema involved.
"""
import sys

from typing_extensions import TypeAliasType

from pydantic import TypeAdapter

n = int(sys.argv[1])
alias = int
for i in reversed(range(n)):
    alias = TypeAliasType(f'A{i}', alias)

if len(sys.argv) > 2:  # show the definitions shape handed to the gatherer
    from pydantic._internal import _schema_gather, _generate_schema

    orig = _generate_schema.gather_schemas_for_cleaning

    def spy(schema, definitions):
        kinds = [v['type'] for v in definitions.values()]
        print(f'root={schema["type"]} definitions={len(definitions)} definition-ref targets={kinds.count("definition-ref")}')
        return orig(schema, definitions)

    _generate_schema.gather_schemas_for_cleaning = spy

ta = TypeAdapter(alias)
print(f'aliases={n} OK validate={ta.validate_python("7")!r}', flush=True)
