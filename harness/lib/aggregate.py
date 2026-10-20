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
        ok_rows = [r for r in group if not r.get("harness_error")]
        errors = sum(1 for r in group if r.get("harness_error"))
        costs = [r["total_cost_usd"] for r in ok_rows]
        durations = [r["duration_ms"] for r in ok_rows]
        tokens = [r["input_tokens"] + r["output_tokens"] for r in ok_rows]
        entries.append(
            {
                "env": env,
                "task_id": task_id,
                "runs": len(group),
                "passes": passes,
                "errors": errors,
                "pass_rate": passes / len(group),
                "median_cost_usd": statistics.median(costs) if costs else None,
                "median_duration_ms": statistics.median(durations) if durations else None,
                "median_total_tokens": statistics.median(tokens) if tokens else None,
            }
        )

    by_task_env: dict[tuple[str, str], dict[str, set]] = {}
    for row in rows:
        if row.get("harness_error"):
            continue
        key = (row["task_id"], row["env"])
        bucket = by_task_env.setdefault(key, {"models": set(), "versions": set()})
        bucket["models"].add(row["model"])
        bucket["versions"].add(row["claude_code_version"])

    by_task: dict[str, dict[str, dict]] = {}
    for (task_id, env), bucket in by_task_env.items():
        by_task.setdefault(task_id, {})[env] = bucket

    warnings = []
    for task_id in sorted(by_task):
        env_buckets = by_task[task_id]
        model_sets_by_env = {env: b["models"] for env, b in env_buckets.items()}
        version_sets_by_env = {env: b["versions"] for env, b in env_buckets.items()}

        if len({frozenset(s) for s in model_sets_by_env.values()}) > 1:
            detail = ", ".join(f"{env}={sorted(models)}" for env, models in sorted(model_sets_by_env.items()))
            warnings.append(f"{task_id}: multiple models observed across environments: {detail}")

        if len({frozenset(s) for s in version_sets_by_env.values()}) > 1:
            detail = ", ".join(f"{env}={sorted(versions)}" for env, versions in sorted(version_sets_by_env.items()))
            warnings.append(f"{task_id}: claude_code_version differs across environments: {detail}")

    by_env: dict[str, list[dict]] = {}
    for row in rows:
        by_env.setdefault(row["env"], []).append(row)

    rollup = []
    for env, env_rows in sorted(by_env.items()):
        passes = sum(1 for r in env_rows if r["pass"])
        ok_rows = [r for r in env_rows if not r.get("harness_error")]
        errors = sum(1 for r in env_rows if r.get("harness_error"))
        costs = [r["total_cost_usd"] for r in ok_rows]
        durations = [r["duration_ms"] for r in ok_rows]
        tokens = [r["input_tokens"] + r["output_tokens"] for r in ok_rows]
        rollup.append(
            {
                "env": env,
                "runs": len(env_rows),
                "passes": passes,
                "errors": errors,
                "pass_rate": passes / len(env_rows),
                "median_cost_usd": statistics.median(costs) if costs else None,
                "median_duration_ms": statistics.median(durations) if durations else None,
                "median_total_tokens": statistics.median(tokens) if tokens else None,
            }
        )

    return {"entries": entries, "warnings": warnings, "rollup": rollup}
