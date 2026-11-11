#!/usr/bin/env python3
"""C++ Forge compiler lab: compile player C++ with real Clang to WebAssembly, run it sandboxed, check it against tests.

  python tools/cpp_lab/setup_sdk.py                              # once
  python tools/cpp_lab/lab.py compile path/to/main.cpp           # Clang's real messages, then runs the program
  python tools/cpp_lab/lab.py verify  <folder with challenges.json, reference_solutions.json, test_bundles.json>

The functions here are the compiler contract the phone's compiler service must also implement (docs/COMPILER_CONTRACT.md):
  info()                          -> what compiler is available
  compile_files(files, profile)   -> {ok, diagnostics, wasm, seconds}
  run_wasm(wasm, stdin, limits)   -> {stdout, stderr, exit_code, ended, ms}
  compile_and_run(request)        -> both in one call (what the game uses)
"""
import glob, hashlib, json, os, re, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = ".exe" if os.name == "nt" else ""
SHIM = os.path.join(HERE, "forge_shim.cpp")


def find_sdk():
    env = os.environ.get("WASI_SDK")
    if env and os.path.isdir(env):
        return env
    found = sorted(glob.glob(os.path.join(HERE, ".sdk", "wasi-sdk-*")))
    found = [f for f in found if os.path.isdir(f)]
    return found[0] if found else ""


SDK = find_sdk()

# flags every player program is built with
STACK_BYTES = 1024 * 1024  # wasi-libc's default stack is only 64 KB, too small for a recursion lesson


def base_flags():
    return ["--target=wasm32-wasip1", "--sysroot=" + os.path.join(SDK, "share", "wasi-sysroot"), "-O0", "-g0", "-fno-exceptions"]


# what a "sanitizer" flag from a test bundle becomes here: checks that trap, no runtime library needed
SANITIZER_MAP = {"-fsanitize=address,undefined": ["-fsanitize=bounds,null,signed-integer-overflow,shift,integer-divide-by-zero", "-fsanitize-trap=all"],
                 "-fno-omit-frame-pointer": []}
HARDENING = "-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE"  # std::vector[] out of range traps


def profile_flags(profile):
    flags = ["-std=" + profile.get("compiler_standard", "c++20"), HARDENING]
    for f in profile.get("compile_flags", []):
        flags += SANITIZER_MAP.get(f, [f])
    return flags


def info():
    if not SDK:
        return {"ok": False, "backend": "desktop_lab", "message": "Toolchain not installed. Run: python tools/cpp_lab/setup_sdk.py"}
    try:
        if not os.environ.get("FORGE_WASMTIME"):
            import wasmtime  # noqa: F401
    except ImportError:
        return {"ok": False, "backend": "desktop_lab", "message": "The WebAssembly runtime is missing. Run: python tools/cpp_lab/setup_sdk.py"}
    r = subprocess.run([os.path.join(SDK, "bin", "clang++" + EXE), "--version"], capture_output=True, text=True)
    first = (r.stdout or r.stderr).splitlines()[0] if (r.stdout or r.stderr) else "clang"
    version = first.split("version ")[1].split(" ")[0] if "version " in first else first
    return {"ok": r.returncode == 0, "backend": "desktop_lab", "clang": version, "standard": "c++20", "runner": "wasmtime command line" if os.environ.get("FORGE_WASMTIME") else "wasmtime library", "message": "ready"}


def _tool(name):
    return os.path.join(SDK, "bin", name + EXE)


def _builtins():
    found = sorted(glob.glob(os.path.join(SDK, "lib", "clang", "*", "lib", "wasi", "libclang_rt.builtins-wasm32.a")))
    return found[0] if found else ""


def uses_traps(profile):
    return any(f in SANITIZER_MAP and SANITIZER_MAP[f] for f in profile.get("compile_flags", []))


INCLUDE_RE = re.compile(r"^[ \t]*#[ \t]*include[ \t]*<([^>\n]+)>", re.M)
PCH_DIR = os.environ.get("FORGE_PCH") or os.path.join(HERE, ".cache", "pch")


def pch_flags(source_text, profile, flags):
    """A precompiled header makes a build about 12 times faster (2.0 s down to 0.2 s for Hello World).
    It must hold EXACTLY the standard headers this file includes, no more: a header that quietly adds
    <iostream> to every program would hide the mistake the lesson teaches (forgetting an #include).
    So the header is built per set of includes, the first time that set is seen, and kept for the next time."""
    if re.search(r"^[ \t]*#[ \t]*(if|ifdef|ifndef)\b", source_text, re.M):
        return []  # includes inside conditions: build the ordinary way
    names = INCLUDE_RE.findall(source_text)
    if not names:
        return []
    key_text = "|".join([profile.get("compiler_standard", "c++20"), "trap" if uses_traps(profile) else "plain", ",".join(names)])
    key = hashlib.sha1(key_text.encode()).hexdigest()[:16]
    os.makedirs(PCH_DIR, exist_ok=True)
    pch = os.path.join(PCH_DIR, key + ".pch")
    if not os.path.exists(pch):
        hpp = os.path.join(PCH_DIR, key + ".hpp")
        with open(hpp, "w") as f:
            f.write("".join("#include <%s>\n" % n for n in names))
        r = subprocess.run([_tool("clang++")] + flags + ["-x", "c++-header", hpp, "-o", pch + ".tmp"], capture_output=True, text=True)
        if r.returncode != 0:
            return []  # a bad header name: let the real build show the real error
        os.replace(pch + ".tmp", pch)
    return ["-include-pch", pch]


def compile_files(files, profile):
    """files: {"main.cpp": "..."}. Builds in TWO steps, exactly as the phone does (Android only runs files named lib*.so,
    and lld decides what it is from its file name, so the phone calls it as `lld -flavor wasm` itself):
      1. clang++ -c for every .cpp      2. lld -flavor wasm links the objects with the C++ library
    Returns {"ok", "diagnostics" (Clang's and lld's own text), "wasm", "seconds"}."""
    if not SDK:
        return {"ok": False, "diagnostics": "Toolchain not installed.", "wasm": "", "seconds": 0.0}
    d = tempfile.mkdtemp(prefix="forge_")
    srcs = []
    for name, text in files.items():
        p = os.path.join(d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        if name.endswith((".cpp", ".cc", ".cxx")):
            srcs.append(p)
    srcs.append(SHIM)
    sysroot = os.path.join(SDK, "share", "wasi-sysroot")
    flags = base_flags() + profile_flags(profile)
    t = time.time()
    objs, messages = [], []
    ok = True
    for i, src in enumerate(srcs):
        obj = os.path.join(d, "obj%d.o" % i)
        with open(src, encoding="utf-8", errors="replace") as sf:
            extra = pch_flags(sf.read(), profile, flags) if src != SHIM else []
        r = subprocess.run([_tool("clang++")] + flags + extra + ["-I" + d, "-c", src, "-o", obj], capture_output=True, text=True, encoding="utf-8", errors="replace")
        messages.append(r.stderr)
        if r.returncode != 0:
            ok = False
            break
        objs.append(obj)
    out = os.path.join(d, "program.wasm")
    if ok:
        lib = os.path.join(sysroot, "lib", "wasm32-wasip1")
        link = [_tool("lld"), "-flavor", "wasm", "-m", "wasm32", "-L" + lib, os.path.join(lib, "crt1-command.o"),
                "-z", "stack-size=%d" % STACK_BYTES] + objs + ["-lc++", "-lc++abi", "-lc", _builtins(), "-o", out]
        r = subprocess.run(link, capture_output=True, text=True, encoding="utf-8", errors="replace")
        messages.append(r.stderr)
        ok = r.returncode == 0
    text = "".join(messages).replace(d + os.sep, "").replace(d + "/", "").replace(SDK, "<toolchain>")
    return {"ok": ok, "diagnostics": text, "wasm": out if ok else "", "seconds": round(time.time() - t, 2)}


def classify(exit_code, stderr_text):
    """The runner command line (wasmtime) exits with 134 when the program was stopped. The text says why.
    Returns (ended, exit_code) using the same words as docs/COMPILER_CONTRACT.md."""
    if exit_code != 134:
        return "finished", exit_code
    if "all fuel consumed" in stderr_text or "wasm trap: interrupt" in stderr_text:
        return "ran out of time", -1
    if "wasm trap" in stderr_text:
        return "stopped by a safety check", -1
    return "finished", exit_code


def run_wasm_cli(wasm, stdin_text, limits):
    """Runs the program with the wasmtime COMMAND LINE: exactly what the phone's compiler service does
    (the Android build of wasmtime has the same options). Used when FORGE_WASMTIME points at the executable."""
    exe = os.environ["FORGE_WASMTIME"]
    fuel, mem, stack = int(limits.get("fuel", 300_000_000)), int(limits.get("memory_mb", 64)) * 1024 * 1024, int(limits.get("stack_bytes", STACK_BYTES))
    wall = int(limits.get("seconds", 10))
    stdout_limit = int(limits.get("stdout_bytes", 4096))
    errfile = tempfile.NamedTemporaryFile(prefix="forge_err_", delete=False)
    t = time.time()
    # no environment, no folders, no network: the program sees only its input and output
    proc = subprocess.Popen([exe, "run", "-W", "fuel=%d,max-memory-size=%d,max-wasm-stack=%d,timeout=%ds" % (fuel, mem, stack, wall), wasm],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errfile, env={})
    try:
        proc.stdin.write(stdin_text.encode("utf-8"))
        proc.stdin.close()
    except OSError:
        pass
    out = proc.stdout.read(stdout_limit + 1)
    flooded = len(out) > stdout_limit
    if flooded:
        proc.kill()
    try:
        proc.wait(timeout=wall + 5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    errfile.close()
    with open(errfile.name, encoding="utf-8", errors="replace") as f:
        err = f.read()
    os.unlink(errfile.name)
    ended, code = classify(proc.returncode, err)
    if flooded:
        ended, code = "printed too much", -1
    return {"stdout": out[:stdout_limit].decode("utf-8", errors="replace"), "stderr": "" if ended != "finished" else err[:400], "exit_code": code, "ended": ended, "ms": round((time.time() - t) * 1000, 1)}


def run_wasm(wasm, stdin_text="", limits=None):
    limits = limits or {}
    if os.environ.get("FORGE_WASMTIME"):
        return run_wasm_cli(wasm, stdin_text, limits)
    import wasmtime
    fuel, memory_mb, stdout_limit = int(limits.get("fuel", 300_000_000)), int(limits.get("memory_mb", 64)), int(limits.get("stdout_bytes", 4096))
    cfg = wasmtime.Config()
    cfg.consume_fuel = True
    eng = wasmtime.Engine(cfg)
    mod = wasmtime.Module.from_file(eng, wasm)
    d = tempfile.mkdtemp(prefix="forge_run_")
    wc = wasmtime.WasiConfig()
    wc.argv = ["program"]
    with open(os.path.join(d, "in"), "w", encoding="utf-8", newline="\n") as f:
        f.write(stdin_text)
    wc.stdin_file, wc.stdout_file, wc.stderr_file = os.path.join(d, "in"), os.path.join(d, "out"), os.path.join(d, "err")
    st = wasmtime.Store(eng)
    st.set_wasi(wc)
    st.set_fuel(fuel)
    st.set_limits(memory_size=memory_mb * 1024 * 1024)
    lk = wasmtime.Linker(eng)
    lk.define_wasi()
    t = time.time()
    ended, code = "finished", 0
    try:
        lk.instantiate(st, mod).exports(st)["_start"](st)
    except wasmtime.ExitTrap as e:
        code = e.code
    except wasmtime.Trap as e:
        ended = "ran out of time" if "fuel" in str(e).lower() else "stopped by a safety check"
        code = -1
    def read(name):
        try:
            with open(os.path.join(d, name), encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""
    return {"stdout": read("out")[:stdout_limit], "stderr": read("err")[:400], "exit_code": code, "ended": ended, "ms": round((time.time() - t) * 1000, 1)}


def compile_and_run(request):
    """request: {"files": {...}, "profile": {"compiler_standard", "compile_flags"}, "stdin": "", "limits": {...}}"""
    c = compile_files(request.get("files", {}), request.get("profile", {}))
    out = {"ok": c["ok"], "diagnostics": c["diagnostics"], "compile_seconds": c["seconds"], "run": None}
    if c["ok"]:
        out["run"] = run_wasm(c["wasm"], request.get("stdin", ""), request.get("limits"))
    return out


def check_cases(wasm, bundle, limits):
    results = []
    for case in bundle["cases"]:
        r = run_wasm(wasm, case.get("stdin", ""), {"memory_mb": limits.get("memory_mb", 64)})
        ok = r["stdout"] == case.get("stdout_exact") and r["exit_code"] == case.get("exit_code", 0)
        results.append({"id": case["id"], "ok": ok, "stdout": r["stdout"], "ended": r["ended"]})
    return results


def verify(folder):
    ch = json.load(open(os.path.join(folder, "challenges.json"), encoding="utf-8"))["challenge_catalog"]
    refs = json.load(open(os.path.join(folder, "reference_solutions.json"), encoding="utf-8"))["reference_solutions"]
    tbs = json.load(open(os.path.join(folder, "test_bundles.json"), encoding="utf-8"))["test_bundles"]
    bad = 0
    for c in ch:
        bundle, limits = tbs[c["test_bundle_id"]], c.get("resource_limits", {})
        ref = compile_files(refs[c["reference_solution_id"]]["files"], bundle)
        line = f"{c['id']:28} reference: "
        if not ref["ok"]:
            print(line + "COMPILE FAILED\n" + ref["diagnostics"])
            bad += 1
            continue
        res = check_cases(ref["wasm"], bundle, limits)
        good = all(r["ok"] for r in res)
        line += ("PASS " if good else "FAIL ") + f"({ref['seconds']}s)"
        bad += not good
        starter = compile_files({f["path"]: f["content"] for f in c["starter_files"]}, bundle)
        if starter["ok"]:
            sres = check_cases(starter["wasm"], bundle, limits)
            fails = not all(r["ok"] for r in sres)
            line += "   starter: " + ("fails as intended (" + sres[0]["ended"] + ")" if fails else "PASSES (the challenge is too easy)")
            bad += not fails
        else:
            line += "   starter: does not compile (that is the lesson)"
        print(line)
    return bad


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "verify":
        bad = verify(sys.argv[2])
        print("\nall challenges fair" if not bad else f"\n{bad} problem(s)")
        sys.exit(1 if bad else 0)
    if len(sys.argv) >= 3 and sys.argv[1] == "compile":
        with open(sys.argv[2], encoding="utf-8") as f:
            src = f.read()
        r = compile_and_run({"files": {"main.cpp": src}, "profile": {"compiler_standard": "c++20", "compile_flags": ["-Wall", "-Wextra", "-Wpedantic"]}})
        print(r["diagnostics"] or "(no messages)")
        print(f"built in {r['compile_seconds']}s" if r["ok"] else "build failed")
        if r["run"]:
            print(r["run"])
        sys.exit(0 if r["ok"] else 1)
    print(__doc__)
