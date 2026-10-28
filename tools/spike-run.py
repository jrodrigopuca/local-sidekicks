"""Run one opencode agent N times on a fixture and tabulate what came back.

    python3 -I tools/spike-run.py --cwd <fixture> --agent probe --model ollama/qwen3.5:2b-16k \
        --prompt "Where is formatPrice used in this repo?" --n 3 --out <dir> \
        --starts-with "USES OF" --must-contain "TOTAL:"

Per run it records seconds, tool calls, the reply, and whether the reply
passes the format checks; prints one row per run and a summary. Raw jsonl
and stderr go to --out (never inside the fixture: the model's grep would find
them). Runs opencode with --standalone and a hard KILL timeout — both learned
in docs/spikes/2026-10-28-tool-calls-2b.md.
"""
import argparse
import json
import os
import subprocess
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument("--cwd", required=True)
ap.add_argument("--agent", required=True)
ap.add_argument("--model", required=True)
ap.add_argument("--prompt", required=True)
ap.add_argument("--n", type=int, default=3)
ap.add_argument("--out", required=True)
ap.add_argument("--timeout", type=int, default=300)
ap.add_argument("--starts-with", default="")
ap.add_argument("--must-contain", action="append", default=[])
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
# opencode locates the project (and its .opencode/agents) through $PWD, not the
# real cwd: a subprocess that only sets cwd gets "Agent not found". Measured.
cwd = os.path.abspath(args.cwd)
env = dict(os.environ, PWD=cwd)

rows = []
for i in range(1, args.n + 1):
    tag = "%s-%d" % (args.agent, i)
    jsonl = os.path.join(args.out, tag + ".jsonl")
    err = os.path.join(args.out, tag + ".err")
    # The cap is enforced here, on the whole process group: one 1490 s run went
    # past a `timeout -s KILL 300` wrapper for reasons not yet understood.
    cmd = ["opencode", "run", "--standalone",
           "--agent", args.agent, "--model", args.model, "--format", "json", args.prompt]
    t0 = time.time()
    with open(jsonl, "w") as fo, open(err, "w") as fe:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=fo, stderr=fe, start_new_session=True)
        try:
            rc = proc.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, 9)
            rc = -9
    secs = round(time.time() - t0)
    tools, text, errors = [], "", []
    boot = None  # seconds from launch to opencode's first event: a slow boot looks like a hung model otherwise
    for line in open(jsonl):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if boot is None and isinstance(e.get("timestamp"), (int, float)):
            boot = round(e["timestamp"] / 1000 - t0)
        if e.get("type") == "error":
            errors.append(str(e.get("error", {}).get("message", e.get("error"))))
            continue
        p = e.get("part", e)
        if p.get("type") == "tool":
            tools.append(p.get("tool"))
        elif p.get("type") == "text":
            text += p.get("text", "")
    text = text.strip()
    ok = bool(text)
    if args.starts_with and not text.startswith(args.starts_with):
        ok = False
    for s in args.must_contain:
        if s not in text:
            ok = False
    rows.append({"run": tag, "rc": rc, "secs": secs, "boot_secs": boot, "tools": tools, "format_ok": ok,
                 "errors": errors, "text": text})
    with open(os.path.join(args.out, tag + ".txt"), "w") as f:
        f.write(text)
    print("%-14s rc=%-3d %4ds boot=%-4s tools=%-22s format=%s  | %s" % (
        tag, rc, secs, ("%ds" % boot) if boot is not None else "?", ",".join(tools) or "-", "OK " if ok else "no",
        (("ERROR " + "; ".join(errors)) if errors else text[:70]).replace("\n", " ")))
    sys.stdout.flush()

n_ok = sum(1 for r in rows if r["format_ok"])
print("== %s: format %d/%d, mean %ds" % (args.agent, n_ok, len(rows), sum(r["secs"] for r in rows) // max(len(rows), 1)))
with open(os.path.join(args.out, args.agent + "-summary.json"), "w") as f:
    json.dump(rows, f, indent=1, ensure_ascii=False)
