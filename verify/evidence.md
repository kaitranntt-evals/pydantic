## C1

Claim: schema gathering uses native call-stack space that grows with the length of a consecutive
definition-reference chain (reference targets that are themselves references, no wrapper in between).

Target: `evalon/pydantic-s-c7dd1857` of `kaitranntt-evals/pydantic-schema-gather-to-core`, commit
`4276473c3cdccd795e6c3f12f4bb9e3f514a8df2`, checked out in a worktree `/home/ubuntu/repos/pyd-c1`
with its own venv `/opt/venv-c1` (Python 3.13, built with the eval's command
`maturin develop --manifest-path pydantic-core/Cargo.toml --uv --frozen`, i.e. the dev profile).
Control: `pydantic-schema-gather-to-core-perfect` (`585c9944900af8d36901073c2eef0ce8d508e215`) in `/opt/venv`.
Host: Linux x86_64, `ulimit -s` = 8192 (kB).

### Traversal path (source, for orientation only)

`pydantic-core/src/schema_gather.rs` on the claim branch: `run()` drives an explicit `Vec<Task>` stack, but
`visit()` (line 306) does `return self.visit_definition_ref(schema, schema_id)` and `visit_definition_ref()`
ends with `self.visit(definition)` (line 340). Both are plain Rust calls, so a definition that is itself a
`definition-ref` re-enters `visit_definition_ref` before the outer call returns. Any other schema type
returns from `visit()` after pushing tasks.

### 1. Native stack pointer per processed reference (`measure`)

Probe: `verify/repro/c1_ref_chain_stack.py`. `definitions` is a `dict` subclass, so the gatherer performs each
target lookup through Python `.get()`; the callback reads the thread's native stack pointer from
`/proc/thread-self/syscall`. Reported: stack pointer at the first lookup minus at the last lookup.

```sh
cd /home/ubuntu/repos/pyd-c1 && /opt/venv-c1/bin/python /home/ubuntu/repos/pydantic/verify/repro/c1_ref_chain_stack.py measure
```

Dev-profile build (the eval's build command):

```console
chain=    1 lookups=    1 native stack growth first->last lookup =        0 bytes (0.0 bytes/ref)
chain=   10 lookups=   10 native stack growth first->last lookup =    22176 bytes (2464.0 bytes/ref)
chain=  100 lookups=  100 native stack growth first->last lookup =   243936 bytes (2464.0 bytes/ref)
chain= 1000 lookups= 1000 native stack growth first->last lookup =  2461536 bytes (2464.0 bytes/ref)
chain= 2000 lookups= 2000 native stack growth first->last lookup =  4925536 bytes (2464.0 bytes/ref)
bash: line 1:  8246 Segmentation fault      (core dumped) $P $R measure
```

(the segfault is the next size, chain=4000.)

Release build (`maturin develop --release ...`, same worktree, then rebuilt back to dev profile):

```console
chain=    1 lookups=    1 native stack growth first->last lookup =        0 bytes (0.0 bytes/ref)
chain=   10 lookups=   10 native stack growth first->last lookup =     3168 bytes (352.0 bytes/ref)
chain=  100 lookups=  100 native stack growth first->last lookup =    34848 bytes (352.0 bytes/ref)
chain= 1000 lookups= 1000 native stack growth first->last lookup =   351648 bytes (352.0 bytes/ref)
chain= 2000 lookups= 2000 native stack growth first->last lookup =   703648 bytes (352.0 bytes/ref)
chain= 4000 lookups= 4000 native stack growth first->last lookup =  1407648 bytes (352.0 bytes/ref)
```

Exactly linear: 2464 bytes (dev) / 352 bytes (release) of native stack per chained reference.

### 2. Crash through `pydantic._internal._schema_gather.gather_schemas_for_cleaning` with plain dicts (`crash N`)

```sh
for n in 10000 20000 50000 100000 200000; do /opt/venv-c1/bin/python $R crash $n; echo "exit=$?"; done
```

Dev profile: every one of these exits 139 (`Segmentation fault (core dumped)`), including the task's
10,000 figure. Bisected thresholds (dev profile), scaling with the stack limit:

```console
ulimit -s 8192: largest surviving chain=3398, smallest crashing=3399
ulimit -s 16384: largest surviving chain=6802, smallest crashing=6803
ulimit -s 32768: largest surviving chain=13611, smallest crashing=13612
```

Release build, `ulimit -s 8192`:

```console
chain=10000 OK collected=10000
release, ulimit -s 8192: largest surviving chain=23803, smallest crashing=23804
```

(50000, 100000, 1000000 all exit 139 in release.)

gdb on the dev build (`gdb -q -batch -ex run -ex 'bt 12' -ex 'bt -8' --args /opt/venv-c1/bin/python $R crash 4000`):

```console
Program received signal SIGSEGV, Segmentation fault.
#1  0x00007ffff6b93f13 in _pydantic_core::schema_gather::get_required (...) at src/schema_gather.rs:147
#2  0x00007ffff6b915ab in _pydantic_core::schema_gather::GatherContext::visit_definition_ref (self=0x7fffffffcee0, def_ref_schema=..., schema_id=140737326817344) at src/schema_gather.rs:319
#3  0x00007ffff6b9309f in _pydantic_core::schema_gather::GatherContext::visit (self=0x7fffffffcee0, schema=...) at src/schema_gather.rs:306
#4  0x00007ffff6b91ab7 in _pydantic_core::schema_gather::GatherContext::visit_definition_ref (self=0x7fffffffcee0, def_ref_schema=..., schema_id=140737326817280) at src/schema_gather.rs:339
#5  0x00007ffff6b9309f in _pydantic_core::schema_gather::GatherContext::visit (self=0x7fffffffcee0, schema=...) at src/schema_gather.rs:306
#6  0x00007ffff6b91ab7 in _pydantic_core::schema_gather::GatherContext::visit_definition_ref (...) at src/schema_gather.rs:339
...
#6826 0x00000000019348b0 in main ()
```

`gdb ... -ex bt ... | grep -c visit_definition_ref` → `3401` active `visit_definition_ref` frames at the crash.

### 3. Controls

Same branch, same API, 1,000,000 nested `nullable` wrappers (no reference chain) — bounded:

```console
$ /opt/venv-c1/bin/python $R control 1000000
nullable depth=1000000 OK
exit=0
```

`pydantic-schema-gather-to-core-perfect` (dev profile), same chain script:

```console
chain=10000 OK collected=10000
exit=0
chain=1000000 OK collected=1000000
exit=0
```

(`measure` does not apply there: that implementation never calls the subclass `.get()`.)

### 4. Reachability from the public API

`verify/repro/c1_public_api_alias_chain.py` builds `A0 = A1 = ... = A{N-1} = int` with `TypeAliasType` and calls
`TypeAdapter(A0)`. With a spy on the gatherer call:

```console
$ /opt/venv-c1/bin/python verify/repro/c1_public_api_alias_chain.py 5 spy
root=definition-ref definitions=5 definition-ref targets=4
aliases=5 OK validate=7
```

So ordinary chained type aliases produce exactly the claimed shape. At the default Python recursion limit the
chain cannot get long enough to matter, because Python-side schema generation fails first:

```console
aliases=100 OK validate=7
exit=0
RecursionError: maximum recursion depth exceeded        # N=300, 500, 2000, 5000 — exit=1
```

With `sys.setrecursionlimit(1000000)` (`verify/repro/c1_public_api_alias_chain_deep.py`), dev build:

```console
$ /opt/venv-c1/bin/python verify/repro/c1_public_api_alias_chain_deep.py 3000
aliases=3000 OK validate=7
$ gdb -q -batch -ex run -ex 'bt 6' --args /opt/venv-c1/bin/python verify/repro/c1_public_api_alias_chain_deep.py 5000
Program received signal SIGSEGV, Segmentation fault.
#4  hashbrown::raw::RawTableInner::find_or_find_insert_index_inner (...)
#5  0x00007ffff6b71e59 in hashbrown::raw::RawTable<(usize, _pydantic_core::schema_gather::Visited), alloc::alloc::Global>::find_or_find_insert_index<...>
```

Release build of the claim branch: N=30000 exits 139 with the faulting frames inside `_pydantic_core...so`
(symbols stripped; one return address `0x00007ffff70b5349` repeated in every frame). The `-perfect` branch:

```console
aliases=3000 OK validate=7
perfect exit=0
aliases=30000 OK validate=7
perfect exit=0
```

### 5. Eval fixtures do not exercise the shape

Archive fixtures copied byte-exact into the claim worktree's `tests/` (removed afterwards):

```console
$ /opt/venv-c1/bin/python -m pytest tests/test_eval_schema_gather_depth.py tests/test_eval_schema_gather_references.py -q -p no:cacheprovider
...............                                                          [100%]
        15 passed
```

### Impact reasoning

- The behavior is real and exactly as claimed: two native frames (`visit` → `visit_definition_ref`) stay
  active per chained reference; stack use is linear (2464 B/ref dev, 352 B/ref release) and ends in a
  process-killing SIGSEGV rather than a Python exception — worse than the `RecursionError` the task set
  out to remove. Nested wrappers on the same branch are bounded, so the defect is specific to this path.
- The task requires "at least 10,000 nested schema levels ... without ... requiring a native call stack
  proportional to schema depth". A 10,000-reference chain segfaults on the eval's own (dev-profile) build
  with the default 8 MiB stack and survives a release build only because 352 B × 10,000 fits; threads with
  smaller stacks (e.g. 512 KiB–1 MiB) would lower the release threshold proportionally (not run).
- Triggering situation: chained type aliases generate the shape naturally, but default-recursion-limit
  Python code cannot generate more than a few hundred links, so ordinary users do not reach the crash.
  It needs a raised recursion limit or hand-built core schemas passed to the gatherer.
- Both fixture files named by the claim pass on this branch, so the checks do not detect it.
