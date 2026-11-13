# Run: bash verify/repro/c3_run.sh   (type-checks this file against the e6353b87 stubs and the base stubs)
from pydantic_core import Some


class MySome(Some[int]):
    pass
