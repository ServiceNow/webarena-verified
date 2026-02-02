"""Container operation helpers for Docker tasks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dev.environments.docker.utils.dockerfile import get_container_port
from dev.environments.settings import get_settings
from dev.utils import logging_utils
from dev.utils.network_utils import find_free_port
from dev.utils.path_utils import get_repo_root
from webarena_verified.environments.env_ctrl_client import EnvCtrlDockerClient

if TYPE_CHECKING:
    from invoke.context import Context

    from dev.environments.settings import BaseSiteSettings


def _container_exists(ctx: Context, name: str) -> bool:
    """Check if container exists."""
    result = ctx.run(f"docker ps -a --filter name=^{name}$ --format '{{{{.Names}}}}'", hide=True, warn=True)
    return bool(result and result.stdout.strip() == name)


def _container_running(ctx: Context, name: str) -> bool:
    """Check if container is running."""
    result = ctx.run(f"docker ps --filter name=^{name}$ --format '{{{{.Names}}}}'", hide=True, warn=True)
    return bool(result and result.stdout.strip() == name)


def _container_remove(ctx: Context, name: str, quiet: bool = False) -> None:
    """Remove container if it exists."""
    if _container_exists(ctx, name):
        if not quiet:
            logging_utils.print_info(f"Removing existing container {name}...")
        ctx.run(f"docker rm -f {name}", hide=True)


def _docker_run(
    ctx: Context,
    settings: BaseSiteSettings,
    image: str,
    name: str,
    port: int,
    idle: bool = False,
    extra_args: str = "",
    env_ctrl_port: int | None = None,
) -> None:
    """Run a docker container with standard options.

    Args:
        ctx: Invoke context.
        settings: Site settings.
        image: Docker image to run.
        name: Container name.
        port: Host port for the web service.
        idle: If True, run container in idle mode (tail -f /dev/null).
        extra_args: Additional docker run arguments.
        env_ctrl_port: Host port for env-ctrl. If None, finds a free port.
    """
    container_port = get_container_port(settings.dockerfile) if settings.dockerfile else 80
    cmd = "docker run -d"

    cmd += f" --name {name} -p {port}:{container_port}"

    # Map env-ctrl port (host port is dynamic or specified, container port is standard)
    host_env_ctrl_port = env_ctrl_port if env_ctrl_port is not None else find_free_port()
    cmd += f" -p {host_env_ctrl_port}:{get_settings().env_ctrl_container_port}"
    logging_utils.print_info(f"env-ctrl port: {host_env_ctrl_port}")

    # Data directory mounting
    if settings.data_dir:
        data_path = Path(settings.data_dir)
        if not data_path.is_absolute():
            data_path = get_repo_root() / data_path
        cmd += f" --volume={data_path}:/data"

    # Named Docker volumes
    for vol_name, container_path in settings.volumes.items():
        cmd += f" -v {vol_name}:{container_path}"

    if extra_args:
        cmd += f" {extra_args}"
    cmd += f" {image}"
    if idle:
        cmd += " tail -f /dev/null"

    desc = "Starting container (idle mode)" if idle else "Starting container"
    with logging_utils.StepContext.create(cmd, desc=desc):
        ctx.run(cmd, hide=True)


def publish_images(ctx: Context, images: list[str], yes: bool = False) -> bool:
    """Push images to Docker registry with confirmation prompt.

    Args:
        ctx: Invoke context.
        images: List of image names with tags to push.
        yes: Skip confirmation prompt if True.

    Returns:
        True if images were published, False if skipped/aborted.
    """
    if not images:
        logging_utils.print_info("No images to publish.")
        return False

    # Show what will be pushed
    logging_utils.print_info("Images to push:")
    for image in images:
        logging_utils.print_info(f"  {image}")

    # Confirmation prompt
    if not yes:
        try:
            response = input("\nPush to registry? [y/N]: ").strip().lower()
        except EOFError:
            response = "n"

        if response not in ("y", "yes"):
            logging_utils.print_info("Skipping publish.")
            return False

    # Push each image
    for image in images:
        with logging_utils.StepContext.create(f"docker push {image}", desc=f"Pushing {image}"):
            ctx.run(f"docker push {image}", pty=True)

    logging_utils.print_success("Published!", Images=", ".join(images))
    return True


def _wait_and_configure(container_name: str, port: int, timeout: int = 120, hostname: str = "localhost") -> None:
    """Wait for services and configure the container."""
    # Client timeout should be longer than wait timeout to allow for the full wait period
    client = EnvCtrlDockerClient.create(container_name, timeout=timeout + 60)

    with logging_utils.StepContext.create(
        f"Waiting for services (timeout: {timeout}s)...", desc="Health check"
    ) as step:
        result = client.start(wait=True, timeout=timeout)
        if not result.success:
            step.mark_failed("Services did not become ready")
            raise RuntimeError(f"Services failed: {result.message}")

    # Configure base URL
    base_url = f"http://{hostname}:{port}/"
    init_result = client.init(base_url=base_url)
    if init_result.success:
        logging_utils.print_info("Configuration complete")
    else:
        logging_utils.print_warning(f"Configuration had issues: {init_result.message}")
