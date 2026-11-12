#!/bin/bash
# Run: verify/repro/c9_lint_rust.sh   (from the repo root; needs cargo with clippy 0.1.99 on PATH)
# C9: the Rust lint command fails on pre-existing code. Exit status 0 = lint-rust failed (reproduced).
make -C pydantic-core lint-rust 2>&1 | grep -E '^error|-->|Error'
status=${PIPESTATUS[0]}
echo "make -C pydantic-core lint-rust exit=$status"
echo "files touched by the solution among the flagged ones:"
git diff --stat a2c935478b7f4d51d6d781d1c95339c8d69c05d0 585c9944900af8d36901073c2eef0ce8d508e215 -- pydantic-core/src/definitions.rs | wc -l
[ "$status" -ne 0 ]
