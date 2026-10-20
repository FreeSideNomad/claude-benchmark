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
