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
