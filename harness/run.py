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


def _error_row(task_dir: Path, env: str, repeat: int, error: Exception) -> dict:
    return {
        "env": env,
        "task_id": task_dir.name,
        "repeat": repeat,
        "pass": False,
        "is_error": True,
        "error": str(error),
        "total_cost_usd": None,
        "duration_ms": None,
        "num_turns": None,
        "input_tokens": None,
        "output_tokens": None,
        "cache_creation_input_tokens": None,
        "cache_read_input_tokens": None,
        "model": None,
        "claude_code_version": None,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def execute_task_repeat_safe(task_dir: Path, env: str, repeat: int) -> dict:
    try:
        return execute_task_repeat(task_dir, env, repeat)
    except Exception as exc:
        return _error_row(task_dir, env, repeat, exc)


def run(env: str, task_filter: str | None = None, repeats: int = REPEATS) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / f"{env}.jsonl"

    already_done = set()
    if results_path.exists():
        with open(results_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    existing = json.loads(line)
                    already_done.add((existing["task_id"], existing["repeat"]))

    tasks = discover_tasks(TASKS_DIR)
    if task_filter:
        tasks = [t for t in tasks if t.name == task_filter]
        if not tasks:
            raise SystemExit(f"No task found matching --task {task_filter!r}")

    for task_dir in tasks:
        for repeat in range(1, repeats + 1):
            if (task_dir.name, repeat) in already_done:
                print(f"[{env}] {task_dir.name} repeat {repeat}/{repeats} already done, skipping")
                continue
            print(f"[{env}] {task_dir.name} repeat {repeat}/{repeats}...")
            row = execute_task_repeat_safe(task_dir, env, repeat)
            with open(results_path, "a") as f:
                f.write(json.dumps(row) + "\n")
            if row.get("is_error"):
                print(f"  -> ERROR: {row['error']}")
            else:
                print(f"  -> pass={row['pass']} cost=${row['total_cost_usd']:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    parser.add_argument("--task", help="Only run this single task_id (for smoke-testing)")
    parser.add_argument("--repeats", type=int, default=REPEATS, help="Override repeats per task")
    args = parser.parse_args()
    run(args.env, task_filter=args.task, repeats=args.repeats)
