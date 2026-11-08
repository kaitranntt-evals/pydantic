# Repro scripts for run v-a7b6ca56

- `reference_schema_gather.py` — unmodified copy of `pydantic/_internal/_schema_gather.py` at `a2c935478` (pre-change Python traversal), used as the oracle.
- `c1_c2_iterable_interleaving_probe.py` — C1/C2: `cd /home/ubuntu/repos/pydantic && /opt/venv/bin/python verify/repro/c1_c2_iterable_interleaving_probe.py` (exit 1 = native and reference differ).
- `c3_dataclass_args_order_probe.py` — C3: run from a checkout of `evalon/pydantic-s-03297959` with its built venv, e.g. `cd /home/ubuntu/repos/pydantic-c3 && /opt/venv-c3/bin/python /home/ubuntu/repos/pydantic/verify/repro/c3_dataclass_args_order_probe.py` (exit 1 = differ).
- `c4_typed_dict_py310_311.sh` — C4: builds `evalon/pydantic-s-44e1e127` on Python 3.10 and 3.11 and runs the delivered gather tests.
