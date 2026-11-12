# Run (claim branch evalon/pydantic-s-734c6460 built into its own venv):
#   cd <worktree of the claim branch> && /opt/venv-734c6460/bin/python <path>/c6_public_exports_vs_docs.py
"""C6: compare `pydantic_core.__all__` with the explicit member list of docs/api/pydantic_core.md.

Exit status 0 = gathering symbols are public but undocumented (problem reproduced), 1 = otherwise.
"""
import re
import sys
from pathlib import Path

import pydantic_core

exported = list(pydantic_core.__all__)
documented = re.findall(r'^\s+- (\S+)\s*$', Path('docs/api/pydantic_core.md').read_text(), flags=re.M)
gather = [n for n in exported if re.search(r'gather|MissingDefinition', n, flags=re.I)]
print('pydantic_core file:', pydantic_core.__file__)
print('gathering symbols in pydantic_core.__all__:', gather)
for n in gather:
    obj = getattr(pydantic_core, n)
    print(f'  {n}: importable={obj is not None} module={getattr(obj, "__module__", None)} in docs member list={n in documented}')
print('all __all__ entries absent from the docs member list:', sorted(set(exported) - set(documented)))
print('docs members absent from __all__:', sorted(set(documented) - set(exported)))
bad = [n for n in gather if n not in documented]
print('RESULT:', f'{len(bad)} public gathering symbol(s) undocumented: {bad}' if bad else 'no undocumented public gathering symbol')
sys.exit(0 if bad else 1)
