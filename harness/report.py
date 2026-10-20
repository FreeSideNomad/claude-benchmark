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
