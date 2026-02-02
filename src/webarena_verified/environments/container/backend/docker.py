"""Docker backend implementation.

Uses the docker CLI to manage containers.
"""

from __future__ import annotations

import socket
import subprocess


class DockerBackend:
    """Docker implementation of ContainerBackend.

    Uses the docker CLI to manage containers.
    """

    def container_exists(self, *, name: str) -> bool:
        """Check if a Docker container exists (running or stopped)."""
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() == name

    def container_running(self, *, name: str) -> bool:
        """Check if a Docker container is currently running."""
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() == name

    def container_remove(self, *, name: str) -> None:
        """Remove a Docker container if it exists."""
        if self.container_exists(name=name):
            subprocess.run(
                ["docker", "rm", "-f", name],
                capture_output=True,
                check=True,
            )

    def container_run(
        self,
        *,
        name: str,
        image: str,
        port_mappings: dict[int, int],
        volume_mappings: dict[str, str],
        env_vars: dict[str, str] | None = None,
    ) -> None:
        """Run a Docker container with the given configuration."""
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            name,
        ]

        # Add port mappings (host_port:container_port)
        for host_port, container_port in port_mappings.items():
            cmd.extend(["-p", f"{host_port}:{container_port}"])

        # Add volume mappings (volume_name:container_path)
        for volume_name, container_path in volume_mappings.items():
            cmd.extend(["-v", f"{volume_name}:{container_path}"])

        # Add environment variables
        if env_vars:
            for key, value in env_vars.items():
                cmd.extend(["-e", f"{key}={value}"])

        cmd.append(image)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to start container: {result.stderr}")

    def get_container_ports(self, *, name: str) -> dict[int, int]:
        """Get the published port mappings for a running Docker container."""
        result = subprocess.run(
            ["docker", "port", name],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return {}

        ports: dict[int, int] = {}
        for line in result.stdout.strip().split("\n"):
            if "->" in line:
                # Format: "80/tcp -> 0.0.0.0:8080"
                container_part, host_mapping = line.split(" -> ")
                container_port = int(container_part.split("/")[0])
                host_port = int(host_mapping.rsplit(":", 1)[1])
                ports[container_port] = host_port
        return ports

    def find_free_port(self) -> int:
        """Find and return an available TCP port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", 0))
            return s.getsockname()[1]
