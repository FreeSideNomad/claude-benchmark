from __future__ import annotations

import subprocess
from pathlib import Path


def create_venv(work_dir: Path) -> None:
    subprocess.run(["uv", "venv"], cwd=work_dir, check=True, capture_output=True)


def install_requirements(work_dir: Path, requirements_file: Path) -> None:
    subprocess.run(
        ["uv", "pip", "install", "pytest", "-r", str(requirements_file)],
        cwd=work_dir,
        check=True,
        capture_output=True,
    )
