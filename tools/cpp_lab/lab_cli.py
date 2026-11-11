#!/usr/bin/env python3
"""JSON command line for the game (on a computer, while developing) and for CI.

  python lab_cli.py --request request.json --response response.json

request  {"action": "info"}
         {"action": "compile_run", "files": {"main.cpp": "..."}, "profile": {"compiler_standard": "c++20", "compile_flags": ["-Wall"]},
          "stdin": "", "limits": {"memory_mb": 64, "fuel": 300000000, "stdout_bytes": 4096}}
response the dictionaries documented in docs/COMPILER_CONTRACT.md
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab  # noqa: E402


def main():
    args = sys.argv[1:]
    req_path = args[args.index("--request") + 1]
    resp_path = args[args.index("--response") + 1]
    with open(req_path, encoding="utf-8") as f:
        req = json.load(f)
    try:
        action = req.get("action")
        if action == "info":
            resp = lab.info()
        elif action == "compile_run":
            resp = lab.compile_and_run(req)
        else:
            resp = {"ok": False, "message": "unknown action " + str(action)}
    except Exception as e:  # the game must always get an answer
        resp = {"ok": False, "message": "lab error: " + str(e)}
    with open(resp_path, "w", encoding="utf-8") as f:
        json.dump(resp, f)


if __name__ == "__main__":
    main()
