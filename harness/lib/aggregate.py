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
