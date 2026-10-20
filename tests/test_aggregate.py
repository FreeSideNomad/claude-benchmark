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


def test_summarize_does_not_flag_drift_for_intra_environment_model_variance():
    rows = [
        _row(env="personal-sub", repeat=1, model="claude-sonnet-5"),
        _row(env="personal-sub", repeat=2, model="claude-haiku-4-5,claude-sonnet-5"),
    ]
    summary = summarize(rows)
    assert summary["warnings"] == []


def test_summarize_computes_overall_rollup_per_environment():
    rows = [
        _row(env="personal-sub", task_id="easy-01", repeat=1, total_cost_usd=0.01, duration_ms=1000, **{"pass": True}),
        _row(env="personal-sub", task_id="medium-01", repeat=1, total_cost_usd=0.03, duration_ms=3000, **{"pass": False}),
    ]
    summary = summarize(rows)
    assert len(summary["rollup"]) == 1
    rollup = summary["rollup"][0]
    assert rollup["env"] == "personal-sub"
    assert rollup["runs"] == 2
    assert rollup["passes"] == 1
