# Run (claim branch evalon/pydantic-s-e2125aea built into its own venv /opt/venv-e2125aea):
#   cd <worktree of the claim branch> && /opt/venv-e2125aea/bin/python <path>/c8_adapter_leftovers.py
"""C8: leftovers in the thin adapter pydantic/_internal/_schema_gather.py.

Part 1: module-level names (imports / assignments) never referenced in the module nor anywhere else in the repo.
Part 2: is the file-wide `# pyright:` suppression still needed? pyright is run on the file as delivered and on
        a copy with only that comment line removed (the file is restored afterwards).
Exit status 0 = unused traversal declarations AND a no-longer-needed file-wide suppression were observed.
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

path = Path('pydantic/_internal/_schema_gather.py')
src = path.read_text()
tree = ast.parse(src)

defined = {}
for node in tree.body:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        for a in node.names:
            defined[a.asname or a.name] = f'import (line {node.lineno})'
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        for t in node.targets if isinstance(node, ast.Assign) else [node.target]:
            if isinstance(t, ast.Name):
                defined[t.id] = f'assignment (line {node.lineno})'
used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
# string annotations (`from __future__ import annotations` keeps annotations as AST, type alias strings do not)
strings = ' '.join(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) < 200)
print('module-level imports/assignments:', defined)
unused = []
for name, kind in defined.items():
    if name in used or name in ('annotations', '__all__'):
        continue
    only_in_alias = name in strings
    grep = subprocess.run(
        ['git', 'grep', '-n', '-w', name, '--', 'pydantic', 'tests', 'pydantic-core/python', 'pydantic-core/tests'],
        capture_output=True, text=True,
    ).stdout.splitlines()
    external = [line for line in grep if not line.startswith(str(path) + ':') and '_schema_gather' in line]
    if external:
        continue  # re-exported: used by other modules
    print(f'  {name}: {kind}; referenced by executable code in the adapter: False; '
          f'appears only inside a string alias: {only_in_alias}; importers elsewhere: {external}')
    unused.append(name)
print('unused traversal-only declarations/imports:', unused)

directive = next((line for line in src.splitlines() if line.startswith('# pyright:')), None)
print('file-wide directive:', directive)


def pyright():
    exe = os.path.join(os.path.dirname(sys.executable), 'pyright')
    r = subprocess.run([exe, '--pythonpath', sys.executable, str(path)], capture_output=True, text=True)
    lines = [line for line in r.stdout.splitlines() if ' - error' in line or ' - warning' in line or 'errors, ' in line]
    return r.returncode, lines


suppression_unneeded = False
if directive:
    print('pyright, file as delivered:      ', pyright())
    try:
        path.write_text(src.replace(directive + '\n', '', 1))
        rc, summary = pyright()
        print('pyright, file-wide directive removed:', (rc, summary))
        suppression_unneeded = rc == 0
    finally:
        path.write_text(src)
print('RESULT: unused declarations:', bool(unused), '| file-wide suppression no longer needed:', suppression_unneeded)
sys.exit(0 if (unused and suppression_unneeded) else 1)
