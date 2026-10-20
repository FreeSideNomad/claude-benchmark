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
