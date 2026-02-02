"""Tests for webarena-verified CLI entrypoints (uvx, Docker)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def run_cli(request, uvx, docker, webarena_verified_docker_img, tmp_path):
    """Factory fixture that returns a function to run CLI commands via the specified runner."""
    runner = request.param

    def _run(args: list[str], timeout: int = 120, path_args: dict[str, Path] | None = None):
        """Run webarena-verified CLI with the specified arguments.

        Args:
            args: CLI arguments (without 'webarena-verified' prefix).
                  Use {key} placeholders for paths defined in path_args.
            timeout: Command timeout in seconds
            path_args: Dict of {placeholder: host_path} for path arguments.
                       For Docker, these are automatically mounted as volumes.

        Returns:
            subprocess.CompletedProcess
        """
        path_args = path_args or {}

        if runner == "uvx":
            # Replace placeholders with host paths
            resolved_args = []
            for arg in args:
                for key, path in path_args.items():
                    arg = arg.replace(f"{{{key}}}", str(path))
                resolved_args.append(arg)

            cmd = [uvx, "webarena-verified", *resolved_args]
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=tmp_path)

        if runner == "docker":
            # Build volume mounts and replace placeholders with container paths
            volumes = []
            container_paths = {}
            for key, host_path in path_args.items():
                container_path = f"/{key}"
                volumes.extend(["-v", f"{host_path}:{container_path}"])
                container_paths[key] = container_path

            resolved_args = []
            for arg in args:
                for key, container_path in container_paths.items():
                    arg = arg.replace(f"{{{key}}}", container_path)
                resolved_args.append(arg)

            cmd = [docker, "run", "--rm", *volumes, webarena_verified_docker_img, *resolved_args]
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        raise ValueError(f"Unknown runner: {runner}")

    return _run


# Define runner parameters with appropriate markers
uvx_runner = pytest.param("uvx", id="uvx")
docker_runner = pytest.param("docker", marks=pytest.mark.docker, id="docker")


@pytest.mark.parametrize("run_cli", [uvx_runner, docker_runner], indirect=True)
def test_cli_help(run_cli):
    """Test that CLI can run --help."""
    result = run_cli(["--help"])
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert "webarena-verified" in result.stdout.lower() or "usage" in result.stdout.lower()


@pytest.mark.parametrize("run_cli", [uvx_runner, docker_runner], indirect=True)
def test_cli_eval_task(run_cli, get_test_asset_path, tmp_path):
    """Test that CLI can evaluate a task using example data."""
    # Copy test assets to tmp_path to avoid modifying original files
    test_data = tmp_path / "cli"
    shutil.copytree(get_test_asset_path("cli"), test_data)

    result = run_cli(
        ["eval-tasks", "--task-ids", "108", "--output-dir", "{output_dir}", "--config", "{config}"],
        path_args={"output_dir": test_data / "agent_logs", "config": test_data / "config.demo.json"},
    )

    assert result.returncode == 0, f"eval-tasks failed: {result.stderr}"

    # Verify eval_result.json was created and check contents
    eval_result_file = test_data / "agent_logs" / "108" / "eval_result.json"
    assert eval_result_file.exists(), "eval_result.json was not created"

    eval_result = json.loads(eval_result_file.read_text())
    assert eval_result["task_id"] == 108
    assert eval_result["status"] == "success"
    assert eval_result["score"] == 1.0
    assert len(eval_result["evaluators_results"]) == 1
    assert eval_result["evaluators_results"][0]["evaluator_name"] == "AgentResponseEvaluator"
    assert eval_result["evaluators_results"][0]["status"] == "success"
    assert eval_result["evaluators_results"][0]["assertions"] is None
