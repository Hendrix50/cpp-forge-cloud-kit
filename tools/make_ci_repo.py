#!/usr/bin/env python3
"""Creates a small folder you can push to a NEW PUBLIC GitHub repository to build the phone toolchain for free.

  python tools/toolchain/make_ci_repo.py            -> creates ..\\glyphforge-toolchain-ci next to your project

Why a separate public repository: GitHub gives public repositories free ARM64 build machines. Private repositories do not
get them for free. This folder holds only open build scripts and the lesson data the tests need, none of your game code.
"""
import os, shutil, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.normpath(os.path.join(ROOT, "..", "glyphforge-toolchain-ci"))
PARTS = [(".github", ".github"), ("tools/toolchain", "tools/toolchain"), ("tools/cpp_lab", "tools/cpp_lab"),
         ("godot_project/data/cpp_forge", "godot_project/data/cpp_forge")]
SKIP = {"__pycache__", ".sdk", ".cache"}


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    for src, dst in PARTS:
        s, d = os.path.join(ROOT, src), os.path.join(OUT, dst)
        if not os.path.exists(s):
            sys.exit("missing: " + src)
        shutil.copytree(s, d, ignore=lambda _dir, names: [n for n in names if n in SKIP])
    with open(os.path.join(OUT, "README.md"), "w") as f:
        f.write("# Glyphforge toolchain build\n\nBuilds Clang for WebAssembly as a static ARM64 program, plus the sysroot and tests.\n"
                "Run: Actions > Build phone toolchain > Run workflow. Download the artifact when it finishes.\n")
    print("created", OUT)
    print("Next, in that folder:  git init, git add ., git commit, create a PUBLIC repository on GitHub and push (see tools/toolchain/README.md).")


if __name__ == "__main__":
    main()
