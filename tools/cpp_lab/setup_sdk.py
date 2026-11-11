#!/usr/bin/env python3
"""Downloads wasi-sdk (a real Clang 19 that targets WebAssembly, with libc++) and the WebAssembly runtime into ./.sdk.
Works on Windows, Linux and macOS. Run once:   python tools/cpp_lab/setup_sdk.py
This is for development and CI. Phones get their own build of the same toolchain (docs/CPP_FORGE_ROADMAP.md, step C3).
"""
import os, platform, shutil, subprocess, sys, tarfile, urllib.request

VERSION = "25"
FULL = "25.0"
BASE = f"https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-{VERSION}/"


def archive_name():
    system, machine = platform.system(), platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x86_64"
    osname = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}.get(system)
    if not osname:
        sys.exit("unsupported system: " + system)
    return f"wasi-sdk-{FULL}-{arch}-{osname}"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    sdk_dir = os.path.join(here, ".sdk")
    os.makedirs(sdk_dir, exist_ok=True)
    name = archive_name()
    target = os.path.join(sdk_dir, name)
    if not os.path.isdir(target):
        url = BASE + name + ".tar.gz"
        print("downloading", url, "(about 110 MB)")
        tgz = os.path.join(sdk_dir, "sdk.tar.gz")
        urllib.request.urlretrieve(url, tgz)
        print("unpacking")
        with tarfile.open(tgz) as tar:
            for m in tar:
                try:
                    tar.extract(m, sdk_dir)
                except OSError:  # Windows without symlink rights: copied below
                    pass
        os.remove(tgz)
        exe = ".exe" if os.name == "nt" else ""
        bindir = os.path.join(target, "bin")
        for tool, real in (("clang++", "clang"), ("clang", "clang"), ("wasm-ld", "lld")):
            dst = os.path.join(bindir, tool + exe)
            src = os.path.join(bindir, real + exe)
            if not os.path.exists(dst) and os.path.exists(src):
                shutil.copy(src, dst)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "wasmtime"])
    print("ready:", target)


if __name__ == "__main__":
    main()
