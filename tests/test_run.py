import json
from unittest.mock import patch

from harness.run import discover_tasks, execute_task_repeat, execute_task_repeat_safe


def test_discover_tasks_finds_only_task_dirs(tmp_path):
    (tmp_path / "easy-01").mkdir()
    (tmp_path / "easy-01" / "meta.yaml").write_text("id: easy-01\n")
    (tmp_path / "not_a_task").mkdir()
    (tmp_path / "stray_file.txt").write_text("x")

    tasks = discover_tasks(tmp_path)

    assert [t.name for t in tasks] == ["easy-01"]


def _fake_result():
    return {
        "is_error": False,
        "total_cost_usd": 0.05,
        "duration_ms": 1000,
        "num_turns": 2,
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "model": "claude-sonnet-5",
    }


def _make_task_dir(tmp_path):
    task_dir = tmp_path / "easy-01"
    task_dir.mkdir()
    (task_dir / "prompt.md").write_text("fix the bug")
    (task_dir / "seed").mkdir()
    (task_dir / "requirements.txt").write_text("")
    return task_dir


def test_execute_task_repeat_wires_lib_calls_and_returns_row(tmp_path):
    task_dir = _make_task_dir(tmp_path)

    with patch("harness.run.worktree.create_worktree") as mock_create, \
         patch("harness.run.worktree.remove_worktree") as mock_remove, \
         patch("harness.run.env_setup.create_venv") as mock_venv, \
         patch("harness.run.env_setup.install_requirements") as mock_install, \
         patch("harness.run.claude_runner.get_claude_version", return_value="2.1.233") as mock_version, \
         patch("harness.run.claude_runner.run_claude", return_value=_fake_result()) as mock_run_claude, \
         patch("harness.run.scorer.score_task", return_value=True) as mock_score:
        row = execute_task_repeat(task_dir, env="personal-sub", repeat=1)

    # Capture work_dir from the first mock call to establish internal consistency
    work_dir = mock_create.call_args.args[1]

    # Assert all lib calls received correct arguments
    mock_create.assert_called_once_with(task_dir / "seed", work_dir)
    mock_venv.assert_called_once_with(work_dir)
    mock_install.assert_called_once_with(work_dir, task_dir / "requirements.txt")
    mock_version.assert_called_once()
    mock_run_claude.assert_called_once_with("fix the bug", cwd=work_dir)
    mock_score.assert_called_once_with(task_dir, work_dir)
    mock_remove.assert_called_once_with(work_dir.parent)

    # Assert row contents
    assert row["env"] == "personal-sub"
    assert row["task_id"] == "easy-01"
    assert row["repeat"] == 1
    assert row["pass"] is True
    assert row["total_cost_usd"] == 0.05
    assert row["claude_code_version"] == "2.1.233"
    assert "timestamp" in row


def test_execute_task_repeat_removes_worktree_even_if_scoring_fails(tmp_path):
    task_dir = _make_task_dir(tmp_path)

    with patch("harness.run.worktree.create_worktree") as mock_create, \
         patch("harness.run.worktree.remove_worktree") as mock_remove, \
         patch("harness.run.env_setup.create_venv"), \
         patch("harness.run.env_setup.install_requirements"), \
         patch("harness.run.claude_runner.get_claude_version", return_value="2.1.233"), \
         patch("harness.run.claude_runner.run_claude", return_value=_fake_result()), \
         patch("harness.run.scorer.score_task", side_effect=RuntimeError("boom")):
        try:
            execute_task_repeat(task_dir, env="personal-sub", repeat=1)
        except RuntimeError:
            pass

    # Capture work_dir to verify cleanup targets the correct directory
    work_dir = mock_create.call_args.args[1]
    mock_remove.assert_called_once_with(work_dir.parent)


def test_execute_task_repeat_safe_converts_exception_to_error_row(tmp_path):
    task_dir = _make_task_dir(tmp_path)

    with patch("harness.run.worktree.create_worktree"), \
         patch("harness.run.worktree.remove_worktree"), \
         patch("harness.run.env_setup.create_venv"), \
         patch("harness.run.env_setup.install_requirements"), \
         patch("harness.run.claude_runner.get_claude_version", return_value="2.1.233"), \
         patch("harness.run.claude_runner.run_claude", side_effect=RuntimeError("boom")):
        row = execute_task_repeat_safe(task_dir, env="personal-sub", repeat=1)

    assert row["harness_error"] is True
    assert row["is_error"] is None
    assert row["pass"] is False
    assert row["error"] == "boom"
    assert row["env"] == "personal-sub"
    assert row["task_id"] == "easy-01"
    assert row["repeat"] == 1


def test_run_skips_already_completed_repeats(tmp_path, monkeypatch):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    task_dir = _make_task_dir(tasks_dir)
    # meta.yaml must exist for discover_tasks to find it
    (task_dir / "meta.yaml").write_text("id: easy-01\n")

    results_dir = tmp_path / "results"
    results_dir.mkdir()
    existing_row = {
        "env": "personal-sub", "task_id": "easy-01", "repeat": 1, "pass": True,
        "is_error": False, "total_cost_usd": 0.01, "input_tokens": 1, "output_tokens": 1,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
        "duration_ms": 100, "num_turns": 1, "model": "claude-sonnet-5",
        "claude_code_version": "2.1.233", "timestamp": "2026-10-20T00:00:00Z",
    }
    (results_dir / "personal-sub.jsonl").write_text(json.dumps(existing_row) + "\n")

    import harness.run as run_module
    monkeypatch.setattr(run_module, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(run_module, "RESULTS_DIR", results_dir)

    fake_row = {**existing_row, "repeat": 2}
    with patch("harness.run.execute_task_repeat_safe", return_value=fake_row) as mock_exec:
        run_module.run("personal-sub", repeats=2)

    # repeat 1 was already done, so only repeat 2 should have been executed
    assert mock_exec.call_count == 1
    assert mock_exec.call_args.args[2] == 2  # repeat number
