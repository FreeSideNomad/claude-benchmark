from __future__ import annotations

import shutil
from pathlib import Path


def create_worktree(seed_dir: Path, work_dir: Path) -> Path:
    """Copy a task's seed/ files into a fresh disposable working directory."""
    shutil.copytree(seed_dir, work_dir)
    return work_dir


def remove_worktree(work_dir: Path) -> None:
    """Remove a working directory created by create_worktree."""
    shutil.rmtree(work_dir, ignore_errors=True)
