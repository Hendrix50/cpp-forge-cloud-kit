#!/bin/sh
# Builds Clang and lld for WebAssembly as STATIC aarch64 programs, inside an Alpine (musl) container.
# A static program needs nothing from the phone's C library, so the same files run on Android arm64.
# Runs inside:  docker run --rm -v "$PWD:/repo" -v "$PWD/out:/out" -v "$PWD/.ccache:/ccache" alpine:3.20 sh /repo/tools/toolchain/build_llvm.sh
# Result in /out: bin/clang, bin/lld, lib/clang/19/include, LICENSE.TXT
set -eux
LLVM_VERSION="${LLVM_VERSION:-19.1.5}"
JOBS="${JOBS:-$(nproc)}"
apk add --no-cache build-base cmake samurai python3 linux-headers curl xz binutils ccache
mkdir -p /work && cd /work
if [ ! -d src ]; then
  curl -fL -o llvm.tar.xz "https://github.com/llvm/llvm-project/releases/download/llvmorg-${LLVM_VERSION}/llvm-project-${LLVM_VERSION}.src.tar.xz"
  mkdir src && tar -xf llvm.tar.xz -C src --strip-components=1
  rm llvm.tar.xz
fi
export CCACHE_DIR=/ccache
export CCACHE_MAXSIZE=3G
cmake -S src/llvm -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=MinSizeRel \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
  -DLLVM_ENABLE_PROJECTS="clang;lld" \
  -DLLVM_TARGETS_TO_BUILD="WebAssembly" \
  -DLLVM_ENABLE_ASSERTIONS=OFF \
  -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF -DLLVM_INCLUDE_DOCS=OFF \
  -DCLANG_INCLUDE_TESTS=OFF -DCLANG_INCLUDE_DOCS=OFF \
  -DLLVM_ENABLE_ZLIB=OFF -DLLVM_ENABLE_ZSTD=OFF -DLLVM_ENABLE_LIBXML2=OFF -DLLVM_ENABLE_TERMINFO=OFF -DLLVM_ENABLE_LIBEDIT=OFF \
  -DLLVM_ENABLE_PLUGINS=OFF -DCLANG_PLUGIN_SUPPORT=OFF \
  -DCLANG_ENABLE_ARCMT=OFF -DCLANG_ENABLE_STATIC_ANALYZER=OFF -DCLANG_ENABLE_OBJC_REWRITER=OFF \
  -DLLVM_BUILD_LLVM_DYLIB=OFF -DLLVM_LINK_LLVM_DYLIB=OFF -DCLANG_LINK_CLANG_DYLIB=OFF \
  -DLLVM_PARALLEL_LINK_JOBS=1 \
  -DCMAKE_EXE_LINKER_FLAGS="-static" \
  -DLLVM_DEFAULT_TARGET_TRIPLE=wasm32-unknown-wasip1
ninja -C build -j"$JOBS" clang lld clang-resource-headers
ccache -s || true
mkdir -p /out/bin /out/lib/clang
cp build/bin/clang-19 /out/bin/clang
cp build/bin/lld /out/bin/lld
cp -r build/lib/clang/19 /out/lib/clang/
strip --strip-unneeded /out/bin/clang /out/bin/lld
cp src/llvm/LICENSE.TXT /out/LICENSE.TXT
ls -la /out/bin
file /out/bin/clang || true
