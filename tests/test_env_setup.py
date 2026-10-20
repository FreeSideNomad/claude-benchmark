from pathlib import Path
from unittest.mock import patch

from harness.lib.env_setup import create_venv, install_requirements


def test_create_venv_runs_uv_venv_in_work_dir():
    with patch("harness.lib.env_setup.subprocess.run") as mock_run:
        create_venv(Path("/tmp/work"))

    mock_run.assert_called_once_with(
        ["uv", "venv"], cwd=Path("/tmp/work"), check=True, capture_output=True
    )


def test_install_requirements_runs_uv_pip_install():
    with patch("harness.lib.env_setup.subprocess.run") as mock_run:
        install_requirements(Path("/tmp/work"), Path("/tmp/task/requirements.txt"))

    mock_run.assert_called_once_with(
        ["uv", "pip", "install", "pytest", "-r", "/tmp/task/requirements.txt"],
        cwd=Path("/tmp/work"),
        check=True,
        capture_output=True,
    )
