"""Control runner: the smallest loop that can run a read-only sidekick on ollama.

    python3 -I runner/control.py --agent runner/examples/find-usages/agent.md \
        --cwd <fixture> --prompt "Where is formatPrice used?" --n 3 --out <dir> \
        [--model qwen3.5:2b-16k] [--expect expected.json]

It exists to measure, not to replace a host: it talks to ollama's native
/api/chat so every knob a host hides is on the table per call — `think`,
`format` (a JSON schema the sampler enforces), `temperature`, `num_ctx`.
Its prompt floor is the agent's prompt plus three tool schemas, nothing else.
See docs/spikes/2026-10-28-formato-de-salida.md for why.

Agent file: a frontmatter block then the prompt. Keys (all optional but prompt):
    description: one line
    tools: [grep, read, glob]       # subset of the three below
    temperature: 0.2
    think: false
    num_ctx: 16384
    max_steps: 6
    output: schema.json             # JSON schema, path relative to the agent file

Defenses a 2B needs, all here: malformed tool arguments go back to the model
as an error instead of crashing; tool output is truncated; an identical tool
call repeated is refused; a step cap and a per-call timeout end every run.
Stdlib only. Paths the tools touch are confined to --cwd.
"""
import argparse
import fnmatch
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MAX_TOOL_CHARS = 6000
MAX_TOOL_LINES = 80

# ---------------------------------------------------------------- tools


def inside(root, path):
    full = os.path.realpath(os.path.join(root, path or "."))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError("path outside the workspace: %s" % path)
    return full


def tool_grep(root, args):
    pattern = args.get("pattern")
    if not pattern or not isinstance(pattern, str):
        raise ValueError("grep needs a string 'pattern'")
    path = inside(root, args.get("path") or ".")
    cmd = ["rg", "-n", "--no-heading", "--color", "never", "--glob", "!.git", "--glob", "!.opencode"]
    if args.get("literal", True):
        cmd.append("-F")
    if args.get("include"):
        cmd += ["--glob", str(args["include"])]
    cmd += ["--", pattern, path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode == 1:
        return "No matches."
    if r.returncode not in (0, 1):
        raise ValueError("rg failed: " + r.stderr.strip()[:200])
    lines = [l.replace(root + os.sep, "", 1) for l in r.stdout.splitlines()]
    return "\n".join(lines)


def tool_read(root, args):
    path = args.get("path")
    if not path or not isinstance(path, str):
        raise ValueError("read needs a string 'path'")
    full = inside(root, path)
    if os.path.isdir(full):
        return "\n".join(sorted(os.listdir(full)))
    offset = int(args.get("offset") or 1)
    limit = int(args.get("limit") or MAX_TOOL_LINES)
    out = []
    with open(full, errors="replace") as f:
        for i, line in enumerate(f, 1):
            if i < offset:
                continue
            if len(out) >= limit:
                out.append("... (truncated; use offset=%d to continue)" % i)
                break
            out.append("%d: %s" % (i, line.rstrip("\n")))
    return "\n".join(out) or "(empty file)"


def tool_glob(root, args):
    pattern = args.get("pattern")
    if not pattern or not isinstance(pattern, str):
        raise ValueError("glob needs a string 'pattern'")
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", ".opencode")]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(fn, pattern):
                hits.append(rel)
    return "\n".join(sorted(hits)[:100]) or "No files match."


def _find_block(lines, old_lines):
    """Positions where old_lines occur in lines, comparing stripped lines (a 2B
    rarely copies indentation exactly)."""
    want = [l.strip() for l in old_lines]
    hits = []
    for i in range(len(lines) - len(want) + 1):
        if [l.strip() for l in lines[i:i + len(want)]] == want:
            hits.append(i)
    return hits


TEST_CASE = __import__("re").compile(r"\b(?:it|test)\s*\(\s*([\"'`])(.*?)\1")


def guard_write(root, path, before, after):
    """What the model cannot be trusted with, enforced: the agent's `writable`
    globs, and never silently dropping an existing test case."""
    rel = os.path.relpath(inside(root, path), root)
    allowed = AGENT_META.get("writable")
    if allowed and not any(fnmatch.fnmatch(rel, g) for g in allowed):
        raise ValueError("Editing %s is not allowed for this task. You may only change files matching: %s"
                         % (rel, ", ".join(allowed)))
    if fnmatch.fnmatch(rel, "*.test.*") or fnmatch.fnmatch(rel, "*.spec.*"):
        # Identity, not count: a 2B replaced the only existing test with its new
        # one and the suite stayed at "1 passed". Every test that existed when
        # the run started must survive; the model may rework the ones it added.
        baseline = BASELINE_TESTS.get(rel, set())
        after_names = set(m[1] for m in TEST_CASE.findall(after or ""))
        lost = [n for n in baseline if n not in after_names]
        if lost:
            raise ValueError("Rejected: this change removes existing test(s) %s from %s. Keep every existing "
                             "it()/test() exactly as it is and add yours next to them." % (", ".join(repr(n) for n in lost), rel))


def tool_edit(root, args):
    path, old, new = args.get("path"), args.get("old_string"), args.get("new_string")
    if not path or not isinstance(old, str) or not isinstance(new, str):
        raise ValueError("edit needs 'path', 'old_string' and 'new_string'")
    full = inside(root, path)
    if not os.path.isfile(full):
        raise ValueError("no such file: %s (use write to create one)" % path)
    text = open(full).read()
    if old and text.count(old) == 1:
        updated = text.replace(old, new, 1)
    else:
        lines = text.split("\n")
        old_lines = old.strip("\n").split("\n") if old.strip() else []
        hits = _find_block(lines, old_lines) if old_lines else []
        if len(hits) != 1:
            if not hits:
                raise ValueError("old_string not found in %s. Read the file and copy the text exactly, "
                                 "including several unique lines." % path)
            raise ValueError("old_string matches %d places in %s; include more surrounding lines." % (len(hits), path))
        i = hits[0]
        lines[i:i + len(old_lines)] = new.strip("\n").split("\n")
        updated = "\n".join(lines)
    guard_write(root, path, text, updated)
    with open(full, "w") as f:
        f.write(updated)
    return "Edited %s (%+d chars)." % (path, len(updated) - len(text))


def tool_write(root, args):
    path, content = args.get("path"), args.get("content")
    if not path or not isinstance(content, str):
        raise ValueError("write needs 'path' and 'content'")
    full = inside(root, path)
    before = open(full).read() if os.path.isfile(full) else ""
    guard_write(root, path, before, content)
    os.makedirs(os.path.dirname(full) or full, exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    return "Wrote %s (%d lines)." % (path, content.count("\n") + 1)


AGENT_META = {}  # set per run; tools that need agent settings read it here
BASELINE_TESTS = {}  # rel path -> test names present when the run started


def snapshot_tests(root):
    BASELINE_TESTS.clear()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", ".opencode")]
        for fn in filenames:
            if fnmatch.fnmatch(fn, "*.test.*") or fnmatch.fnmatch(fn, "*.spec.*"):
                full = os.path.join(dirpath, fn)
                try:
                    names = set(m[1] for m in TEST_CASE.findall(open(full, errors="replace").read()))
                except OSError:
                    continue
                BASELINE_TESTS[os.path.relpath(full, root)] = names


def tool_run_tests(root, args):
    cmd = AGENT_META.get("test_command")
    if not cmd:
        raise ValueError("this agent has no test_command configured")
    try:
        r = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return "Tests timed out after 180 s."
    out = (r.stdout + r.stderr).strip().splitlines()
    tail = "\n".join(out[-40:])
    return "exit code %d\n%s" % (r.returncode, tail)


TOOLS = {
    "edit": (tool_edit, "Replace one block of text in a file. old_string must match the file's text (copy it from read); "
                        "it must occur once.",
             {"type": "object", "properties": {
                 "path": {"type": "string"},
                 "old_string": {"type": "string", "description": "Exact text to replace, several lines for uniqueness."},
                 "new_string": {"type": "string", "description": "The replacement text."},
             }, "required": ["path", "old_string", "new_string"]}),
    "write": (tool_write, "Write a whole file (creates or overwrites it). Prefer edit for small changes.",
              {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
               "required": ["path", "content"]}),
    "run_tests": (tool_run_tests, "Run the project's test suite and return its result.",
                  {"type": "object", "properties": {}}),
    "grep": (tool_grep, "Search file contents. Returns one line per match as path:line: text. Paths are relative to the repository root.",
             {"type": "object", "properties": {
                 "pattern": {"type": "string", "description": "Text to search for (literal by default)."},
                 "path": {"type": "string", "description": "File or directory to search; default is the whole repository."},
                 "literal": {"type": "boolean", "description": "true (default) for literal text, false for a regular expression."},
             }, "required": ["pattern"]}),
    "read": (tool_read, "Read a file with line numbers, or list a directory.",
             {"type": "object", "properties": {
                 "path": {"type": "string"},
                 "offset": {"type": "integer", "description": "First line to read (1-based)."},
                 "limit": {"type": "integer", "description": "How many lines."},
             }, "required": ["path"]}),
    "glob": (tool_glob, "Find files by name pattern, e.g. **/*.tsx or *.test.ts.",
             {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}),
}


def tool_schemas(names):
    return [{"type": "function", "function": {"name": n, "description": TOOLS[n][1], "parameters": TOOLS[n][2]}}
            for n in names]

# ---------------------------------------------------------------- agent file


def parse_agent(path):
    text = open(path).read()
    meta, body = {}, text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            for line in text[3:end].strip().splitlines():
                if ":" not in line or line.lstrip().startswith("#"):
                    continue
                k, v = line.split(":", 1)
                v = v.strip()
                if v.startswith("[") and v.endswith("]"):
                    v = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
                elif v.lower() in ("true", "false"):
                    v = v.lower() == "true"
                else:
                    try:
                        v = float(v) if "." in v else int(v)
                    except ValueError:
                        v = v.strip("'\"")
                meta[k.strip()] = v
            body = text[end + 4:]
    schema = None
    if meta.get("output"):
        schema = json.load(open(os.path.join(os.path.dirname(os.path.abspath(path)), meta["output"])))
    return meta, body.strip(), schema

# ---------------------------------------------------------------- ollama


def chat(model, messages, tools, meta, fmt=None, timeout=300):
    body = {
        "model": model, "messages": messages, "stream": False,
        "think": bool(meta.get("think", False)),
        "options": {"temperature": float(meta.get("temperature", 0.2)),
                    "num_ctx": int(meta.get("num_ctx", 16384)),
                    "num_predict": int(meta.get("num_predict", 2048))},
    }
    if tools:
        body["tools"] = tools
    if fmt:
        body["format"] = fmt
    req = urllib.request.Request(OLLAMA + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

# ---------------------------------------------------------------- schema check (tiny)


def conforms(value, schema):
    t = schema.get("type")
    if t == "object":
        if not isinstance(value, dict):
            return False
        for k in schema.get("required", []):
            if k not in value:
                return False
        return all(conforms(value[k], s) for k, s in schema.get("properties", {}).items() if k in value)
    if t == "array":
        return isinstance(value, list) and all(conforms(v, schema.get("items", {})) for v in value)
    if t == "string":
        return isinstance(value, str) and (value in schema["enum"] if "enum" in schema else True)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float))
    if t == "boolean":
        return isinstance(value, bool)
    return True

# ---------------------------------------------------------------- one run


def run_once(model, meta, prompt, schema, root, user_prompt, timeout):
    AGENT_META.clear()
    AGENT_META.update(meta)
    snapshot_tests(root)
    names = [n for n in (meta.get("tools") or ["grep", "read", "glob"]) if n in TOOLS]
    tools = tool_schemas(names)
    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": user_prompt}]
    log = {"steps": [], "tool_calls": [], "prompt_tokens": 0, "eval_tokens": 0, "errors": []}
    seen = set()
    t0 = time.time()
    final_text = ""
    for step in range(1, int(meta.get("max_steps", 6)) + 1):
        try:
            r = chat(model, messages, tools, meta, timeout=timeout)
        except (urllib.error.URLError, OSError) as e:
            log["errors"].append("step %d: %s" % (step, e))
            break
        log["prompt_tokens"] += r.get("prompt_eval_count", 0)
        log["eval_tokens"] += r.get("eval_count", 0)
        msg = r["message"]
        calls = msg.get("tool_calls") or []
        log["steps"].append({"step": step, "tool_calls": len(calls), "prompt_tokens": r.get("prompt_eval_count", 0),
                             "eval_tokens": r.get("eval_count", 0), "secs": round(r.get("total_duration", 0) / 1e9, 1)})
        messages.append(msg)
        if not calls:
            final_text = msg.get("content", "")
            break
        for c in calls:
            fn = c.get("function", {})
            name = fn.get("name")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {"_raw": args}
            key = name + json.dumps(args, sort_keys=True)
            if name not in TOOLS or name not in names:
                result = "Error: unknown tool %r. Available: %s" % (name, ", ".join(names))
            elif key in seen:
                # A repeat is only pointless if nothing changed since; after an
                # edit, re-running the tests or re-reading a file is the right move.
                result = ("You already called %s with these arguments and nothing has changed since; its result is above. "
                          "If the task is done, answer now without calling tools." % name)
            else:
                try:
                    result = TOOLS[name][0](root, args)
                except (ValueError, OSError, subprocess.TimeoutExpired) as e:
                    result = "Error: %s" % e
            seen.add(key)
            if name in ("edit", "write") and not result.startswith("Error"):
                seen = {k for k in seen if k.startswith(("edit", "write"))}  # the world changed: reads and test runs are fresh again
            if len(result) > MAX_TOOL_CHARS:
                result = result[:MAX_TOOL_CHARS] + "\n... (truncated)"
            log["tool_calls"].append({"name": name, "args": args, "chars": len(result), "result": result[:1500]})
            messages.append({"role": "tool", "content": result, "tool_name": name})
    else:
        log["errors"].append("max_steps reached")
    output, format_ok = None, None
    if schema:
        # The tool results go back in, next to the request: with them two
        # messages up, behind the model's own prose, a 2B drifted into
        # pattern-continuation (58 invented entries, lines 6, 8, 10… 112).
        evidence = "\n\n".join("Result of %s:\n%s" % (m["tool_name"], m["content"])
                               for m in messages if m.get("role") == "tool")
        messages.append({"role": "user", "content":
                         "Now give the final answer as JSON matching the schema. Use ONLY these tool results; "
                         "every entry must correspond to one of these lines, and there are no others.\n\n" + evidence})
        try:
            r = chat(model, messages, None, meta, fmt=schema, timeout=timeout)
            log["prompt_tokens"] += r.get("prompt_eval_count", 0)
            log["eval_tokens"] += r.get("eval_count", 0)
            final_text = r["message"].get("content", "")
            output = json.loads(final_text)
            format_ok = conforms(output, schema)
        except (urllib.error.URLError, OSError, ValueError) as e:
            log["errors"].append("final: %s" % e)
            format_ok = False
    # Entries the tools never returned: the failure mode to count, not to hide.
    invented = None
    if isinstance(output, dict) and isinstance(output.get("uses"), list):
        returned = set()
        for m in messages:
            if m.get("role") == "tool":
                for line in m["content"].splitlines():
                    parts = line.split(":", 2)
                    if len(parts) >= 2 and parts[1].isdigit():
                        returned.add("%s:%s" % (parts[0], parts[1]))
        def key(u):  # tolerate "path:line" written into `path`; the scorer counts that separately
            p, ln = str(u.get("path")), str(u.get("line"))
            if p.endswith(":" + ln):
                p = p[: -len(":" + ln)]
            return "%s:%s" % (p, ln)
        invented = sorted(key(u) for u in output["uses"] if isinstance(u, dict) and key(u) not in returned)
    log.update({"secs": round(time.time() - t0), "text": final_text, "output": output,
                "format_ok": format_ok, "invented": invented})
    return log

# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--model", default="qwen3.5:2b-16k")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=300, help="seconds per model call")
    ap.add_argument("--expect", help="JSON list of 'path:line' that a correct answer's uses[] must contain")
    ap.add_argument("--reset", action="store_true", help="git checkout -- . && git clean -fd in --cwd before each run")
    ap.add_argument("--verify", help="shell command run in --cwd AFTER each run; its exit code and a vitest-style "
                                     "'N passed / N failed' count are recorded")
    ap.add_argument("--expect-tests", type=int, help="with --verify: minimum tests passed for the run to count as OK "
                                                     "(baseline + the ones the task adds), so green never hides a regression")
    ap.add_argument("--expect-diff", help="regex the git diff must match for the run to count as OK — green can be "
                                          "gamed (a 2B wrote a test that never called the function under test)")
    a = ap.parse_args()
    meta, prompt, schema = parse_agent(a.agent)
    root = os.path.realpath(a.cwd)
    os.makedirs(a.out, exist_ok=True)
    expect = set(json.load(open(a.expect))) if a.expect else None
    tag = os.path.basename(os.path.dirname(os.path.abspath(a.agent))) or "agent"
    rows = []
    for i in range(1, a.n + 1):
        if a.reset:
            subprocess.run(["git", "-C", root, "checkout", "--", "."], check=True)
            subprocess.run(["git", "-C", root, "clean", "-fdq"], check=True)
        log = run_once(a.model, meta, prompt, schema, root, a.prompt, a.timeout)
        score = ""
        if a.reset or a.verify:
            diff = subprocess.run(["git", "-C", root, "status", "--short"], capture_output=True, text=True).stdout
            log["changed_files"] = [l[3:] for l in diff.splitlines() if l.strip()]
            log["diff"] = subprocess.run(["git", "-C", root, "--no-pager", "diff"], capture_output=True, text=True).stdout[:20000]
            score += " changed=%s" % (",".join(log["changed_files"]) or "-")
        if a.verify:
            import re
            try:
                v = subprocess.run(a.verify, shell=True, cwd=root, capture_output=True, text=True, timeout=180)
                out = v.stdout + v.stderr
                passed = re.search(r"Tests\s+(\d+) passed", out)
                failed = re.search(r"Tests\s+(?:\d+ failed \| )?(\d+) failed|(\d+) failed", out)
                log["verify"] = {"rc": v.returncode,
                                 "passed": int(passed.group(1)) if passed else None,
                                 "failed": int(next(g for g in failed.groups() if g)) if failed else 0,
                                 "tail": "\n".join(out.strip().splitlines()[-15:])}
            except subprocess.TimeoutExpired:
                log["verify"] = {"rc": None, "passed": None, "failed": None, "tail": "verify timed out"}
            v = log["verify"]
            if a.expect_tests is not None:
                v["ok"] = v["rc"] == 0 and (v["passed"] or 0) >= a.expect_tests
            if a.expect_diff:
                v["diff_ok"] = bool(re.search(a.expect_diff, log.get("diff", "")))
                v["ok"] = v.get("ok", v["rc"] == 0) and v["diff_ok"]
                score += " diff=%s" % ("OK" if v["diff_ok"] else "NO")
            score += " verify=rc%s passed=%s failed=%s%s" % (
                v["rc"], v["passed"], v["failed"], (" -> %s" % ("OK" if v["ok"] else "NO")) if "ok" in v else "")
        if expect is not None and isinstance(log.get("output"), dict):
            # A 2B sometimes writes "path:line" into `path`; score the content,
            # and count the deviation separately rather than as ten misses.
            got, sloppy = set(), 0
            for u in log["output"].get("uses", []):
                if not isinstance(u, dict):
                    continue
                p = str(u.get("path"))
                if p.endswith(":%s" % u.get("line")):
                    p, sloppy = p[: -len(":%s" % u.get("line"))], sloppy + 1
                got.add("%s:%s" % (p, u.get("line")))
            log["path_with_line"] = sloppy
            hit = len(got & expect)
            score = " recall=%d/%d extra=%d invented=%s%s" % (
                hit, len(expect), len(got - expect),
                len(log["invented"]) if log.get("invented") is not None else "?",
                (" path:line=%d" % sloppy) if sloppy else "")
            log["recall"] = [hit, len(expect)]
            log["extra"] = sorted(got - expect)
        rows.append(log)
        with open(os.path.join(a.out, "%s-%d.json" % (tag, i)), "w") as f:
            json.dump(log, f, indent=1, ensure_ascii=False)
        print("%s-%d  %4ds  steps=%d  tools=%-18s  tokens in/out=%d/%d  format=%s%s%s" % (
            tag, i, log["secs"], len(log["steps"]), ",".join(c["name"] for c in log["tool_calls"]) or "-",
            log["prompt_tokens"], log["eval_tokens"],
            {True: "OK", False: "no", None: "n/a"}[log["format_ok"]], score,
            ("  ERR " + "; ".join(log["errors"])) if log["errors"] else ""))
        sys.stdout.flush()
    ok = sum(1 for r in rows if r["format_ok"])
    print("== %s on %s: format %d/%d, mean %ds, mean out tokens %d" % (
        tag, a.model, ok, len(rows), sum(r["secs"] for r in rows) // len(rows), sum(r["eval_tokens"] for r in rows) // len(rows)))


if __name__ == "__main__":
    main()
