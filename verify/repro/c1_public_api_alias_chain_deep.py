# Run: <venv>/bin/python verify/repro/c1_public_api_alias_chain_deep.py N   (same as c1_public_api_alias_chain.py, with the Python recursion limit raised so schema generation itself gets past ~100 aliases)
import sys; sys.setrecursionlimit(1000000); sys.argv=['x',sys.argv[1]]
import os; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'c1_public_api_alias_chain.py')).read())
