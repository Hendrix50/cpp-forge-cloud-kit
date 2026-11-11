#!/usr/bin/env bash
# Proves a finished toolchain folder works:  bash tools/toolchain/test_toolchain.sh <toolchain folder>
# Runs every lesson example and challenge through it, twice: once with the wasmtime library, once with the wasmtime
# COMMAND LINE (what the phone does). Then prints cold and warm build times for Hello World.
set -euo pipefail
TC="$(cd "${1:?toolchain folder}" && pwd)"
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
export WASI_SDK="$TC"
export FORGE_PCH="$(mktemp -d)"
python3 -m pip install --quiet wasmtime || python3 -m pip install --quiet --break-system-packages wasmtime
echo "== clang"
"$TC/bin/clang" --version | head -1
echo "== content checks, wasmtime library"
python3 "$HERE/tools/cpp_lab/check_content.py" | tail -4
echo "== content checks, wasmtime command line (the phone's path)"
FORGE_WASMTIME="$TC/wasmtime-host" python3 "$HERE/tools/cpp_lab/check_content.py" | tail -4
echo "== Hello World build time (cold, then warm)"
python3 - <<PY
import sys; sys.path.insert(0, "$HERE/tools/cpp_lab")
import lab
src = '#include <iostream>\n#include <numeric>\nint main() { std::cout << "Hello, World!\\\\n"; }\n'
for label in ("cold (builds the header)", "warm"):
    r = lab.compile_files({"main.cpp": src}, {"compiler_standard": "c++20", "compile_flags": ["-Wall"]})
    print("%-26s ok=%s %.2fs" % (label, r["ok"], r["seconds"]))
PY
echo "== sizes"
du -sh "$TC" "$TC/bin" "$TC/share/wasi-sysroot" "$TC/android"
