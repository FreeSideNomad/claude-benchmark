from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def overlay_tests(task_dir: Path, work_dir: Path) -> None:
    """Copy the task's hidden tests/ into the working directory, replacing any existing tests/."""
    dest = work_dir / "tests"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(task_dir / "tests", dest)


def run_pytest(work_dir: Path) -> bool:
    """Run the overlaid tests inside the working directory's uv-managed venv. True on pass."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(work_dir)
    result = subprocess.run(
        ["uv", "run", "pytest", "tests", "-q"],
        cwd=work_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def score_task(task_dir: Path, work_dir: Path) -> bool:
    overlay_tests(task_dir, work_dir)
    return run_pytest(work_dir)
