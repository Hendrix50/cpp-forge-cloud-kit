# Building the phone toolchain in the cloud (no Linux machine needed)

GitHub gives **public** repositories free ARM64 Linux build machines. This folder builds Clang and lld for WebAssembly as
static ARM64 programs there, adds the C++ library, the sandbox runner and the tests, and gives you one zip.

## Steps (Windows)
1. In your project folder: `python tools\toolchain\make_ci_repo.py`. It creates `..\glyphforge-toolchain-ci` with only open build scripts and the lesson data (none of your game code).
2. On github.com create a **new, empty, public** repository, for example `glyphforge-toolchain-ci` (no README, no licence).
3. In Command Prompt:
```
cd ..\glyphforge-toolchain-ci
git init
git add .
git commit -m "toolchain build"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/glyphforge-toolchain-ci.git
git push -u origin main
```
4. On GitHub open the **Actions** tab, choose **Build phone toolchain**, press **Run workflow**. (If Actions asks to be enabled, enable it.)
5. First run takes roughly 1.5 to 3.5 hours. Later runs reuse a cache and are much faster. You can close the browser.
6. When the run is green, open it and download the artifact **forge-toolchain-android-arm64**.
7. If a step is red, open it, copy the last 60 lines of its log and send them to me. A first run of a big build usually needs one or two fixes.

## What the workflow does
| Step | Script | Result |
|---|---|---|
| Build | `build_llvm.sh` | Static `clang` and `lld` (WebAssembly target only) built from LLVM 19.1.5 source in an Alpine (musl) container. Static programs do not depend on the phone's C library |
| Assemble | `assemble.sh` | Same folder layout as wasi-sdk: compiler, linker, headers, WebAssembly C and C++ libraries (from the official wasi-sdk), the Android build of wasmtime, licences |
| Test | `test_toolchain.sh` | Every lesson example and challenge, through the wasmtime library and through the wasmtime command line (the phone's path), plus Hello World build times |
| Pack | workflow | `forge-toolchain-android-arm64.zip` (without the test-only runner) |

## Honest status
`assemble.sh` and `test_toolchain.sh` were run here against a stand-in (the official x86 wasi-sdk compiler) and everything passed.
`build_llvm.sh` and the workflow have **not** been run: they need a machine this sandbox does not have. Expect some iteration.

## After you have the zip
Check it on your phone before it goes in the game (see `docs/ANDROID_TOOLCHAIN.md`, "Device self-test").
