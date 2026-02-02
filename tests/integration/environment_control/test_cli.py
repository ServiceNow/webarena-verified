"""Integration tests for environment_control CLI.

Tests the env-ctrl CLI commands running in a Docker container.

Usage:
    pytest tests/integration/environment_control/test_cli.py -v
"""

import json

# --- CLI Command Tests ---


def test_cli_list(docker_exec):
    """Test 'env-ctrl list' shows available environment types."""
    result = docker_exec("env-ctrl list")

    assert result.returncode == 0
    assert "dummy" in result.stdout
    assert "admin" in result.stdout


def test_cli_status(docker_exec):
    """Test 'env-ctrl status' with dummy env."""
    result = docker_exec("env-ctrl -e dummy status")

    assert result.returncode == 0
    assert "OK" in result.stdout


def test_cli_status_verbose(docker_exec):
    """Test 'env-ctrl status -v' returns JSON."""
    result = docker_exec("env-ctrl -v -e dummy status")

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert "details" in data
    assert "value" in data["details"]


def test_cli_start(docker_exec):
    """Test 'env-ctrl start' with dummy env."""
    result = docker_exec("env-ctrl -e dummy start")

    assert result.returncode == 0
    assert "OK" in result.stdout


def test_cli_stop(docker_exec):
    """Test 'env-ctrl stop' with dummy env."""
    result = docker_exec("env-ctrl -e dummy stop")

    assert result.returncode == 0
    assert "OK" in result.stdout


# --- CLI with Environment Variable Control ---


def test_cli_status_unhealthy(docker_exec):
    """Test 'env-ctrl status' returns failure when DUMMY_HEALTHY=0."""
    result = docker_exec("env-ctrl -e dummy status", env={"DUMMY_HEALTHY": "0"})

    assert result.returncode == 1
    assert "FAILED" in result.stdout


def test_cli_status_unhealthy_verbose(docker_exec):
    """Test 'env-ctrl status -v' returns failure JSON when DUMMY_HEALTHY=0."""
    result = docker_exec("env-ctrl -v -e dummy status", env={"DUMMY_HEALTHY": "0"})

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["success"] is False


def test_cli_init_failure(docker_exec):
    """Test 'env-ctrl init' fails when DUMMY_INIT_FAIL=1."""
    # Note: init requires base_url for shopping_admin, but dummy doesn't need it
    result = docker_exec("env-ctrl -e dummy init", env={"DUMMY_INIT_FAIL": "1"})

    assert result.returncode == 1
    assert "FAILED" in result.stdout


def test_cli_start_failure(docker_exec):
    """Test 'env-ctrl start' fails when DUMMY_START_FAIL=1."""
    result = docker_exec("env-ctrl -e dummy start", env={"DUMMY_START_FAIL": "1"})

    assert result.returncode == 1
    assert "FAILED" in result.stdout


def test_cli_stop_failure(docker_exec):
    """Test 'env-ctrl stop' fails when DUMMY_STOP_FAIL=1."""
    result = docker_exec("env-ctrl -e dummy stop", env={"DUMMY_STOP_FAIL": "1"})

    assert result.returncode == 1
    assert "FAILED" in result.stdout


# --- CLI Error Handling ---


def test_cli_unknown_env_type(docker_exec):
    """Test 'env-ctrl' with unknown environment type."""
    result = docker_exec("env-ctrl -e unknown status")

    assert result.returncode == 1
    assert "Unknown environment type" in result.stderr or "unknown" in result.stderr.lower()


def test_cli_missing_env_type(docker_exec):
    """Test 'env-ctrl' without WA_ENV_CTRL_TYPE set returns error."""
    # Override the container's WA_ENV_CTRL_TYPE
    result = docker_exec("env-ctrl status", env={"WA_ENV_CTRL_TYPE": ""})

    # Should fail because no env type specified
    assert result.returncode == 1
