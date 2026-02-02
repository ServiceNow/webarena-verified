"""Fixtures for environment_control integration tests.

Starts a Python 3.10 container with the environment_control package mounted
and installed, running the env-ctrl server with the dummy ops.
"""

import socket
import subprocess
import time
from collections.abc import Generator
from dataclasses import dataclass

import pytest

from webarena_verified.environments.env_ctrl_client import EnvCtrlClient

# Container configuration
CONTAINER_NAME = "env-ctrl-test"
CONTAINER_IMAGE = "python:3.10-slim"


@dataclass
class EnvControlContainer:
    """Container info returned by env_control_container fixture."""

    name: str
    base_url: str
    port: int


def _find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _image_exists(image: str) -> bool:
    """Check if a Docker image exists locally."""
    result = subprocess.run(
        ["docker", "images", "-q", image],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


@pytest.fixture(scope="session")
def env_ctrl_server_port() -> int:
    """Find an available port for the env-ctrl server."""
    return _find_free_port()


@pytest.fixture(scope="module")
def env_control_container(request, docker, env_ctrl_server_port) -> Generator[EnvControlContainer]:
    """Start a Python container with environment_control installed and server running.

    The container:
    - Uses python:3.10-slim image
    - Mounts packages/environment_control into /app
    - Installs the package with pip
    - Runs env-ctrl serve with WA_ENV_CTRL_TYPE=dummy

    Yields:
        EnvControlContainer with name, base_url, and port.

    Cleanup:
    - Removes the container
    - If the image was pulled by this test (didn't exist before), removes it too
    """
    port = env_ctrl_server_port
    base_url = f"http://localhost:{port}"

    # Check if image existed before we start
    image_existed_before = _image_exists(CONTAINER_IMAGE)

    # Get the path to packages/environment_control using pytest rootpath
    package_path = request.config.rootpath / "packages" / "environment_control"

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
            f"{port}:{port}",
            "-v",
            f"{package_path}:/app",
            "-w",
            "/app",
            "-e",
            "WA_ENV_CTRL_TYPE=dummy",
            "-e",
            f"WA_ENV_CTRL_PORT={port}",
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
    client = EnvCtrlClient(base_url=base_url, timeout=5)
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
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
        raise RuntimeError(f"Server did not start within {max_wait}s. Logs:\n{logs.stdout}\n{logs.stderr}")

    yield EnvControlContainer(name=CONTAINER_NAME, base_url=base_url, port=port)

    # Cleanup container
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)

    # If image didn't exist before, remove it
    if not image_existed_before:
        subprocess.run(["docker", "rmi", CONTAINER_IMAGE], capture_output=True)


@pytest.fixture
def client(env_control_container: EnvControlContainer) -> EnvCtrlClient:
    """Create a client connected to the test container's server."""
    return EnvCtrlClient(base_url=env_control_container.base_url, timeout=10)


@pytest.fixture
def docker_exec(env_control_container: EnvControlContainer):
    """Return a function to execute commands in the container."""
    container_name = env_control_container.name

    def _exec(cmd: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        docker_cmd = ["docker", "exec"]

        if env:
            for key, value in env.items():
                docker_cmd.extend(["-e", f"{key}={value}"])

        docker_cmd.extend([container_name, "bash", "-c", cmd])

        return subprocess.run(docker_cmd, capture_output=True, text=True)

    return _exec
