import subprocess
from unittest.mock import patch

from harness.lib.scorer import overlay_tests, run_pytest, score_task


def test_overlay_tests_copies_files(tmp_path):
    task_dir = tmp_path / "task"
    work_dir = tmp_path / "work"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test_x.py").write_text("def test_x(): pass\n")
    work_dir.mkdir()

    overlay_tests(task_dir, work_dir)

    assert (work_dir / "tests" / "test_x.py").read_text() == "def test_x(): pass\n"


def test_overlay_tests_replaces_existing_tests_dir(tmp_path):
    task_dir = tmp_path / "task"
    work_dir = tmp_path / "work"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test_new.py").write_text("def test_new(): pass\n")
    (work_dir / "tests").mkdir(parents=True)
    (work_dir / "tests" / "stale.py").write_text("stale\n")

    overlay_tests(task_dir, work_dir)

    assert not (work_dir / "tests" / "stale.py").exists()
    assert (work_dir / "tests" / "test_new.py").exists()


def test_run_pytest_returns_true_on_success(tmp_path):
    completed = subprocess.CompletedProcess(args=[], returncode=0)
    with patch("harness.lib.scorer.subprocess.run", return_value=completed):
        assert run_pytest(tmp_path) is True


def test_run_pytest_returns_false_on_failure(tmp_path):
    completed = subprocess.CompletedProcess(args=[], returncode=1)
    with patch("harness.lib.scorer.subprocess.run", return_value=completed):
        assert run_pytest(tmp_path) is False


def test_score_task_overlays_then_runs(tmp_path):
    task_dir = tmp_path / "task"
    work_dir = tmp_path / "work"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test_x.py").write_text("def test_x(): pass\n")
    work_dir.mkdir()

    with patch("harness.lib.scorer.run_pytest", return_value=True) as mock_run_pytest:
        assert score_task(task_dir, work_dir) is True

    mock_run_pytest.assert_called_once_with(work_dir)
    assert (work_dir / "tests" / "test_x.py").exists()
