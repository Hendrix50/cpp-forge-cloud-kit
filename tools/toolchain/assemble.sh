#!/usr/bin/env bash
# Puts the phone toolchain together:  bash tools/toolchain/assemble.sh <folder with the built bin/ and lib/> [output folder]
#   clang + lld (built by build_llvm.sh)
#   + the C++ library, C library and compiler runtime for WebAssembly (platform-independent files from the official wasi-sdk)
#   + the Android build of the sandbox runner (wasmtime)
# The result has the same layout as wasi-sdk, so tools/cpp_lab/lab.py can use it directly (WASI_SDK=<output folder>).
set -euo pipefail
BUILT="${1:?folder with the built bin/ lib/}"
TC="${2:-forge-toolchain}"
SDK_VERSION="${SDK_VERSION:-25}"
WASMTIME_VERSION="${WASMTIME_VERSION:-50.0.1}"
WORK="$(mktemp -d)"
rm -rf "$TC"
mkdir -p "$TC/bin" "$TC/lib/clang/19/lib/wasi" "$TC/share/wasi-sysroot/include" "$TC/share/wasi-sysroot/lib/wasm32-wasip1" "$TC/android" "$TC/licenses"

# 1. the compiler and linker
cp -a "$BUILT/bin/clang" "$TC/bin/clang"
cp -a "$BUILT/bin/clang" "$TC/bin/clang++"
cp -a "$BUILT/bin/lld" "$TC/bin/lld"
cp -a "$BUILT/lib/clang/19/include" "$TC/lib/clang/19/include"
[ -f "$BUILT/LICENSE.TXT" ] && cp "$BUILT/LICENSE.TXT" "$TC/licenses/LLVM-LICENSE.TXT"

# 2. WebAssembly C and C++ libraries (they are .wasm code: the same on every computer)
SDK_ARCHIVE="${SDK_ARCHIVE:-$WORK/sdk.tar.gz}"
if [ ! -f "$SDK_ARCHIVE" ]; then
  curl -fL -o "$SDK_ARCHIVE" "https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-${SDK_VERSION}/wasi-sdk-${SDK_VERSION}.0-x86_64-linux.tar.gz"
fi
mkdir -p "$WORK/sdk"
tar -xzf "$SDK_ARCHIVE" -C "$WORK/sdk" --strip-components=1
SYS="$WORK/sdk/share/wasi-sysroot"
cp "$WORK/sdk/lib/clang/19/lib/wasi/libclang_rt.builtins-wasm32.a" "$TC/lib/clang/19/lib/wasi/"
[ -d "$SYS/include/c++" ] && cp -r "$SYS/include/c++" "$TC/share/wasi-sysroot/include/"
cp -r "$SYS/include/wasm32-wasip1" "$TC/share/wasi-sysroot/include/"
for f in "$SYS"/lib/wasm32-wasip1/*.a "$SYS"/lib/wasm32-wasip1/*.o; do
  case "$(basename "$f")" in *experimental*) ;; *) cp "$f" "$TC/share/wasi-sysroot/lib/wasm32-wasip1/" ;; esac
done

# 3. the sandbox runner for Android (official build) and the one for this computer (used by the tests)
BASE="https://github.com/bytecodealliance/wasmtime/releases/download/v${WASMTIME_VERSION}"
ANDROID_ARCHIVE="${WASMTIME_ANDROID_ARCHIVE:-$WORK/wt-android.tar.xz}"
[ -f "$ANDROID_ARCHIVE" ] || curl -fL -o "$ANDROID_ARCHIVE" "$BASE/wasmtime-v${WASMTIME_VERSION}-aarch64-android.tar.xz"
mkdir -p "$WORK/wt-android" && tar -xJf "$ANDROID_ARCHIVE" -C "$WORK/wt-android" --strip-components=1
cp "$WORK/wt-android/wasmtime" "$TC/android/wasmtime"
HOST_ARCH="$(uname -m)"; [ "$HOST_ARCH" = "x86_64" ] || HOST_ARCH="aarch64"
HOST_ARCHIVE="${WASMTIME_HOST_ARCHIVE:-$WORK/wt-host.tar.xz}"
[ -f "$HOST_ARCHIVE" ] || curl -fL -o "$HOST_ARCHIVE" "$BASE/wasmtime-v${WASMTIME_VERSION}-${HOST_ARCH}-linux.tar.xz"
mkdir -p "$WORK/wt-host" && tar -xJf "$HOST_ARCHIVE" -C "$WORK/wt-host" --strip-components=1
cp "$WORK/wt-host/wasmtime" "$TC/wasmtime-host"
chmod +x "$TC/wasmtime-host"

# 4. licences and version
for pair in "WebAssembly/wasi-libc/main/LICENSE:wasi-libc-LICENSE" "bytecodealliance/wasmtime/main/LICENSE:wasmtime-LICENSE"; do
  curl -fsSL "https://raw.githubusercontent.com/${pair%%:*}" -o "$TC/licenses/${pair##*:}" || echo "(could not fetch ${pair##*:})"
done
cat > "$TC/licenses/NOTICE.md" <<NOTE
This toolchain contains: LLVM/Clang/lld 19.1.5 (Apache-2.0 with LLVM exceptions), libc++ and libc++abi (Apache-2.0 with LLVM exceptions),
wasi-libc (Apache-2.0 with LLVM exceptions, MIT and BSD parts), compiler-rt builtins (Apache-2.0 with LLVM exceptions),
wasmtime ${WASMTIME_VERSION} (Apache-2.0 with LLVM exceptions). Shown in the game's credits screen.
NOTE
cat > "$TC/VERSION" <<VER
llvm 19.1.5
wasi-sdk ${SDK_VERSION} (sysroot and builtins)
wasmtime ${WASMTIME_VERSION}
built $(date -u +%Y-%m-%dT%H:%MZ)
VER
rm -rf "$WORK"
du -sh "$TC"
echo "assembled: $TC"
