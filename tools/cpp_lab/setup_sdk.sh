#!/bin/bash
# Downloads wasi-sdk (real Clang 19 that targets WebAssembly) and the Python WebAssembly runtime into ./.sdk
# Linux x86_64 only (for development and CI). Phones get their own build of the same toolchain (see docs/CPP_FORGE_ROADMAP.md).
set -e
cd "$(dirname "$0")"
mkdir -p .sdk && cd .sdk
if [ ! -d wasi-sdk-25.0-x86_64-linux ]; then
  curl -L -o sdk.tgz https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-25/wasi-sdk-25.0-x86_64-linux.tar.gz
  tar xzf sdk.tgz && rm sdk.tgz
fi
pip install wasmtime --break-system-packages 2>/dev/null || pip install wasmtime
echo "ready: $(pwd)/wasi-sdk-25.0-x86_64-linux"
