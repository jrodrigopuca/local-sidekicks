# local-sidekicks

Small, single-task agents for [opencode](https://opencode.ai) running local
models through [ollama](https://ollama.com). Sidekicks, not heroes: each one
does ONE thing — explain a script, find where a symbol is used, review a
React component, update a Vitest test — with a few hard rules, a fixed output
shape and only the tools that task needs.

Target: models of the Qwen 3.5 8B class. Development floor: Qwen 3.5 2B. A
sidekick that holds on 2B holds on 8B; the reverse is not true.

This is the small-model counterpart of
[local-agents](https://github.com/jrodrigopuca/local-agents), and it borrows
its method from [interaction](https://github.com/jrodrigopuca/interaction):
nothing is believed about a sidekick until it is measured against the bare
model. The three decisions that shape the repo are in [`docs/adr/`](docs/adr/).

## What exists today

```
runner/control.py          the control runner: a minimal loop on ollama's native API
                           (think/format/temperature per call), read-only and write tools,
                           path allowlist, test guards, external verification per run
runner/examples/<task>/    agent.md (+ schema.json): find-usages, update-vitest-test
tools/log-proxy.py         see the exact bytes a host sends to ollama
tools/spike-run.py         run an opencode agent N times and tabulate
setup/                     what a machine needs (ollama context window, opencode config)
docs/spikes/               what was measured, with numbers — read these first
docs/adr/                  the decisions
```

Measured so far on Qwen 3.5 2B (see `docs/spikes/`): a read-only task runs
in ~30 s with a valid JSON answer 5/5 and recall 10/10 on the control runner
(floor 545 tokens) versus 28–1490 s and 1/12 valid formats through opencode;
a write task (add a Vitest test) lands 2/3 fully correct once the runner's
guards and one task-specific prompt rule are in place.

## Planned layout

```
agents/<task>/      one folder per task: agent.md + fixtures/ + scenarios.yaml
core/base.md        shared rules; starts EMPTY, each line buys its way in by measurement
harness/            run N times, judge, budget, runs/ — spike-run.py and control.py are its seeds
MODELOS.md          what each model does with and without the sidekicks
```
