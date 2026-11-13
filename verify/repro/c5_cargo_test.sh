#!/bin/bash
# Run: bash verify/repro/c5_cargo_test.sh   (from the repo root; needs /opt/venv built per the eval's startup.sh)
cd "$(dirname "$0")/../../pydantic-core" || exit 1
echo '--- cargo test with the startup.sh environment (VIRTUAL_ENV=/opt/venv)'
VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH cargo test 2>&1 | grep -E "Running|running|test result|error|exit status" | cut -c1-300
echo "exit=${PIPESTATUS[0]}"
libdir=$(/opt/venv/bin/python -c "import sysconfig;print(sysconfig.get_config_var('LIBDIR'))")
echo "--- control: same, with LD_LIBRARY_PATH=$libdir"
VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH LD_LIBRARY_PATH=$libdir cargo test 2>&1 | grep -E "Running|running|test result|error|exit status" | cut -c1-300
echo "exit=${PIPESTATUS[0]}"
