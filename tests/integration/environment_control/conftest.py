"""Fixtures for environment_control integration tests.

Starts a Python 3.10 container with the environment_control package mounted
and installed, running the env-ctrl server with the dummy ops.
"""

import os
import subprocess
import time

import pytest

from webarena_verified.environments.env_ctrl_client import EnvCtrlClient

# Container configuration
CONTAINER_NAME = "env-ctrl-test"
CONTAINER_IMAGE = "python:3.10-slim"
SERVER_PORT = 8877


def _image_exists(image: str) -> bool:
    """Check if a Docker image exists locally."""
    result = subprocess.run(
        ["docker", "images", "-q", image],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


@pytest.fixture(scope="module")
def env_control_container(request, docker):
    """Start a Python container with environment_control installed and server running.

    The container:
    - Uses python:3.10-slim image
    - Mounts packages/environment_control into /app
    - Installs the package with pip
    - Runs env-ctrl serve with WA_ENV_CTRL_TYPE=dummy
    - Exposes port 8877

    Cleanup:
    - Removes the container
    - If the image was pulled by this test (didn't exist before), removes it too
    """
    # Check if image existed before we start
    image_existed_before = _image_exists(CONTAINER_IMAGE)

    # Get the path to packages/environment_control
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    package_path = os.path.join(repo_root, "packages", "environment_control")

    # Stop any existing container
    subprocess.run(
        ["docker", "rm", "-f", CONTAINER_NAME],
        capture_output=True,
    )

    # Start the container
    result = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER_NAME,
            "-p",
            f"{SERVER_PORT}:{SERVER_PORT}",
            "-v",
            f"{package_path}:/app",
            "-w",
            "/app",
            "-e",
            "WA_ENV_CTRL_TYPE=dummy",
            "-e",
            "WA_ENV_CTRL_PORT=8877",
            CONTAINER_IMAGE,
            "bash",
            "-c",
            "pip install --upgrade pip && pip install . && env-ctrl serve",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to start container: {result.stderr}")

    # Wait for server to be ready
    client = EnvCtrlClient(base_url=f"http://localhost:{SERVER_PORT}", timeout=5)
    max_wait = 30
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            client.status()
            break
        except Exception:
            time.sleep(1)
    else:
        # Get container logs for debugging
        logs = subprocess.run(
            ["docker", "logs", CONTAINER_NAME],
            capture_output=True,
            text=True,
        )
        raise RuntimeError(f"Server did not start within {max_wait}s. Logs:\n{logs.stdout}\n{logs.stderr}")

    yield CONTAINER_NAME

    # Cleanup container
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)

    # If image didn't exist before, remove it
    if not image_existed_before:
        subprocess.run(["docker", "rmi", CONTAINER_IMAGE], capture_output=True)


@pytest.fixture
def client(env_control_container):
    """Create a client connected to the test container's server."""
    return EnvCtrlClient(base_url=f"http://localhost:{SERVER_PORT}", timeout=10)


@pytest.fixture
def docker_exec(env_control_container):
    """Return a function to execute commands in the container."""

    def _exec(cmd: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        docker_cmd = ["docker", "exec"]

        if env:
            for key, value in env.items():
                docker_cmd.extend(["-e", f"{key}={value}"])

        docker_cmd.extend([CONTAINER_NAME, "bash", "-c", cmd])

        return subprocess.run(docker_cmd, capture_output=True, text=True)

    return _exec
