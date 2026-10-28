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

## Planned layout

```
agents/<task>/      one folder per task: agent.md + fixtures/ + scenarios.yaml
core/base.md        shared rules; starts EMPTY, each line buys its way in by measurement
harness/            run.py (opencode run, with/without agent), judge.py, budget.py, runs/
install.py          renders agents into opencode's agents directory
MODELOS.md          what each model does with and without the sidekicks
```

Status: skeleton. Nothing runs yet.
