from unittest.mock import patch

from harness.run import discover_tasks, execute_task_repeat


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
    assert mock_run_claude.call_args.args[0] == "fix the bug"
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
