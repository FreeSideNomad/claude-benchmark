# Claude Cross-Environment Coding Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a harness that runs 12 self-authored, deterministic Python coding tasks through Claude Code non-interactively, 3 times each, and compares pass-rate/cost/duration across whichever of the 4 access environments (personal subscription, personal API, work subscription, work API) the user invokes it under.

**Architecture:** A `harness/` package with small, independently-testable modules (`worktree`, `env_setup`, `claude_runner`, `scorer`, `aggregate`) composed by two thin CLIs — `run.py` (executes tasks against one environment, appends JSONL rows) and `report.py` (aggregates all environments' JSONL into a comparison table + static HTML dashboard). A `tasks/` directory holds 12 self-contained fixtures (seed code + hidden pytest suite + fixed prompt).

**Tech Stack:** Python 3.11+, stdlib only for the harness itself, `pytest` for scoring and for the harness's own test suite, `uv` for all dependency installs (both the harness's own dev deps and each task's disposable per-run venv), the `claude` CLI (Claude Code 2.1.233 or compatible) invoked via `subprocess`.

## Global Constraints

- Python-only task set for v1 — no other languages.
- All dependency installation, for the harness's own dev deps and for each task's per-run venv, goes through `uv` (`uv venv` / `uv pip install`), never plain `venv`/`pip`.
- Scoring is pytest exit-code only — no LLM-judged grading.
- Every task runs exactly 3 repeats per environment; this is not a configurable-down CLI default (it can be overridden explicitly for smoke-testing, see Task 8).
- Tasks must be self-contained and offline — no network calls during Claude Code's run or during test execution.
- Hidden `tests/` must never be present in a task's `seed/` — only copied in by the harness after Claude Code's run completes.
- `prompt.md` is fixed, committed text for every task — never templated or randomized at run time.
- Every results row must record `model` and `claude_code_version`; `report.py` must flag (not silently average over) any drift in either across environments for the same task.
- Results are append-only JSONL, one file per environment at `results/<env>.jsonl`.
- A task's seed code must never contain its own nested `.git` — `create_worktree` works by plain file copy, not `git worktree add` (see spec rationale).

---

## Part A — Harness library and CLIs

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `harness/__init__.py`
- Create: `harness/lib/__init__.py`
- Create: `tasks/.gitkeep`
- Create: `results/.gitkeep`
- Create: `reports/.gitkeep`

**Interfaces:**
- Produces: an importable `harness` package (so later tasks can `from harness.lib.X import ...`) and a working `uv run pytest` command for the harness's own test suite.

- [ ] **Step 1: Initialize the uv project**

Run:
```bash
cd /Users/igormusic/code/claude-benchmark
uv init --bare --name claude-benchmark --python 3.11
```
Expected: creates `pyproject.toml` with `[project]` name/version/requires-python.

- [ ] **Step 2: Add pytest as a dev dependency**

Run:
```bash
uv add --dev pytest
```
Expected: `pyproject.toml` gains a `[dependency-groups]` / `dev = [...]` entry containing `pytest`, and `uv.lock` is created.

- [ ] **Step 3: Configure pytest to find the `harness` package and `tests/` dir**

Edit `pyproject.toml`, adding:
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 4: Create package `__init__.py` files**

`harness/__init__.py`:
```python
```
(empty file)

`harness/lib/__init__.py`:
```python
```
(empty file)

- [ ] **Step 5: Create data directories with placeholders**

`tasks/.gitkeep`, `results/.gitkeep`, `reports/.gitkeep` — each an empty file, so the directories exist in a fresh clone before any tasks/results are added.

- [ ] **Step 6: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
reports/dashboard.html
```

- [ ] **Step 7: Create an empty `tests/` dir with a trivial smoke test**

`tests/test_smoke.py`:
```python
def test_smoke():
    assert 1 + 1 == 2
```

- [ ] **Step 8: Run the test suite to confirm the project is wired correctly**

Run: `uv run pytest -q`
Expected: `1 passed`

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock .gitignore harness tasks/.gitkeep results/.gitkeep reports/.gitkeep tests/test_smoke.py
git commit -m "Scaffold uv project with harness package skeleton"
```

---

### Task 2: `harness/lib/worktree.py` — disposable per-run working directory

**Files:**
- Create: `harness/lib/worktree.py`
- Test: `tests/test_worktree.py`

**Interfaces:**
- Produces: `create_worktree(seed_dir: Path, work_dir: Path) -> Path`, `remove_worktree(work_dir: Path) -> None`.

- [ ] **Step 1: Write the failing tests**

`tests/test_worktree.py`:
```python
from harness.lib.worktree import create_worktree, remove_worktree


def test_create_worktree_copies_seed_content(tmp_path):
    seed_dir = tmp_path / "seed"
    work_dir = tmp_path / "work"
    seed_dir.mkdir()
    (seed_dir / "hello.txt").write_text("hello\n")
    (seed_dir / "sub").mkdir()
    (seed_dir / "sub" / "nested.txt").write_text("nested\n")

    create_worktree(seed_dir, work_dir)

    assert (work_dir / "hello.txt").read_text() == "hello\n"
    assert (work_dir / "sub" / "nested.txt").read_text() == "nested\n"


def test_remove_worktree_deletes_work_dir(tmp_path):
    seed_dir = tmp_path / "seed"
    work_dir = tmp_path / "work"
    seed_dir.mkdir()
    (seed_dir / "hello.txt").write_text("hello\n")
    create_worktree(seed_dir, work_dir)

    remove_worktree(work_dir)

    assert not work_dir.exists()


def test_remove_worktree_is_safe_if_already_missing(tmp_path):
    remove_worktree(tmp_path / "does-not-exist")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_worktree.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.lib.worktree'`

- [ ] **Step 3: Implement**

`harness/lib/worktree.py`:
```python
from __future__ import annotations

import shutil
from pathlib import Path


def create_worktree(seed_dir: Path, work_dir: Path) -> Path:
    """Copy a task's seed/ files into a fresh disposable working directory."""
    shutil.copytree(seed_dir, work_dir)
    return work_dir


def remove_worktree(work_dir: Path) -> None:
    """Remove a working directory created by create_worktree."""
    shutil.rmtree(work_dir, ignore_errors=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_worktree.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/lib/worktree.py tests/test_worktree.py
git commit -m "Add disposable per-run working directory helper"
```

---

### Task 3: `harness/lib/env_setup.py` — uv-managed per-task venv

**Files:**
- Create: `harness/lib/env_setup.py`
- Test: `tests/test_env_setup.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `create_venv(work_dir: Path) -> None`, `install_requirements(work_dir: Path, requirements_file: Path) -> None`.

- [ ] **Step 1: Write the failing tests**

`tests/test_env_setup.py`:
```python
from pathlib import Path
from unittest.mock import patch

from harness.lib.env_setup import create_venv, install_requirements


def test_create_venv_runs_uv_venv_in_work_dir():
    with patch("harness.lib.env_setup.subprocess.run") as mock_run:
        create_venv(Path("/tmp/work"))

    mock_run.assert_called_once_with(
        ["uv", "venv"], cwd=Path("/tmp/work"), check=True, capture_output=True
    )


def test_install_requirements_runs_uv_pip_install():
    with patch("harness.lib.env_setup.subprocess.run") as mock_run:
        install_requirements(Path("/tmp/work"), Path("/tmp/task/requirements.txt"))

    mock_run.assert_called_once_with(
        ["uv", "pip", "install", "pytest", "-r", "/tmp/task/requirements.txt"],
        cwd=Path("/tmp/work"),
        check=True,
        capture_output=True,
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_env_setup.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.lib.env_setup'`

- [ ] **Step 3: Implement**

`harness/lib/env_setup.py`:
```python
from __future__ import annotations

import subprocess
from pathlib import Path


def create_venv(work_dir: Path) -> None:
    subprocess.run(["uv", "venv"], cwd=work_dir, check=True, capture_output=True)


def install_requirements(work_dir: Path, requirements_file: Path) -> None:
    subprocess.run(
        ["uv", "pip", "install", "pytest", "-r", str(requirements_file)],
        cwd=work_dir,
        check=True,
        capture_output=True,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_env_setup.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/lib/env_setup.py tests/test_env_setup.py
git commit -m "Add uv-based per-task venv setup helpers"
```

---

### Task 4: `harness/lib/claude_runner.py` — invoke Claude Code, normalize usage/cost

**Files:**
- Create: `harness/lib/claude_runner.py`
- Test: `tests/test_claude_runner.py`

**Interfaces:**
- Produces: `get_claude_version() -> str`, `run_claude(prompt: str, cwd: Path) -> dict` returning keys `is_error`, `total_cost_usd`, `duration_ms`, `num_turns`, `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `model`.

- [ ] **Step 1: Write the failing tests**

`tests/test_claude_runner.py`:
```python
import json
import subprocess
from unittest.mock import patch

from harness.lib.claude_runner import get_claude_version, run_claude

SAMPLE_RESULT_JSON = json.dumps(
    {
        "is_error": False,
        "duration_api_ms": 1986,
        "num_turns": 1,
        "stop_reason": "end_turn",
        "session_id": "13d34318-e616-494b-9297-3e96efbcd2f6",
        "total_cost_usd": 0.1513,
        "usage": {
            "input_tokens": 2,
            "cache_creation_input_tokens": 23954,
            "cache_read_input_tokens": 25151,
            "output_tokens": 4,
        },
        "modelUsage": {
            "claude-sonnet-5": {
                "inputTokens": 2,
                "outputTokens": 4,
                "costUSD": 0.1513,
                "canonicalModel": "claude-sonnet-5",
            }
        },
        "result": "ok",
        "type": "result",
        "duration_ms": 2052,
    }
)


def test_get_claude_version_strips_output():
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="2.1.233 (Claude Code)\n")
    with patch("harness.lib.claude_runner.subprocess.run", return_value=completed) as mock_run:
        version = get_claude_version()

    assert version == "2.1.233 (Claude Code)"
    mock_run.assert_called_once_with(["claude", "--version"], capture_output=True, text=True, check=True)


def test_run_claude_normalizes_fields(tmp_path):
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=SAMPLE_RESULT_JSON)
    with patch("harness.lib.claude_runner.subprocess.run", return_value=completed):
        result = run_claude("do the thing", cwd=tmp_path)

    assert result == {
        "is_error": False,
        "total_cost_usd": 0.1513,
        "duration_ms": 2052,
        "num_turns": 1,
        "input_tokens": 2,
        "output_tokens": 4,
        "cache_creation_input_tokens": 23954,
        "cache_read_input_tokens": 25151,
        "model": "claude-sonnet-5",
    }


def test_run_claude_joins_multiple_models_sorted(tmp_path):
    raw = json.loads(SAMPLE_RESULT_JSON)
    raw["modelUsage"]["claude-haiku-4-5"] = raw["modelUsage"]["claude-sonnet-5"]
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(raw))
    with patch("harness.lib.claude_runner.subprocess.run", return_value=completed):
        result = run_claude("do the thing", cwd=tmp_path)

    assert result["model"] == "claude-haiku-4-5,claude-sonnet-5"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_claude_runner.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.lib.claude_runner'`

- [ ] **Step 3: Implement**

`harness/lib/claude_runner.py`:
```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def get_claude_version() -> str:
    result = subprocess.run(["claude", "--version"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def run_claude(prompt: str, cwd: Path) -> dict:
    """Run Claude Code non-interactively in `cwd` and return a normalized result dict."""
    result = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--permission-mode",
            "acceptEdits",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    raw = json.loads(result.stdout)
    usage = raw["usage"]
    model_usage = raw.get("modelUsage", {})
    return {
        "is_error": raw["is_error"],
        "total_cost_usd": raw["total_cost_usd"],
        "duration_ms": raw["duration_ms"],
        "num_turns": raw["num_turns"],
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
        "model": ",".join(sorted(model_usage.keys())),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_claude_runner.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/lib/claude_runner.py tests/test_claude_runner.py
git commit -m "Add Claude Code non-interactive runner with normalized usage/cost fields"
```

---

### Task 5: `harness/lib/scorer.py` — overlay hidden tests, run pytest

**Files:**
- Create: `harness/lib/scorer.py`
- Test: `tests/test_scorer.py`

**Interfaces:**
- Produces: `overlay_tests(task_dir: Path, work_dir: Path) -> None`, `run_pytest(work_dir: Path) -> bool`, `score_task(task_dir: Path, work_dir: Path) -> bool`.

- [ ] **Step 1: Write the failing tests**

`tests/test_scorer.py`:
```python
import subprocess
from unittest.mock import patch

from harness.lib.scorer import overlay_tests, run_pytest, score_task


def test_overlay_tests_copies_files(tmp_path):
    task_dir = tmp_path / "task"
    work_dir = tmp_path / "work"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test_x.py").write_text("def test_x(): pass\n")
    work_dir.mkdir()

    overlay_tests(task_dir, work_dir)

    assert (work_dir / "tests" / "test_x.py").read_text() == "def test_x(): pass\n"


def test_overlay_tests_replaces_existing_tests_dir(tmp_path):
    task_dir = tmp_path / "task"
    work_dir = tmp_path / "work"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test_new.py").write_text("def test_new(): pass\n")
    (work_dir / "tests").mkdir(parents=True)
    (work_dir / "tests" / "stale.py").write_text("stale\n")

    overlay_tests(task_dir, work_dir)

    assert not (work_dir / "tests" / "stale.py").exists()
    assert (work_dir / "tests" / "test_new.py").exists()


def test_run_pytest_returns_true_on_success(tmp_path):
    completed = subprocess.CompletedProcess(args=[], returncode=0)
    with patch("harness.lib.scorer.subprocess.run", return_value=completed):
        assert run_pytest(tmp_path) is True


def test_run_pytest_returns_false_on_failure(tmp_path):
    completed = subprocess.CompletedProcess(args=[], returncode=1)
    with patch("harness.lib.scorer.subprocess.run", return_value=completed):
        assert run_pytest(tmp_path) is False


def test_score_task_overlays_then_runs(tmp_path):
    task_dir = tmp_path / "task"
    work_dir = tmp_path / "work"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test_x.py").write_text("def test_x(): pass\n")
    work_dir.mkdir()

    with patch("harness.lib.scorer.run_pytest", return_value=True) as mock_run_pytest:
        assert score_task(task_dir, work_dir) is True

    mock_run_pytest.assert_called_once_with(work_dir)
    assert (work_dir / "tests" / "test_x.py").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scorer.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.lib.scorer'`

- [ ] **Step 3: Implement**

`harness/lib/scorer.py`:
```python
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def overlay_tests(task_dir: Path, work_dir: Path) -> None:
    """Copy the task's hidden tests/ into the working directory, replacing any existing tests/."""
    dest = work_dir / "tests"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(task_dir / "tests", dest)


def run_pytest(work_dir: Path) -> bool:
    """Run the overlaid tests inside the working directory's uv-managed venv. True on pass."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(work_dir)
    result = subprocess.run(
        ["uv", "run", "pytest", "tests", "-q"],
        cwd=work_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def score_task(task_dir: Path, work_dir: Path) -> bool:
    overlay_tests(task_dir, work_dir)
    return run_pytest(work_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scorer.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/lib/scorer.py tests/test_scorer.py
git commit -m "Add hidden-test overlay and pytest-based scorer"
```

---

### Task 6: `harness/lib/aggregate.py` — load and summarize results

**Files:**
- Create: `harness/lib/aggregate.py`
- Test: `tests/test_aggregate.py`

**Interfaces:**
- Produces: `load_results(results_dir: Path) -> list[dict]`, `summarize(rows: list[dict]) -> dict` with shape `{"entries": [...], "warnings": [...]}`. Each entry has keys `env`, `task_id`, `runs`, `passes`, `pass_rate`, `median_cost_usd`, `median_duration_ms`, `median_total_tokens`.

- [ ] **Step 1: Write the failing tests**

`tests/test_aggregate.py`:
```python
import json

from harness.lib.aggregate import load_results, summarize


def _row(**overrides):
    row = {
        "env": "personal-sub",
        "task_id": "easy-01",
        "repeat": 1,
        "pass": True,
        "is_error": False,
        "total_cost_usd": 0.01,
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "duration_ms": 1000,
        "num_turns": 2,
        "model": "claude-sonnet-5",
        "claude_code_version": "2.1.233",
        "timestamp": "2026-10-20T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_load_results_reads_all_jsonl_files(tmp_path):
    (tmp_path / "personal-sub.jsonl").write_text(json.dumps(_row()) + "\n")
    (tmp_path / "work-api.jsonl").write_text(json.dumps(_row(env="work-api")) + "\n")

    rows = load_results(tmp_path)

    assert len(rows) == 2
    assert {r["env"] for r in rows} == {"personal-sub", "work-api"}


def test_summarize_computes_pass_rate_and_medians():
    rows = [
        _row(repeat=1, total_cost_usd=0.01, duration_ms=1000),
        _row(repeat=2, total_cost_usd=0.03, duration_ms=3000),
        _row(repeat=3, **{"pass": False, "total_cost_usd": 0.02, "duration_ms": 2000}),
    ]
    summary = summarize(rows)

    assert len(summary["entries"]) == 1
    entry = summary["entries"][0]
    assert entry["env"] == "personal-sub"
    assert entry["task_id"] == "easy-01"
    assert entry["runs"] == 3
    assert entry["passes"] == 2
    assert entry["pass_rate"] == 2 / 3
    assert entry["median_cost_usd"] == 0.02
    assert entry["median_duration_ms"] == 2000


def test_summarize_flags_model_drift_across_environments():
    rows = [
        _row(env="personal-sub", model="claude-sonnet-5"),
        _row(env="work-api", model="claude-opus-5"),
    ]
    summary = summarize(rows)

    assert any("multiple models" in w for w in summary["warnings"])


def test_summarize_flags_version_drift_across_environments():
    rows = [
        _row(env="personal-sub", claude_code_version="2.1.233"),
        _row(env="work-api", claude_code_version="2.1.200"),
    ]
    summary = summarize(rows)

    assert any("claude_code_version" in w for w in summary["warnings"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_aggregate.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.lib.aggregate'`

- [ ] **Step 3: Implement**

`harness/lib/aggregate.py`:
```python
from __future__ import annotations

import json
import statistics
from pathlib import Path


def load_results(results_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(Path(results_dir).glob("*.jsonl")):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def summarize(rows: list[dict]) -> dict:
    by_env_task: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        by_env_task.setdefault((row["env"], row["task_id"]), []).append(row)

    entries = []
    for (env, task_id), group in sorted(by_env_task.items()):
        passes = sum(1 for r in group if r["pass"])
        entries.append(
            {
                "env": env,
                "task_id": task_id,
                "runs": len(group),
                "passes": passes,
                "pass_rate": passes / len(group),
                "median_cost_usd": statistics.median(r["total_cost_usd"] for r in group),
                "median_duration_ms": statistics.median(r["duration_ms"] for r in group),
                "median_total_tokens": statistics.median(
                    r["input_tokens"] + r["output_tokens"] for r in group
                ),
            }
        )

    by_task: dict[str, list[dict]] = {}
    for row in rows:
        by_task.setdefault(row["task_id"], []).append(row)

    warnings = []
    for task_id, task_rows in sorted(by_task.items()):
        models = {r["model"] for r in task_rows}
        versions = {r["claude_code_version"] for r in task_rows}
        if len(models) > 1:
            warnings.append(f"{task_id}: multiple models observed across environments: {sorted(models)}")
        if len(versions) > 1:
            warnings.append(
                f"{task_id}: multiple claude_code_version values observed across environments: {sorted(versions)}"
            )

    return {"entries": entries, "warnings": warnings}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_aggregate.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/lib/aggregate.py tests/test_aggregate.py
git commit -m "Add results aggregation with pass-rate/median stats and drift warnings"
```

---

### Task 7: `harness/report.py` — comparison table + HTML dashboard

**Files:**
- Create: `harness/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `load_results`, `summarize` from `harness.lib.aggregate` (Task 6).
- Produces: `render_markdown_table(summary: dict) -> str`, `render_html_dashboard(summary: dict) -> str`, `main(results_dir: Path, out_path: Path) -> None`.

- [ ] **Step 1: Write the failing tests**

`tests/test_report.py`:
```python
import json

from harness.lib.aggregate import summarize
from harness.report import main, render_html_dashboard, render_markdown_table

SAMPLE_ROW = {
    "env": "personal-sub",
    "task_id": "easy-01",
    "repeat": 1,
    "pass": True,
    "is_error": False,
    "total_cost_usd": 0.02,
    "input_tokens": 10,
    "output_tokens": 5,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "duration_ms": 1500,
    "num_turns": 1,
    "model": "claude-sonnet-5",
    "claude_code_version": "2.1.233",
    "timestamp": "2026-10-20T00:00:00Z",
}


def _sample_summary():
    return summarize([SAMPLE_ROW])


def test_render_markdown_table_includes_task_row():
    table = render_markdown_table(_sample_summary())
    assert "easy-01" in table
    assert "1/1" in table


def test_render_html_dashboard_is_self_contained_and_includes_data():
    html = render_html_dashboard(_sample_summary())
    assert "<html>" in html
    assert "easy-01" in html
    assert "http://" not in html
    assert "https://" not in html


def test_main_writes_dashboard_file_and_prints_table(tmp_path, capsys):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    (results_dir / "personal-sub.jsonl").write_text(json.dumps(SAMPLE_ROW) + "\n")
    out_path = tmp_path / "reports" / "dashboard.html"

    main(results_dir=results_dir, out_path=out_path)

    captured = capsys.readouterr()
    assert "easy-01" in captured.out
    assert out_path.exists()
    assert "easy-01" in out_path.read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_report.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.report'`

- [ ] **Step 3: Implement**

`harness/report.py`:
```python
from __future__ import annotations

import argparse
from pathlib import Path

from harness.lib.aggregate import load_results, summarize

REPO_ROOT = Path(__file__).resolve().parent.parent


def render_markdown_table(summary: dict) -> str:
    lines = [
        "| env | task_id | pass_rate | median_cost_usd | median_duration_ms |",
        "| --- | --- | --- | --- | --- |",
    ]
    for e in summary["entries"]:
        lines.append(
            f"| {e['env']} | {e['task_id']} | {e['passes']}/{e['runs']} "
            f"| ${e['median_cost_usd']:.4f} | {e['median_duration_ms']:.0f} |"
        )
    if summary["warnings"]:
        lines.append("")
        lines.append("**Warnings:**")
        for w in summary["warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines)


def render_html_dashboard(summary: dict) -> str:
    rows_html = "\n".join(
        f"<tr><td>{e['env']}</td><td>{e['task_id']}</td>"
        f"<td>{e['passes']}/{e['runs']}</td>"
        f"<td>${e['median_cost_usd']:.4f}</td>"
        f"<td>{e['median_duration_ms']:.0f}</td></tr>"
        for e in summary["entries"]
    )
    warnings_html = "".join(f"<li>{w}</li>" for w in summary["warnings"])
    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Claude benchmark results</title>
<style>
table {{ border-collapse: collapse; font-family: sans-serif; }}
td, th {{ border: 1px solid #ccc; padding: 4px 8px; }}
</style>
</head>
<body>
<h1>Claude benchmark results</h1>
<table>
<tr><th>env</th><th>task_id</th><th>pass rate</th><th>median cost (USD)</th><th>median duration (ms)</th></tr>
{rows_html}
</table>
<h2>Warnings</h2>
<ul>{warnings_html}</ul>
</body>
</html>
"""


def main(
    results_dir: Path = REPO_ROOT / "results",
    out_path: Path = REPO_ROOT / "reports" / "dashboard.html",
) -> None:
    rows = load_results(results_dir)
    summary = summarize(rows)
    print(render_markdown_table(summary))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html_dashboard(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=REPO_ROOT / "results")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "reports" / "dashboard.html")
    args = parser.parse_args()
    main(results_dir=args.results_dir, out_path=args.out)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_report.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add harness/report.py tests/test_report.py
git commit -m "Add comparison table and self-contained HTML dashboard report"
```

---

### Task 8: `harness/run.py` — orchestrator CLI

**Files:**
- Create: `harness/run.py`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: `create_worktree`/`remove_worktree` (Task 2), `create_venv`/`install_requirements` (Task 3), `get_claude_version`/`run_claude` (Task 4), `score_task` (Task 5).
- Produces: `discover_tasks(tasks_dir: Path) -> list[Path]`, `execute_task_repeat(task_dir: Path, env: str, repeat: int) -> dict`, `run(env: str, task_filter: str | None, repeats: int) -> None`.

- [ ] **Step 1: Write the failing tests**

`tests/test_run.py`:
```python
from unittest.mock import patch

from harness.run import discover_tasks, execute_task_repeat


def test_discover_tasks_finds_only_task_dirs(tmp_path):
    (tmp_path / "easy-01").mkdir()
    (tmp_path / "easy-01" / "meta.yaml").write_text("id: easy-01\n")
    (tmp_path / "not_a_task").mkdir()
    (tmp_path / "stray_file.txt").write_text("x")

    tasks = discover_tasks(tmp_path)

    assert [t.name for t in tasks] == ["easy-01"]


def _fake_result():
    return {
        "is_error": False,
        "total_cost_usd": 0.05,
        "duration_ms": 1000,
        "num_turns": 2,
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "model": "claude-sonnet-5",
    }


def _make_task_dir(tmp_path):
    task_dir = tmp_path / "easy-01"
    task_dir.mkdir()
    (task_dir / "prompt.md").write_text("fix the bug")
    (task_dir / "seed").mkdir()
    (task_dir / "requirements.txt").write_text("")
    return task_dir


def test_execute_task_repeat_wires_lib_calls_and_returns_row(tmp_path):
    task_dir = _make_task_dir(tmp_path)

    with patch("harness.run.worktree.create_worktree") as mock_create, \
         patch("harness.run.worktree.remove_worktree") as mock_remove, \
         patch("harness.run.env_setup.create_venv") as mock_venv, \
         patch("harness.run.env_setup.install_requirements") as mock_install, \
         patch("harness.run.claude_runner.get_claude_version", return_value="2.1.233") as mock_version, \
         patch("harness.run.claude_runner.run_claude", return_value=_fake_result()) as mock_run_claude, \
         patch("harness.run.scorer.score_task", return_value=True) as mock_score:
        row = execute_task_repeat(task_dir, env="personal-sub", repeat=1)

    assert mock_create.called
    assert mock_venv.called
    assert mock_install.called
    assert mock_version.called
    assert mock_run_claude.call_args.args[0] == "fix the bug"
    assert mock_score.called
    assert mock_remove.called
    assert row["env"] == "personal-sub"
    assert row["task_id"] == "easy-01"
    assert row["repeat"] == 1
    assert row["pass"] is True
    assert row["total_cost_usd"] == 0.05
    assert row["claude_code_version"] == "2.1.233"
    assert "timestamp" in row


def test_execute_task_repeat_removes_worktree_even_if_scoring_fails(tmp_path):
    task_dir = _make_task_dir(tmp_path)

    with patch("harness.run.worktree.create_worktree"), \
         patch("harness.run.worktree.remove_worktree") as mock_remove, \
         patch("harness.run.env_setup.create_venv"), \
         patch("harness.run.env_setup.install_requirements"), \
         patch("harness.run.claude_runner.get_claude_version", return_value="2.1.233"), \
         patch("harness.run.claude_runner.run_claude", return_value=_fake_result()), \
         patch("harness.run.scorer.score_task", side_effect=RuntimeError("boom")):
        try:
            execute_task_repeat(task_dir, env="personal-sub", repeat=1)
        except RuntimeError:
            pass

    assert mock_remove.called
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.run'`

- [ ] **Step 3: Implement**

`harness/run.py`:
```python
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from harness.lib import claude_runner, env_setup, scorer, worktree

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
RESULTS_DIR = REPO_ROOT / "results"
REPEATS = 3


def discover_tasks(tasks_dir: Path = TASKS_DIR) -> list[Path]:
    return sorted(p for p in tasks_dir.iterdir() if (p / "meta.yaml").exists())


def execute_task_repeat(task_dir: Path, env: str, repeat: int) -> dict:
    task_id = task_dir.name
    prompt = (task_dir / "prompt.md").read_text()
    base_dir = Path(tempfile.mkdtemp(prefix=f"{task_id}-r{repeat}-"))
    work_dir = base_dir / "work"

    try:
        worktree.create_worktree(task_dir / "seed", work_dir)
        env_setup.create_venv(work_dir)
        env_setup.install_requirements(work_dir, task_dir / "requirements.txt")
        claude_version = claude_runner.get_claude_version()
        result = claude_runner.run_claude(prompt, cwd=work_dir)
        passed = scorer.score_task(task_dir, work_dir)
    finally:
        worktree.remove_worktree(base_dir)

    return {
        "env": env,
        "task_id": task_id,
        "repeat": repeat,
        "pass": passed,
        **result,
        "claude_code_version": claude_version,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def run(env: str, task_filter: str | None = None, repeats: int = REPEATS) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / f"{env}.jsonl"
    tasks = discover_tasks()
    if task_filter:
        tasks = [t for t in tasks if t.name == task_filter]

    for task_dir in tasks:
        for repeat in range(1, repeats + 1):
            print(f"[{env}] {task_dir.name} repeat {repeat}/{repeats}...")
            row = execute_task_repeat(task_dir, env, repeat)
            with open(results_path, "a") as f:
                f.write(json.dumps(row) + "\n")
            print(f"  -> pass={row['pass']} cost=${row['total_cost_usd']:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    parser.add_argument("--task", help="Only run this single task_id (for smoke-testing)")
    parser.add_argument("--repeats", type=int, default=REPEATS, help="Override repeats per task")
    args = parser.parse_args()
    run(args.env, task_filter=args.task, repeats=args.repeats)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_run.py -q`
Expected: `3 passed`

- [ ] **Step 5: Run the full harness test suite**

Run: `uv run pytest -q`
Expected: all tests across Tasks 1-8 pass (the `test_smoke.py` placeholder from Task 1 can now be deleted since real tests exist — delete `tests/test_smoke.py`).

- [ ] **Step 6: Commit**

```bash
git rm tests/test_smoke.py
git add harness/run.py tests/test_run.py
git commit -m "Add orchestrator CLI wiring worktree/env/claude/scorer per task repeat"
```

---

## Part B — Task fixtures

Each fixture task follows the same shape: create `meta.yaml` / `prompt.md` / `requirements.txt` (empty) / `seed/*.py` (containing the bug or unimplemented stub) / `tests/*.py` (hidden suite), verify the tests FAIL against the seed as shipped (proving the suite exercises the defect), verify the tests PASS against a reference fix applied temporarily, then revert the seed back to its shipped (broken) state before committing. `requirements.txt` is an empty file for every fixture (no third-party deps needed).

The verify commands below are run from the task's own directory and mirror exactly what `harness/lib/scorer.py` does at benchmark time (copy `tests/` next to the code, run with `PYTHONPATH` pointing at the code root).

### Task 9: Fixture `easy-01-fix-average` (bug-fix / easy)

**Files:**
- Create: `tasks/easy-01-fix-average/meta.yaml`
- Create: `tasks/easy-01-fix-average/prompt.md`
- Create: `tasks/easy-01-fix-average/requirements.txt`
- Create: `tasks/easy-01-fix-average/seed/stats.py`
- Create: `tasks/easy-01-fix-average/tests/test_stats.py`

- [ ] **Step 1: Create the fixture files**

`tasks/easy-01-fix-average/meta.yaml`:
```yaml
id: easy-01-fix-average
title: Fix average() bug
difficulty: easy
category: bug-fix
```

`tasks/easy-01-fix-average/prompt.md`:
```
The `average` function in `stats.py` is supposed to return the arithmetic
mean of a list of numbers as a float, and raise `ValueError` for an empty
list. Fix it.
```

`tasks/easy-01-fix-average/requirements.txt`:
```
```
(empty file)

`tasks/easy-01-fix-average/seed/stats.py`:
```python
def average(nums):
    if not nums:
        return 0
    total = 0
    for n in nums:
        total += n
    return total // len(nums)
```

`tasks/easy-01-fix-average/tests/test_stats.py`:
```python
import pytest

from stats import average


def test_average_of_integers():
    assert average([1, 2, 3, 4]) == 2.5


def test_average_of_single_value():
    assert average([7]) == 7.0


def test_average_raises_on_empty():
    with pytest.raises(ValueError):
        average([])
```

- [ ] **Step 2: Verify the hidden tests FAIL against the shipped (buggy) seed**

```bash
cd tasks/easy-01-fix-average
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: 2 of 3 tests FAIL (`test_average_of_integers` on the `//` truncation, `test_average_raises_on_empty` because it returns `0` instead of raising).

- [ ] **Step 3: Apply the reference fix temporarily and verify all tests PASS**

Edit `seed/stats.py` to:
```python
def average(nums):
    if not nums:
        raise ValueError("average of empty list")
    return sum(nums) / len(nums)
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `3 passed`

- [ ] **Step 4: Revert the seed back to the shipped (buggy) version and clean up**

Edit `seed/stats.py` back to its original Step 1 content (the `//`/no-raise version), then:
```bash
cd ..            # back to tasks/easy-01-fix-average
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/easy-01-fix-average
git commit -m "Add fixture: easy-01-fix-average"
```

---

### Task 10: Fixture `easy-02-simplify-shipping-cost` (refactor / easy)

**Files:**
- Create: `tasks/easy-02-simplify-shipping-cost/meta.yaml`
- Create: `tasks/easy-02-simplify-shipping-cost/prompt.md`
- Create: `tasks/easy-02-simplify-shipping-cost/requirements.txt`
- Create: `tasks/easy-02-simplify-shipping-cost/seed/shipping.py`
- Create: `tasks/easy-02-simplify-shipping-cost/tests/test_shipping.py`

- [ ] **Step 1: Create the fixture files**

`tasks/easy-02-simplify-shipping-cost/meta.yaml`:
```yaml
id: easy-02-simplify-shipping-cost
title: Simplify nested shipping-cost conditionals
difficulty: easy
category: refactor
```

`tasks/easy-02-simplify-shipping-cost/prompt.md`:
```
`shipping_cost` in `shipping.py` works correctly but is deeply nested and
hard to follow. Refactor it to be flatter and clearer (e.g. a small rate
table instead of nested if/else) without changing its behavior for any
input. `country` is only ever `'US'` or `'INTL'`, and both `is_express`
values must be handled.
```

`tasks/easy-02-simplify-shipping-cost/requirements.txt`:
```
```
(empty file)

`tasks/easy-02-simplify-shipping-cost/seed/shipping.py`:
```python
def shipping_cost(weight_kg, country, is_express):
    if country == "US":
        if is_express:
            if weight_kg <= 1:
                return 15
            else:
                return 15 + (weight_kg - 1) * 4
        else:
            if weight_kg <= 1:
                return 6
            else:
                return 6 + (weight_kg - 1) * 2
    else:
        if is_express:
            if weight_kg <= 1:
                return 30
            else:
                return 30 + (weight_kg - 1) * 8
        else:
            if weight_kg <= 1:
                return 12
            else:
                return 12 + (weight_kg - 1) * 5
```

`tasks/easy-02-simplify-shipping-cost/tests/test_shipping.py`:
```python
from shipping import shipping_cost


def test_us_standard_base_rate():
    assert shipping_cost(1, "US", False) == 6


def test_us_standard_extra_weight():
    assert shipping_cost(3, "US", False) == 10


def test_us_express():
    assert shipping_cost(2, "US", True) == 19


def test_intl_standard():
    assert shipping_cost(1, "INTL", False) == 12


def test_intl_express_extra_weight():
    assert shipping_cost(4, "INTL", True) == 54
```

- [ ] **Step 2: Verify the hidden tests PASS against the shipped seed**

This fixture's seed is already behaviorally correct (it's a refactor task, not a bug fix), so the check here is that the tests pass *before* any refactor — proving the test suite correctly describes current behavior:
```bash
cd tasks/easy-02-simplify-shipping-cost
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: `5 passed`

- [ ] **Step 3: Verify a refactored version still passes (behavior-preservation check)**

Temporarily replace `seed/shipping.py` with a flattened version:
```python
_RATES = {
    ("US", True): (15, 4),
    ("US", False): (6, 2),
    ("INTL", True): (30, 8),
    ("INTL", False): (12, 5),
}


def shipping_cost(weight_kg, country, is_express):
    base, per_extra_kg = _RATES[(country, is_express)]
    extra_kg = max(weight_kg - 1, 0)
    return base + extra_kg * per_extra_kg
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `5 passed` (confirms the hidden tests accept a legitimately refactored, behavior-equivalent solution)

- [ ] **Step 4: Revert the seed back to its original nested form and clean up**

Edit `seed/shipping.py` back to the original Step 1 nested version, then:
```bash
cd ..            # back to tasks/easy-02-simplify-shipping-cost
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/easy-02-simplify-shipping-cost
git commit -m "Add fixture: easy-02-simplify-shipping-cost"
```

---

### Task 11: Fixture `easy-03-fix-plugin-wiring` (multi-file-reasoning / easy)

**Files:**
- Create: `tasks/easy-03-fix-plugin-wiring/meta.yaml`
- Create: `tasks/easy-03-fix-plugin-wiring/prompt.md`
- Create: `tasks/easy-03-fix-plugin-wiring/requirements.txt`
- Create: `tasks/easy-03-fix-plugin-wiring/seed/greeter.py`
- Create: `tasks/easy-03-fix-plugin-wiring/seed/formatter.py`
- Create: `tasks/easy-03-fix-plugin-wiring/tests/test_greeter.py`

- [ ] **Step 1: Create the fixture files**

`tasks/easy-03-fix-plugin-wiring/meta.yaml`:
```yaml
id: easy-03-fix-plugin-wiring
title: Fix cross-module shout() behavior
difficulty: easy
category: multi-file-reasoning
```

`tasks/easy-03-fix-plugin-wiring/prompt.md`:
```
`greet(name)` in `greeter.py` should return the greeting shouted —
upper-cased with a trailing `!` — e.g. `greet('ana')` should return
`'HELLO, ANA!'`. It calls `shout` from `formatter.py`, which currently
just returns the text unchanged. Fix `shout` so `greet` behaves as
described.
```

`tasks/easy-03-fix-plugin-wiring/requirements.txt`:
```
```
(empty file)

`tasks/easy-03-fix-plugin-wiring/seed/greeter.py`:
```python
from formatter import shout


def greet(name):
    return shout(f"hello, {name}")
```

`tasks/easy-03-fix-plugin-wiring/seed/formatter.py`:
```python
def shout(text):
    return text
```

`tasks/easy-03-fix-plugin-wiring/tests/test_greeter.py`:
```python
from formatter import shout
from greeter import greet


def test_shout_uppercases_and_adds_exclamation():
    assert shout("hi") == "HI!"


def test_greet_uses_shout():
    assert greet("ana") == "HELLO, ANA!"
```

- [ ] **Step 2: Verify the hidden tests FAIL against the shipped seed**

```bash
cd tasks/easy-03-fix-plugin-wiring
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: `2 failed` (both — `shout` currently passes text through unchanged)

- [ ] **Step 3: Apply the reference fix temporarily and verify all tests PASS**

Edit `seed/formatter.py` to:
```python
def shout(text):
    return text.upper() + "!"
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `2 passed`

- [ ] **Step 4: Revert the seed back to the shipped version and clean up**

Edit `seed/formatter.py` back to its original Step 1 content, then:
```bash
cd ..            # back to tasks/easy-03-fix-plugin-wiring
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/easy-03-fix-plugin-wiring
git commit -m "Add fixture: easy-03-fix-plugin-wiring"
```

---

### Task 12: Fixture `easy-04-dedupe-performance` (perf-optimization / easy)

**Files:**
- Create: `tasks/easy-04-dedupe-performance/meta.yaml`
- Create: `tasks/easy-04-dedupe-performance/prompt.md`
- Create: `tasks/easy-04-dedupe-performance/requirements.txt`
- Create: `tasks/easy-04-dedupe-performance/seed/dedupe.py`
- Create: `tasks/easy-04-dedupe-performance/tests/test_dedupe.py`

- [ ] **Step 1: Create the fixture files**

`tasks/easy-04-dedupe-performance/meta.yaml`:
```yaml
id: easy-04-dedupe-performance
title: Speed up O(n^2) duplicate removal
difficulty: easy
category: perf-optimization
```

`tasks/easy-04-dedupe-performance/prompt.md`:
```
`unique_preserve_order(items)` in `dedupe.py` returns the items in their
original order with duplicates removed, but is accidentally O(n^2) for
large inputs because of the `item not in result` list scan. Rewrite it to
run in O(n) time (a set to track items already seen), keeping identical
behavior: same order, first occurrence kept, all items are hashable.
```

`tasks/easy-04-dedupe-performance/requirements.txt`:
```
```
(empty file)

`tasks/easy-04-dedupe-performance/seed/dedupe.py`:
```python
def unique_preserve_order(items):
    result = []
    for item in items:
        if item not in result:
            result.append(item)
    return result
```

`tasks/easy-04-dedupe-performance/tests/test_dedupe.py`:
```python
import time

from dedupe import unique_preserve_order


def test_preserves_first_occurrence_order():
    assert unique_preserve_order([3, 1, 3, 2, 1, 4]) == [3, 1, 2, 4]


def test_empty_list():
    assert unique_preserve_order([]) == []


def test_runs_fast_on_large_input():
    items = list(range(20000)) + list(range(10000))
    start = time.perf_counter()
    result = unique_preserve_order(items)
    elapsed = time.perf_counter() - start

    assert result == list(range(20000))
    assert elapsed < 2.0
```

- [ ] **Step 2: Verify the hidden tests against the shipped seed**

```bash
cd tasks/easy-04-dedupe-performance
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: `test_preserves_first_occurrence_order` and `test_empty_list` PASS regardless (the O(n^2) seed is still functionally correct). `test_runs_fast_on_large_input` may pass or fail on the seed depending on hardware — either is fine here: correctness is this fixture's hard gate, the timing bound is a generous secondary nudge toward the O(n) fix, not something this verification step needs to force one way or the other.

- [ ] **Step 3: Apply the reference fix temporarily and verify all tests PASS**

Edit `seed/dedupe.py` to:
```python
def unique_preserve_order(items):
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `3 passed`, comfortably faster than the O(n^2) version.

- [ ] **Step 4: Revert the seed back to the shipped version and clean up**

Edit `seed/dedupe.py` back to its original Step 1 content, then:
```bash
cd ..            # back to tasks/easy-04-dedupe-performance
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/easy-04-dedupe-performance
git commit -m "Add fixture: easy-04-dedupe-performance"
```

---

### Task 13: Fixture `medium-01-fix-cache-ttl` (bug-fix / medium)

**Files:**
- Create: `tasks/medium-01-fix-cache-ttl/meta.yaml`
- Create: `tasks/medium-01-fix-cache-ttl/prompt.md`
- Create: `tasks/medium-01-fix-cache-ttl/requirements.txt`
- Create: `tasks/medium-01-fix-cache-ttl/seed/cache.py`
- Create: `tasks/medium-01-fix-cache-ttl/tests/test_cache.py`

- [ ] **Step 1: Create the fixture files**

`tasks/medium-01-fix-cache-ttl/meta.yaml`:
```yaml
id: medium-01-fix-cache-ttl
title: Fix inverted TTL-expiry check
difficulty: medium
category: bug-fix
```

`tasks/medium-01-fix-cache-ttl/prompt.md`:
```
`TTLCache.get` in `cache.py` should return `None` (and drop the entry)
once `ttl_seconds` has elapsed since the matching `set`, and otherwise
return the stored value. It currently ignores expiry entirely. Fix it,
keeping the existing constructor signature (`ttl_seconds`, optional
`clock` callable) so callers can inject a fake clock in tests.
```

`tasks/medium-01-fix-cache-ttl/requirements.txt`:
```
```
(empty file)

`tasks/medium-01-fix-cache-ttl/seed/cache.py`:
```python
import time


class TTLCache:
    """In-memory cache where each entry expires after `ttl_seconds`."""

    def __init__(self, ttl_seconds, clock=None):
        self.ttl_seconds = ttl_seconds
        self._clock = clock or time.time
        self._store = {}

    def set(self, key, value):
        self._store[key] = (value, self._clock())

    def get(self, key):
        if key not in self._store:
            return None
        value, stored_at = self._store[key]
        if self._clock() - stored_at > self.ttl_seconds:
            return value
        return value
```

`tasks/medium-01-fix-cache-ttl/tests/test_cache.py`:
```python
from cache import TTLCache


def make_clock(times):
    it = iter(times)
    return lambda: next(it)


def test_returns_value_before_expiry():
    cache = TTLCache(ttl_seconds=10, clock=make_clock([0, 5]))
    cache.set("a", "hello")
    assert cache.get("a") == "hello"


def test_returns_none_after_expiry():
    cache = TTLCache(ttl_seconds=10, clock=make_clock([0, 11]))
    cache.set("a", "hello")
    assert cache.get("a") is None


def test_expired_entry_is_dropped():
    cache = TTLCache(ttl_seconds=10, clock=make_clock([0, 11, 20, 20]))
    cache.set("a", "hello")
    assert cache.get("a") is None
    cache.set("a", "world")
    assert cache.get("a") == "world"
```

- [ ] **Step 2: Verify the hidden tests FAIL against the shipped seed**

```bash
cd tasks/medium-01-fix-cache-ttl
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: `2 failed, 1 passed` (`test_returns_none_after_expiry` and `test_expired_entry_is_dropped` fail because expiry is never enforced)

- [ ] **Step 3: Apply the reference fix temporarily and verify all tests PASS**

Edit `seed/cache.py`'s `get` method to:
```python
    def get(self, key):
        if key not in self._store:
            return None
        value, stored_at = self._store[key]
        if self._clock() - stored_at > self.ttl_seconds:
            del self._store[key]
            return None
        return value
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `3 passed`

- [ ] **Step 4: Revert the seed back to the shipped version and clean up**

Edit `seed/cache.py`'s `get` method back to its original Step 1 content, then:
```bash
cd ..            # back to tasks/medium-01-fix-cache-ttl
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/medium-01-fix-cache-ttl
git commit -m "Add fixture: medium-01-fix-cache-ttl"
```

---

### Task 14: Fixture `medium-02-add-csv-filter` (feature-add / medium)

**Files:**
- Create: `tasks/medium-02-add-csv-filter/meta.yaml`
- Create: `tasks/medium-02-add-csv-filter/prompt.md`
- Create: `tasks/medium-02-add-csv-filter/requirements.txt`
- Create: `tasks/medium-02-add-csv-filter/seed/rows.py`
- Create: `tasks/medium-02-add-csv-filter/tests/test_rows.py`

- [ ] **Step 1: Create the fixture files**

`tasks/medium-02-add-csv-filter/meta.yaml`:
```yaml
id: medium-02-add-csv-filter
title: Implement filter_rows()
difficulty: medium
category: feature-add
```

`tasks/medium-02-add-csv-filter/prompt.md`:
```
Implement `filter_rows(rows, predicate)` in `rows.py`. It takes a list of
dicts and a one-argument predicate function, and returns a new list
containing only the rows for which `predicate(row)` returns a truthy
value, preserving the original order. Do not mutate the input list.
```

`tasks/medium-02-add-csv-filter/requirements.txt`:
```
```
(empty file)

`tasks/medium-02-add-csv-filter/seed/rows.py`:
```python
def filter_rows(rows, predicate):
    """Return rows (list[dict]) for which predicate(row) is True.

    Not yet implemented.
    """
    raise NotImplementedError
```

`tasks/medium-02-add-csv-filter/tests/test_rows.py`:
```python
from rows import filter_rows


def test_filters_matching_rows():
    rows = [{"name": "a", "age": 10}, {"name": "b", "age": 20}, {"name": "c", "age": 30}]
    result = filter_rows(rows, lambda r: r["age"] >= 20)
    assert result == [{"name": "b", "age": 20}, {"name": "c", "age": 30}]


def test_preserves_order_and_does_not_mutate_input():
    rows = [{"n": 1}, {"n": 2}, {"n": 3}]
    original = list(rows)
    result = filter_rows(rows, lambda r: r["n"] != 2)
    assert result == [{"n": 1}, {"n": 3}]
    assert rows == original


def test_empty_result_when_nothing_matches():
    rows = [{"n": 1}]
    assert filter_rows(rows, lambda r: r["n"] > 100) == []
```

- [ ] **Step 2: Verify the hidden tests FAIL against the shipped seed**

```bash
cd tasks/medium-02-add-csv-filter
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: `3 failed` (all raise `NotImplementedError`)

- [ ] **Step 3: Apply the reference fix temporarily and verify all tests PASS**

Edit `seed/rows.py` to:
```python
def filter_rows(rows, predicate):
    return [row for row in rows if predicate(row)]
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `3 passed`

- [ ] **Step 4: Revert the seed back to the shipped version and clean up**

Edit `seed/rows.py` back to its original Step 1 content, then:
```bash
cd ..            # back to tasks/medium-02-add-csv-filter
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/medium-02-add-csv-filter
git commit -m "Add fixture: medium-02-add-csv-filter"
```

---

### Task 15: Fixture `medium-03-topological-sort` (algorithm / medium)

**Files:**
- Create: `tasks/medium-03-topological-sort/meta.yaml`
- Create: `tasks/medium-03-topological-sort/prompt.md`
- Create: `tasks/medium-03-topological-sort/requirements.txt`
- Create: `tasks/medium-03-topological-sort/seed/toposort.py`
- Create: `tasks/medium-03-topological-sort/tests/test_toposort.py`

- [ ] **Step 1: Create the fixture files**

`tasks/medium-03-topological-sort/meta.yaml`:
```yaml
id: medium-03-topological-sort
title: Implement topological_sort()
difficulty: medium
category: algorithm
```

`tasks/medium-03-topological-sort/prompt.md`:
```
Implement `topological_sort(dependencies)` in `toposort.py`.
`dependencies` is a dict like `{'b': ['a'], 'c': ['a', 'b']}` mapping each
node to the list of nodes it depends on. Return a list containing every
node exactly once, such that each node appears after all of its
dependencies. Raise `ValueError` if the graph has a cycle. Nodes with no
entry on the left but referenced as a dependency should still appear in
the output.
```

`tasks/medium-03-topological-sort/requirements.txt`:
```
```
(empty file)

`tasks/medium-03-topological-sort/seed/toposort.py`:
```python
def topological_sort(dependencies):
    """Not yet implemented.

    `dependencies` is a dict mapping each node name to a list of node
    names it depends on (must come before it). Should return a list of
    all nodes in a valid dependency order.
    """
    raise NotImplementedError
```

`tasks/medium-03-topological-sort/tests/test_toposort.py`:
```python
import pytest

from toposort import topological_sort


def test_simple_chain():
    order = topological_sort({"b": ["a"], "c": ["b"]})
    assert order.index("a") < order.index("b") < order.index("c")
    assert set(order) == {"a", "b", "c"}


def test_diamond_dependency():
    order = topological_sort({"b": ["a"], "c": ["a"], "d": ["b", "c"]})
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_node_with_no_dependencies_appears():
    assert topological_sort({"a": []}) == ["a"]


def test_cycle_raises_value_error():
    with pytest.raises(ValueError):
        topological_sort({"a": ["b"], "b": ["a"]})
```

- [ ] **Step 2: Verify the hidden tests FAIL against the shipped seed**

```bash
cd tasks/medium-03-topological-sort
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: `4 failed` (all raise `NotImplementedError`)

- [ ] **Step 3: Apply the reference fix temporarily and verify all tests PASS**

Edit `seed/toposort.py` to:
```python
def topological_sort(dependencies):
    all_nodes = set(dependencies)
    for deps in dependencies.values():
        all_nodes.update(deps)

    graph = {node: list(dependencies.get(node, [])) for node in all_nodes}
    visited = {}
    order = []

    def visit(node):
        state = visited.get(node)
        if state == "done":
            return
        if state == "visiting":
            raise ValueError(f"cycle detected at {node!r}")
        visited[node] = "visiting"
        for dep in graph[node]:
            visit(dep)
        visited[node] = "done"
        order.append(node)

    for node in sorted(all_nodes):
        visit(node)

    return order
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `4 passed`

- [ ] **Step 4: Revert the seed back to the shipped version and clean up**

Edit `seed/toposort.py` back to its original Step 1 content, then:
```bash
cd ..            # back to tasks/medium-03-topological-sort
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/medium-03-topological-sort
git commit -m "Add fixture: medium-03-topological-sort"
```

---

### Task 16: Fixture `medium-04-wire-new-validator` (multi-file-reasoning / medium)

**Files:**
- Create: `tasks/medium-04-wire-new-validator/meta.yaml`
- Create: `tasks/medium-04-wire-new-validator/prompt.md`
- Create: `tasks/medium-04-wire-new-validator/requirements.txt`
- Create: `tasks/medium-04-wire-new-validator/seed/pipeline.py`
- Create: `tasks/medium-04-wire-new-validator/seed/validators/__init__.py`
- Create: `tasks/medium-04-wire-new-validator/seed/validators/length.py`
- Create: `tasks/medium-04-wire-new-validator/tests/test_pipeline.py`

- [ ] **Step 1: Create the fixture files**

`tasks/medium-04-wire-new-validator/meta.yaml`:
```yaml
id: medium-04-wire-new-validator
title: Add and wire in a numeric validator
difficulty: medium
category: multi-file-reasoning
```

`tasks/medium-04-wire-new-validator/prompt.md`:
```
Add a new validator in `validators/numeric.py`: `validate_numeric(value)`
returns the string `'not_numeric'` if `value` is not a string of only
digits (use `str.isdigit()`), otherwise returns `None`. Wire it into the
pipeline by adding it to `pipeline.py`'s list of validators (after the
existing length check), so `pipeline.validate(value)` includes
`'not_numeric'` in its result when applicable, alongside the existing
`'too_long'` check.
```

`tasks/medium-04-wire-new-validator/requirements.txt`:
```
```
(empty file)

`tasks/medium-04-wire-new-validator/seed/pipeline.py`:
```python
from validators.length import validate_length

_VALIDATORS = [validate_length]


def validate(value):
    errors = []
    for validator in _VALIDATORS:
        error = validator(value)
        if error:
            errors.append(error)
    return errors
```

`tasks/medium-04-wire-new-validator/seed/validators/__init__.py`:
```python
```
(empty file)

`tasks/medium-04-wire-new-validator/seed/validators/length.py`:
```python
def validate_length(value):
    if len(value) > 20:
        return "too_long"
    return None
```

`tasks/medium-04-wire-new-validator/tests/test_pipeline.py`:
```python
from pipeline import validate


def test_passes_short_numeric_value():
    assert validate("123") == []


def test_flags_non_numeric_value():
    assert validate("abc") == ["not_numeric"]


def test_flags_too_long_value():
    assert validate("1" * 25) == ["too_long"]


def test_flags_both_errors_at_once():
    assert validate("a" * 25) == ["too_long", "not_numeric"]
```

- [ ] **Step 2: Verify the hidden tests FAIL against the shipped seed**

```bash
cd tasks/medium-04-wire-new-validator
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: `2 failed, 2 passed` (`test_flags_non_numeric_value` and `test_flags_both_errors_at_once` fail — there's no numeric validator yet)

- [ ] **Step 3: Apply the reference fix temporarily and verify all tests PASS**

Create `seed/validators/numeric.py`:
```python
def validate_numeric(value):
    if not value.isdigit():
        return "not_numeric"
    return None
```

Edit `seed/pipeline.py` to:
```python
from validators.length import validate_length
from validators.numeric import validate_numeric

_VALIDATORS = [validate_length, validate_numeric]


def validate(value):
    errors = []
    for validator in _VALIDATORS:
        error = validator(value)
        if error:
            errors.append(error)
    return errors
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `4 passed`

- [ ] **Step 4: Revert the seed back to the shipped version and clean up**

Delete `seed/validators/numeric.py` and restore `seed/pipeline.py` to its original Step 1 content, then:
```bash
cd ..            # back to tasks/medium-04-wire-new-validator
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/medium-04-wire-new-validator
git commit -m "Add fixture: medium-04-wire-new-validator"
```

---

### Task 17: Fixture `hard-01-add-rate-limiter` (feature-add / hard)

**Files:**
- Create: `tasks/hard-01-add-rate-limiter/meta.yaml`
- Create: `tasks/hard-01-add-rate-limiter/prompt.md`
- Create: `tasks/hard-01-add-rate-limiter/requirements.txt`
- Create: `tasks/hard-01-add-rate-limiter/seed/rate_limiter.py`
- Create: `tasks/hard-01-add-rate-limiter/tests/test_rate_limiter.py`

- [ ] **Step 1: Create the fixture files**

`tasks/hard-01-add-rate-limiter/meta.yaml`:
```yaml
id: hard-01-add-rate-limiter
title: Implement a token-bucket rate limiter
difficulty: hard
category: feature-add
```

`tasks/hard-01-add-rate-limiter/prompt.md`:
```
Implement a token-bucket rate limiter in `rate_limiter.py`.
`TokenBucketRateLimiter(capacity, refill_rate_per_second, clock=None)`
starts with a full bucket of `capacity` tokens. Each call to `allow()`
should: refill the bucket based on elapsed time since the last refill
(`refill_rate_per_second` tokens per second, capped at `capacity`), then,
if at least 1 token is available, consume one token and return `True`;
otherwise return `False` without consuming a token. `clock` is an
injectable zero-argument callable returning the current time (for
testability) — default to `time.time`. The constructor should call
`clock()` once to initialize the last-refill timestamp.
```

`tasks/hard-01-add-rate-limiter/requirements.txt`:
```
```
(empty file)

`tasks/hard-01-add-rate-limiter/seed/rate_limiter.py`:
```python
import time


class TokenBucketRateLimiter:
    """Token-bucket rate limiter.

    Not yet implemented: `allow()` should always return True until the
    real implementation is written.
    """

    def __init__(self, capacity, refill_rate_per_second, clock=None):
        self.capacity = capacity
        self.refill_rate_per_second = refill_rate_per_second
        self._clock = clock or time.time

    def allow(self):
        return True
```

`tasks/hard-01-add-rate-limiter/tests/test_rate_limiter.py`:
```python
from rate_limiter import TokenBucketRateLimiter


def make_clock(times):
    it = iter(times)
    return lambda: next(it)


def test_allows_up_to_capacity_then_denies():
    limiter = TokenBucketRateLimiter(capacity=2, refill_rate_per_second=1, clock=make_clock([0, 0, 0, 0]))
    assert limiter.allow() is True
    assert limiter.allow() is True
    assert limiter.allow() is False


def test_refills_over_time():
    limiter = TokenBucketRateLimiter(capacity=1, refill_rate_per_second=1, clock=make_clock([0, 0, 0, 2]))
    assert limiter.allow() is True
    assert limiter.allow() is False
    assert limiter.allow() is True


def test_refill_is_capped_at_capacity():
    limiter = TokenBucketRateLimiter(capacity=3, refill_rate_per_second=1, clock=make_clock([0, 0, 100, 100]))
    assert limiter.allow() is True
    assert limiter.allow() is True
    assert limiter.allow() is True
```

- [ ] **Step 2: Verify the hidden tests FAIL against the shipped seed**

```bash
cd tasks/hard-01-add-rate-limiter
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: `2 failed, 1 passed` (`test_allows_up_to_capacity_then_denies` and `test_refills_over_time` both fail because the stub never denies; `test_refill_is_capped_at_capacity`'s three assertions are all `True` so it passes trivially against the stub)

- [ ] **Step 3: Apply the reference fix temporarily and verify all tests PASS**

Edit `seed/rate_limiter.py` to:
```python
import time


class TokenBucketRateLimiter:
    def __init__(self, capacity, refill_rate_per_second, clock=None):
        self.capacity = capacity
        self.refill_rate_per_second = refill_rate_per_second
        self._clock = clock or time.time
        self._tokens = capacity
        self._last_refill = self._clock()

    def allow(self):
        now = self._clock()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate_per_second)
        self._last_refill = now
        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `3 passed`

- [ ] **Step 4: Revert the seed back to the shipped version and clean up**

Edit `seed/rate_limiter.py` back to its original Step 1 content, then:
```bash
cd ..            # back to tasks/hard-01-add-rate-limiter
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/hard-01-add-rate-limiter
git commit -m "Add fixture: hard-01-add-rate-limiter"
```

---

### Task 18: Fixture `hard-02-extract-order-service` (refactor / hard)

**Files:**
- Create: `tasks/hard-02-extract-order-service/meta.yaml`
- Create: `tasks/hard-02-extract-order-service/prompt.md`
- Create: `tasks/hard-02-extract-order-service/requirements.txt`
- Create: `tasks/hard-02-extract-order-service/seed/inventory.py`
- Create: `tasks/hard-02-extract-order-service/seed/order.py`
- Create: `tasks/hard-02-extract-order-service/tests/test_order.py`

- [ ] **Step 1: Create the fixture files**

`tasks/hard-02-extract-order-service/meta.yaml`:
```yaml
id: hard-02-extract-order-service
title: Separate validation/stock/recording concerns across two files
difficulty: hard
category: refactor
```

`tasks/hard-02-extract-order-service/prompt.md`:
```
`order.py` and `inventory.py` mix validation, stock management, and order
recording together inside `place_order`. Refactor so each concern is a
clearly separated function (e.g. a validation step, a stock-check/reduce
step, a record step), keeping `place_order(item, qty, customer_email)`
and `order_count()` in `order.py` as the only functions other code calls,
with unchanged behavior for: invalid email (no '@'), non-positive
quantity, insufficient stock, and the success path.
```

`tasks/hard-02-extract-order-service/requirements.txt`:
```
```
(empty file)

`tasks/hard-02-extract-order-service/seed/inventory.py`:
```python
_STOCK = {"widget": 5, "gadget": 0, "gizmo": 10}


def has_stock(item, qty):
    return _STOCK.get(item, 0) >= qty


def reduce_stock(item, qty):
    _STOCK[item] = _STOCK.get(item, 0) - qty
```

`tasks/hard-02-extract-order-service/seed/order.py`:
```python
from inventory import has_stock, reduce_stock

_ORDERS = []


def place_order(item, qty, customer_email):
    if "@" not in customer_email:
        return {"ok": False, "reason": "invalid_email"}
    if qty <= 0:
        return {"ok": False, "reason": "invalid_quantity"}
    if not has_stock(item, qty):
        return {"ok": False, "reason": "out_of_stock"}
    reduce_stock(item, qty)
    order = {"item": item, "qty": qty, "customer_email": customer_email}
    _ORDERS.append(order)
    return {"ok": True, "order": order}


def order_count():
    return len(_ORDERS)
```

`tasks/hard-02-extract-order-service/tests/test_order.py`:
```python
import inventory
import order


def test_successful_order_reduces_stock_and_is_recorded():
    before = order.order_count()
    result = order.place_order("widget", 2, "a@example.com")
    assert result == {"ok": True, "order": {"item": "widget", "qty": 2, "customer_email": "a@example.com"}}
    assert inventory.has_stock("widget", 4) is False
    assert order.order_count() == before + 1


def test_rejects_invalid_email():
    before = order.order_count()
    result = order.place_order("gizmo", 1, "not-an-email")
    assert result == {"ok": False, "reason": "invalid_email"}
    assert order.order_count() == before


def test_rejects_non_positive_quantity():
    before = order.order_count()
    result = order.place_order("gizmo", 0, "a@example.com")
    assert result == {"ok": False, "reason": "invalid_quantity"}
    assert order.order_count() == before


def test_rejects_when_out_of_stock():
    before = order.order_count()
    result = order.place_order("gadget", 1, "a@example.com")
    assert result == {"ok": False, "reason": "out_of_stock"}
    assert order.order_count() == before
```

- [ ] **Step 2: Verify the hidden tests PASS against the shipped seed**

This is a refactor task — the seed is already behaviorally correct, so the check is that the suite passes before refactoring, proving it correctly pins current behavior:
```bash
cd tasks/hard-02-extract-order-service
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: `4 passed`

- [ ] **Step 3: Verify a refactored version still passes (behavior-preservation check)**

Temporarily replace `seed/inventory.py` and `seed/order.py` with a separated-concerns version:

`seed/inventory.py`:
```python
_STOCK = {"widget": 5, "gadget": 0, "gizmo": 10}


def has_stock(item, qty):
    return _STOCK.get(item, 0) >= qty


def reduce_stock(item, qty):
    _STOCK[item] = _STOCK.get(item, 0) - qty
```
(unchanged — already single-purpose)

`seed/order.py`:
```python
from inventory import has_stock, reduce_stock

_ORDERS = []


def _validate(qty, customer_email):
    if "@" not in customer_email:
        return "invalid_email"
    if qty <= 0:
        return "invalid_quantity"
    return None


def _reserve_stock(item, qty):
    if not has_stock(item, qty):
        return "out_of_stock"
    reduce_stock(item, qty)
    return None


def _record(item, qty, customer_email):
    order = {"item": item, "qty": qty, "customer_email": customer_email}
    _ORDERS.append(order)
    return order


def place_order(item, qty, customer_email):
    validation_error = _validate(qty, customer_email)
    if validation_error:
        return {"ok": False, "reason": validation_error}
    stock_error = _reserve_stock(item, qty)
    if stock_error:
        return {"ok": False, "reason": stock_error}
    order = _record(item, qty, customer_email)
    return {"ok": True, "order": order}


def order_count():
    return len(_ORDERS)
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `4 passed`

- [ ] **Step 4: Revert the seed back to the original tangled version and clean up**

Edit `seed/order.py` back to its original Step 1 content (`seed/inventory.py` was unchanged), then:
```bash
cd ..            # back to tasks/hard-02-extract-order-service
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/hard-02-extract-order-service
git commit -m "Add fixture: hard-02-extract-order-service"
```

---

### Task 19: Fixture `hard-03-lru-cache` (algorithm / hard)

**Files:**
- Create: `tasks/hard-03-lru-cache/meta.yaml`
- Create: `tasks/hard-03-lru-cache/prompt.md`
- Create: `tasks/hard-03-lru-cache/requirements.txt`
- Create: `tasks/hard-03-lru-cache/seed/lru.py`
- Create: `tasks/hard-03-lru-cache/tests/test_lru.py`

- [ ] **Step 1: Create the fixture files**

`tasks/hard-03-lru-cache/meta.yaml`:
```yaml
id: hard-03-lru-cache
title: Implement a fixed-capacity LRU cache
difficulty: hard
category: algorithm
```

`tasks/hard-03-lru-cache/prompt.md`:
```
Implement `LRUCache` in `lru.py` with `get(key)` and `put(key, value)` as
described in the class docstring: fixed capacity, correct
least-recently-used eviction (a dict plus a way to track recency order is
the natural approach). `capacity` is always a positive integer.
```

`tasks/hard-03-lru-cache/requirements.txt`:
```
```
(empty file)

`tasks/hard-03-lru-cache/seed/lru.py`:
```python
class LRUCache:
    """Fixed-capacity cache. Not yet implemented.

    `get(key)` returns the value or None if absent, and marks it as
    most-recently-used. `put(key, value)` inserts/updates a value,
    evicting the least-recently-used entry if capacity is exceeded.
    """

    def __init__(self, capacity):
        self.capacity = capacity

    def get(self, key):
        raise NotImplementedError

    def put(self, key, value):
        raise NotImplementedError
```

`tasks/hard-03-lru-cache/tests/test_lru.py`:
```python
from lru import LRUCache


def test_get_missing_key_returns_none():
    cache = LRUCache(2)
    assert cache.get("x") is None


def test_put_and_get_roundtrip():
    cache = LRUCache(2)
    cache.put("a", 1)
    assert cache.get("a") == 1


def test_evicts_least_recently_used():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_get_refreshes_recency():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")
    cache.put("c", 3)
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_put_on_existing_key_updates_value_and_recency():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 10)
    cache.put("c", 3)
    assert cache.get("a") == 10
    assert cache.get("b") is None
```

- [ ] **Step 2: Verify the hidden tests FAIL against the shipped seed**

```bash
cd tasks/hard-03-lru-cache
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: `5 failed` (every test calls `get`/`put`, and both unconditionally raise `NotImplementedError` in the stub — nothing can pass until implemented)

- [ ] **Step 3: Apply the reference fix temporarily and verify all tests PASS**

Edit `seed/lru.py` to:
```python
class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self._store = {}
        self._order = []

    def get(self, key):
        if key not in self._store:
            return None
        self._order.remove(key)
        self._order.append(key)
        return self._store[key]

    def put(self, key, value):
        if key in self._store:
            self._order.remove(key)
        elif len(self._store) >= self.capacity:
            lru_key = self._order.pop(0)
            del self._store[lru_key]
        self._store[key] = value
        self._order.append(key)
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `5 passed`

- [ ] **Step 4: Revert the seed back to the shipped version and clean up**

Edit `seed/lru.py` back to its original Step 1 content, then:
```bash
cd ..            # back to tasks/hard-03-lru-cache
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/hard-03-lru-cache
git commit -m "Add fixture: hard-03-lru-cache"
```

---

### Task 20: Fixture `hard-04-index-batch-lookup` (perf-optimization / hard)

**Files:**
- Create: `tasks/hard-04-index-batch-lookup/meta.yaml`
- Create: `tasks/hard-04-index-batch-lookup/prompt.md`
- Create: `tasks/hard-04-index-batch-lookup/requirements.txt`
- Create: `tasks/hard-04-index-batch-lookup/seed/lookup.py`
- Create: `tasks/hard-04-index-batch-lookup/tests/test_lookup.py`

- [ ] **Step 1: Create the fixture files**

`tasks/hard-04-index-batch-lookup/meta.yaml`:
```yaml
id: hard-04-index-batch-lookup
title: Replace O(n*m) price lookup with an index
difficulty: hard
category: perf-optimization
```

`tasks/hard-04-index-batch-lookup/prompt.md`:
```
`annotate_with_prices` in `lookup.py` is correct but slow for large
inputs — it does a full linear scan over `price_list` for every single
order (O(orders x price_list)). Rewrite it to build a single
`item -> price` lookup dict once, then use it for O(1) lookups per
order. Keep behavior identical: unmatched items get `'price': None`, the
input lists must not be mutated, and output order matches `orders`.
```

`tasks/hard-04-index-batch-lookup/requirements.txt`:
```
```
(empty file)

`tasks/hard-04-index-batch-lookup/seed/lookup.py`:
```python
def annotate_with_prices(orders, price_list):
    """orders: list of dicts with an 'item' key.
    price_list: list of dicts with 'item' and 'price' keys.
    Returns a new list of orders, each with a 'price' key added
    (None if the item isn't found in price_list).
    """
    result = []
    for order in orders:
        price = None
        for entry in price_list:
            if entry["item"] == order["item"]:
                price = entry["price"]
                break
        result.append({**order, "price": price})
    return result
```

`tasks/hard-04-index-batch-lookup/tests/test_lookup.py`:
```python
import time

from lookup import annotate_with_prices


def test_matches_known_items():
    orders = [{"item": "a"}, {"item": "b"}]
    prices = [{"item": "a", "price": 10}, {"item": "b", "price": 20}]
    assert annotate_with_prices(orders, prices) == [
        {"item": "a", "price": 10},
        {"item": "b", "price": 20},
    ]


def test_unmatched_item_gets_none():
    orders = [{"item": "z"}]
    prices = [{"item": "a", "price": 10}]
    assert annotate_with_prices(orders, prices) == [{"item": "z", "price": None}]


def test_does_not_mutate_inputs():
    orders = [{"item": "a"}]
    prices = [{"item": "a", "price": 10}]
    orders_copy = [dict(o) for o in orders]
    prices_copy = [dict(p) for p in prices]

    annotate_with_prices(orders, prices)

    assert orders == orders_copy
    assert prices == prices_copy


def test_runs_fast_on_large_input():
    prices = [{"item": f"item-{i}", "price": i} for i in range(5000)]
    orders = [{"item": f"item-{i % 5000}"} for i in range(5000)]
    start = time.perf_counter()
    result = annotate_with_prices(orders, prices)
    elapsed = time.perf_counter() - start

    assert len(result) == 5000
    assert result[0]["price"] == 0
    assert elapsed < 2.0
```

- [ ] **Step 2: Verify the hidden tests against the shipped seed**

```bash
cd tasks/hard-04-index-batch-lookup
uv venv seed/.check-venv
uv pip install --python seed/.check-venv/bin/python pytest -r requirements.txt
cp -r tests seed/tests
cd seed
PYTHONPATH=. .check-venv/bin/pytest tests -q
```
Expected: `test_matches_known_items`, `test_unmatched_item_gets_none`, and `test_does_not_mutate_inputs` PASS regardless (the O(n*m) version is still correct). `test_runs_fast_on_large_input` may pass or fail on the seed depending on hardware (5000x5000 = 25M comparisons is near the 2.0s budget) — either is fine here: correctness is this fixture's hard gate, the timing bound is a secondary nudge toward the intended optimization, not something this verification step needs to force one way or the other.

- [ ] **Step 3: Apply the reference fix temporarily and verify all tests PASS comfortably**

Edit `seed/lookup.py` to:
```python
def annotate_with_prices(orders, price_list):
    price_by_item = {entry["item"]: entry["price"] for entry in price_list}
    return [{**order, "price": price_by_item.get(order["item"])} for order in orders]
```

Run: `PYTHONPATH=. .check-venv/bin/pytest tests -q` (from `seed/`)
Expected: `4 passed`, with `test_runs_fast_on_large_input` now comfortably fast.

- [ ] **Step 4: Revert the seed back to the shipped version and clean up**

Edit `seed/lookup.py` back to its original Step 1 content, then:
```bash
cd ..            # back to tasks/hard-04-index-batch-lookup
rm -rf seed/tests seed/.check-venv
```

- [ ] **Step 5: Commit**

```bash
git add tasks/hard-04-index-batch-lookup
git commit -m "Add fixture: hard-04-index-batch-lookup"
```

---

## Part C — End-to-end verification

### Task 21: Manual smoke-test runbook (not automated — costs real Claude Code invocations)

**Files:**
- None created; this task is a manual verification pass using the CLIs built in Tasks 7-8 against the real `claude` CLI, to confirm the whole pipeline works before trusting a full 12x3x4 run.

- [ ] **Step 1: Confirm the full fixture set is discovered**

Run: `uv run python -c "from harness.run import discover_tasks; print(len(discover_tasks()))"`
Expected: `12`

- [ ] **Step 2: Run one cheap single-task, single-repeat smoke test against the currently active environment**

Run:
```bash
uv run python harness/run.py --env smoke-test --task easy-01-fix-average --repeats 1
```
Expected: prints `[smoke-test] easy-01-fix-average repeat 1/1...` followed by `-> pass=True cost=$0.0XXX` (pass should be `True` if Claude Code correctly fixes the bug; investigate `results/smoke-test.jsonl`'s row if not). This single call also validates: `uv venv`/`uv pip install` work from Python's `subprocess`, `claude -p ... --output-format json` parses correctly end-to-end, and the hidden-test overlay + scoring works.

- [ ] **Step 3: Inspect the recorded row**

Run: `cat results/smoke-test.jsonl`
Expected: one JSON line with all the fields from the Task 6 schema populated (non-null `total_cost_usd`, `model`, `claude_code_version` matching the locally installed Claude Code version).

- [ ] **Step 4: Generate the report from just the smoke-test data and confirm it renders**

Run: `uv run python harness/report.py`
Expected: a markdown table printed to stdout containing `easy-01-fix-average`, and `reports/dashboard.html` written and openable in a browser.

- [ ] **Step 5: Remove the smoke-test results so they don't pollute the real comparison**

```bash
rm results/smoke-test.jsonl
```

- [ ] **Step 6: Run the real benchmark once per environment**

In each of the 4 already-configured shells (per `.zshrc`), run:
```bash
uv run python harness/run.py --env personal-sub
uv run python harness/run.py --env personal-api
uv run python harness/run.py --env work-sub
uv run python harness/run.py --env work-api
```
Each is 12 tasks x 3 repeats = 36 Claude Code invocations. Then from any one checkout with all 4 `results/*.jsonl` files present (copy them over if the environments ran on different machines):
```bash
uv run python harness/report.py
```
Expected: a comparison table covering all 4 environments, and `reports/dashboard.html` reflecting the full run. Review the "Warnings" section for any model/version drift before drawing conclusions from the cost/performance comparison.

- [ ] **Step 7: Commit the real results**

```bash
git add results/*.jsonl
git commit -m "Add first full 4-environment benchmark run"
```
