# claude-benchmark

A deterministic coding benchmark for comparing Claude Code's performance and cost
across different access environments — personal subscription, personal API key,
work subscription, work API key — using a fixed set of self-authored Python coding
tasks.

The goal is not to grade the model in the abstract, but to answer a practical
question: for the *same* 12 coding tasks, how do pass-rate, cost, and duration
differ depending on which Claude Code account/billing path you run through?

## How it works

- 12 self-contained Python tasks live under `tasks/<id>/` — 4 easy / 4 medium /
  4 hard, two each across bug-fix, feature-add, refactor, algorithm,
  multi-file-reasoning, and perf-optimization. Each task has a `seed/` (the
  starting code Claude Code sees, with a bug/stub/tangle to fix), a fixed
  `prompt.md`, and a hidden `tests/` suite that's never shown to the agent.
- `harness/run.py` drives Claude Code non-interactively against each task,
  3 repeats per task, scoring purely by pytest exit code (no LLM judging).
  Each run gets a disposable working directory and its own `uv`-managed venv.
- `harness/report.py` aggregates the results into a markdown comparison table
  and a self-contained HTML dashboard — pass-rate, cost, duration, and token
  usage per environment, plus an overall per-environment rollup, with warnings
  if the underlying model or Claude Code version drifted between environments
  (which would invalidate the comparison).

Results are stored as append-only JSONL under `results/<env>.jsonl` — one file
per environment, so runs from separate machines can be copied into the same
`results/` directory and merged by `report.py`.

## Usage

Each of the 4 environments is assumed to already be configured in your own
shell (e.g. via shell functions that set `ANTHROPIC_API_KEY` / Claude Code's
auth config per account). The harness does not manage credentials or switch
environments itself — you activate one, then run the harness once per
environment, tagging it with whatever label you choose:

```bash
# in a shell already configured for one environment:
uv run python harness/run.py --env personal-sub

# repeat once per environment, in that environment's own shell:
uv run python harness/run.py --env personal-api
uv run python harness/run.py --env work-sub
uv run python harness/run.py --env work-api
```

Smoke-test a single fixture cheaply before a full run:

```bash
uv run python harness/run.py --env smoke-test --task easy-01-fix-average --repeats 1
```

Generate the comparison report once some `results/*.jsonl` files exist:

```bash
uv run python harness/report.py
```

This prints a markdown table to stdout and writes `reports/dashboard.html`.

## Development

```bash
uv run pytest -q
```

Design spec and implementation plan live under `docs/superpowers/`.
