from __future__ import annotations

import argparse
import html
from pathlib import Path

from harness.lib.aggregate import load_results, summarize

REPO_ROOT = Path(__file__).resolve().parent.parent


def _fmt_cost(v):
    return f"${v:.4f}" if v is not None else "N/A"


def _fmt_num(v):
    return f"{v:.0f}" if v is not None else "N/A"


def render_markdown_table(summary: dict) -> str:
    lines = [
        "| env | task_id | pass_rate | median_cost_usd | median_duration_ms | median_total_tokens |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for e in summary["entries"]:
        lines.append(
            f"| {e['env']} | {e['task_id']} | {e['passes']}/{e['runs']} "
            f"| {_fmt_cost(e['median_cost_usd'])} | {_fmt_num(e['median_duration_ms'])} | {_fmt_num(e['median_total_tokens'])} |"
        )

    lines.append("")
    lines.append("## Overall per-environment rollup")
    lines.append("")
    lines.append("| env | pass_rate | median_cost_usd | median_duration_ms | median_total_tokens |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in summary["rollup"]:
        lines.append(
            f"| {r['env']} | {r['passes']}/{r['runs']} "
            f"| {_fmt_cost(r['median_cost_usd'])} | {_fmt_num(r['median_duration_ms'])} | {_fmt_num(r['median_total_tokens'])} |"
        )

    if summary["warnings"]:
        lines.append("")
        lines.append("**Warnings:**")
        for w in summary["warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines)


def render_html_dashboard(summary: dict) -> str:
    rows_html = "\n".join(
        f"<tr><td>{html.escape(e['env'])}</td><td>{html.escape(e['task_id'])}</td>"
        f"<td>{e['passes']}/{e['runs']}</td>"
        f"<td>{_fmt_cost(e['median_cost_usd'])}</td>"
        f"<td>{_fmt_num(e['median_duration_ms'])}</td>"
        f"<td>{_fmt_num(e['median_total_tokens'])}</td></tr>"
        for e in summary["entries"]
    )
    rollup_rows_html = "\n".join(
        f"<tr><td>{html.escape(r['env'])}</td>"
        f"<td>{r['passes']}/{r['runs']}</td>"
        f"<td>{_fmt_cost(r['median_cost_usd'])}</td>"
        f"<td>{_fmt_num(r['median_duration_ms'])}</td>"
        f"<td>{_fmt_num(r['median_total_tokens'])}</td></tr>"
        for r in summary["rollup"]
    )
    warnings_section = ""
    if summary["warnings"]:
        warnings_html = "".join(f"<li>{html.escape(w)}</li>" for w in summary["warnings"])
        warnings_section = f"<h2>Warnings</h2>\n<ul>{warnings_html}</ul>"

    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Claude benchmark results</title>
<style>
table {{ border-collapse: collapse; font-family: sans-serif; margin-bottom: 24px; }}
td, th {{ border: 1px solid #ccc; padding: 4px 8px; }}
</style>
</head>
<body>
<h1>Claude benchmark results</h1>
<table>
<tr><th>env</th><th>task_id</th><th>pass rate</th><th>median cost (USD)</th><th>median duration (ms)</th><th>median tokens</th></tr>
{rows_html}
</table>
<h2>Overall per-environment rollup</h2>
<table>
<tr><th>env</th><th>pass rate</th><th>median cost (USD)</th><th>median duration (ms)</th><th>median tokens</th></tr>
{rollup_rows_html}
</table>
{warnings_section}
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
