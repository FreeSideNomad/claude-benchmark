import json
import subprocess
from unittest.mock import patch

from harness.lib.claude_runner import VERSION_TIMEOUT_SECONDS, get_claude_version, run_claude

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
    mock_run.assert_called_once_with(
        ["claude", "--version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=VERSION_TIMEOUT_SECONDS,
    )


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
