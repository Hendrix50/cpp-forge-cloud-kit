#!/usr/bin/env python3
"""Content CI for C++ Forge: nothing ships unless real Clang agrees with it.

  python tools/cpp_lab/check_content.py

Checks, in the real compiler and sandbox:
  1. every challenge: the reference solution passes all test cases and the broken starter fails
  2. every lesson example (godot_project/data/cpp_forge/lesson_examples.json): it compiles or fails exactly as the lesson says
     (including the wording of Clang's messages the lesson quotes), prints what the lesson shows, and ends the way it claims
Exit code 0 only when everything agrees. Run it before every release and in CI.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lab  # noqa: E402

DATA = os.path.normpath(os.path.join(HERE, "..", "..", "godot_project", "data", "cpp_forge"))


def check_example(e):
    r = lab.compile_and_run({"files": e["files"], "profile": e["profile"], "stdin": e.get("stdin", ""), "limits": e.get("limits", {})})
    want = e["expect"]
    problems = []
    if bool(want["compiles"]) != r["ok"]:
        problems.append("compiles=%s but the lesson says %s\n%s" % (r["ok"], want["compiles"], r["diagnostics"][:400]))
        return problems, r
    for needle in want.get("diagnostic_contains", []):
        if needle not in r["diagnostics"]:
            problems.append("Clang's message does not contain %r\n%s" % (needle, r["diagnostics"][:400]))
    if r["ok"]:
        run = r["run"]
        if "stdout" in want and run["stdout"] != want["stdout"]:
            problems.append("prints %r, the lesson says %r" % (run["stdout"], want["stdout"]))
        if "exit_code" in want and run["exit_code"] != want["exit_code"]:
            problems.append("exit code %s, the lesson says %s" % (run["exit_code"], want["exit_code"]))
        if "ended" in want and run["ended"] != want["ended"]:
            problems.append("ended %r, the lesson says %r" % (run["ended"], want["ended"]))
    return problems, r


def main():
    info = lab.info()
    if not info["ok"]:
        sys.exit(info["message"])
    print("compiler: Clang %s (%s), runner: %s\n" % (info["clang"], info["backend"], info.get("runner", "")))
    bad = 0
    print("-- challenges")
    bad += lab.verify(DATA)
    print("\n-- lesson examples")
    with open(os.path.join(DATA, "lesson_examples.json"), encoding="utf-8") as f:
        examples = json.load(f)["examples"]
    for e in examples:
        problems, r = check_example(e)
        print("%-4s %-28s %-26s %.2fs" % ("ok" if not problems else "FAIL", e["id"], e["module"], r["compile_seconds"]))
        for p in problems:
            print("       " + p.replace("\n", "\n       "))
        bad += bool(problems)
    print("\neverything agrees with the compiler" if not bad else "\n%d problem(s)" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
