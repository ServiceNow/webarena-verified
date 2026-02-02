"""Create base Docker image from original image."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dev.environments.docker.utils.containers import publish_images
from dev.environments.docker.utils.dockerfile import get_container_port
from dev.environments.docker.utils.sites import _get_container_name, _get_site_settings
from dev.environments.settings import get_settings
from dev.utils.logging_utils import StepContext, print_info, print_success, print_warning
from dev.utils.network_utils import find_free_port
from dev.utils.path_utils import get_repo_root

if TYPE_CHECKING:
    from invoke.context import Context

    from dev.environments.settings import BaseSiteSettings


def create_base_img(
    ctx: Context,
    site: str,
    timeout: int = 300,
    dry_run: bool = False,
    no_squash: bool = False,
) -> None:
    """Create a base image from the original Docker image.

    Pipeline:
    1. Start container with mounts and env vars
    2. Run setup scripts (bootstrap, services, patches, cleanup)
    3. Squash to output image (unless no_squash)

    Args:
        ctx: Invoke context.
        site: Site name (e.g., 'shopping_admin').
        timeout: Timeout for service startup in seconds.
        dry_run: If True, run scripts with BUILD_DRY_RUN=true but skip squash.
        no_squash: If True, commit image directly without squashing.
    """
    settings = _get_site_settings(site)

    if not settings.base_docker_img:
        raise ValueError(f"Site '{site}' does not have base_docker_img configured")

    port = find_free_port()
    env_ctrl_port = find_free_port()
    print_info(f"Using ports: web={port}, env-ctrl={env_ctrl_port}")

    container = f"{_get_container_name(site)}_build"
    output_image = f"{settings.base_docker_img}:latest"
    site_dir = (Path(__file__).parent.parent / "sites" / site).resolve()
    env_ctrl_pkg = get_repo_root() / get_settings().env_ctrl_package_path

    try:
        _start_container(ctx, container, settings, site_dir, env_ctrl_pkg, port, env_ctrl_port, timeout, dry_run)

        # Always run scripts - they handle dry_run internally via BUILD_DRY_RUN env var
        _run_setup_scripts(ctx, container, site_dir / "scripts")

        if dry_run:
            print_warning("DRY RUN - squash skipped.")
        elif no_squash:
            _commit(ctx, container, output_image)
            print_success("Image created (not squashed)!", Image=output_image)
            ctx.run(f"docker images | grep -E '({output_image.split(':')[0]}|REPOSITORY)'")
        else:
            _squash(ctx, container, output_image)
            print_success("Image created!", Image=output_image)
            ctx.run(f"docker images | grep -E '({output_image.split(':')[0]}|REPOSITORY)'")

            # Prompt to publish
            publish_images(ctx, [output_image])

    except KeyboardInterrupt:
        print_warning("Interrupted by user (Ctrl-C)")
        raise SystemExit(130) from None
    finally:
        _cleanup_or_commit_wip(ctx, container, settings)


def _start_container(
    ctx: Context,
    container: str,
    settings: BaseSiteSettings,
    site_dir: Path,
    env_ctrl_pkg: Path,
    port: int,
    env_ctrl_port: int,
    timeout: int,
    dry_run: bool = False,
) -> None:
    """Start build container with mounts and env vars."""
    print_info(f"Starting container from {settings.original_docker_img}...")
    ctx.run(f"docker rm -f {container}", warn=True, hide=True)

    base_url = f"http://localhost:{port}/"
    mounts = [
        f"-v {site_dir}:/build-site:ro",
        f"-v {env_ctrl_pkg}:/build-env-ctrl:ro",
    ]
    env_vars = [
        f"-e BUILD_BASE_URL={base_url}",
        f"-e BUILD_TIMEOUT={timeout}",
        f"-e BUILD_DRY_RUN={str(dry_run).lower()}",
        "-e BUILD_ENV_CTRL_SRC=/build-env-ctrl",
        "-e WA_ENV_CTRL_ROOT=/opt",
        f"-e WA_ENV_CTRL_TYPE={settings.site.value}",
    ]

    container_port = get_container_port(settings.dockerfile) if settings.dockerfile else 80
    cmd = (
        f"docker run -d --name {container} "
        f"-p {port}:{container_port} "
        f"-p {env_ctrl_port}:{get_settings().env_ctrl_container_port} "
        f"{' '.join(env_vars)} "
        f"{' '.join(mounts)} "
        f"{settings.original_docker_img} tail -f /dev/null"
    )
    with StepContext.create(cmd, desc="Starting container"):
        ctx.run(cmd, hide=True)


def _run_setup_scripts(ctx: Context, container: str, scripts_dir: Path) -> None:
    """Execute build scripts in order."""
    if not scripts_dir.exists():
        print_info("No build scripts found")
        return

    for script in sorted(scripts_dir.glob("*.sh")):
        print_info(f"Running {script.name}...")
        # Use plain=True to avoid Rich markup parsing (output may contain paths like [/etc/gitlab])
        with StepContext.create(f"docker exec {container} bash /build-site/scripts/{script.name}", plain=True):
            ctx.run(f"docker exec {container} bash /build-site/scripts/{script.name}")


def _commit(ctx: Context, container: str, output: str) -> None:
    """Commit container into image without squashing.

    Args:
        ctx: Invoke context.
        container: Container name to commit.
        output: Output image name with tag.
    """
    print_info("Committing image (no squash)...")
    ctx.run(f"docker stop {container}", hide=True)

    with StepContext.create(f"docker commit {container} {output}", desc="Committing"):
        ctx.run(f"docker commit {container} {output}", hide=True)


def _squash(ctx: Context, container: str, output: str, squash_timeout: int = 3600) -> None:
    """Commit and squash container into slim image.

    Args:
        ctx: Invoke context.
        container: Container name to commit.
        output: Output image name with tag.
        squash_timeout: Timeout for docker-squash operations in seconds (default: 3600).
    """
    print_info("Squashing image...")
    ctx.run(f"docker stop {container}", hide=True)

    temp = f"{output.split(':')[0]}_temp:build"
    with StepContext.create(f"docker commit {container} {temp}", desc="Committing"):
        ctx.run(f"docker commit {container} {temp}", hide=True)

    with StepContext.create(f"docker-squash -t {output}", desc="Squashing"):
        ctx.run(f"DOCKER_TIMEOUT={squash_timeout} uv run docker-squash -v -t {output} {temp}", hide=False)

    ctx.run(f"docker rmi {temp}", warn=True, hide=True)


def _cleanup_or_commit_wip(ctx: Context, container: str, settings: BaseSiteSettings) -> None:
    """Ask user whether to clean up container or commit as WIP image.

    Args:
        ctx: Invoke context.
        container: Container name to clean up or commit.
        settings: Site settings for WIP image naming.
    """
    try:
        response = input("\nClean up build container? [Y/n]: ").strip().lower()
    except EOFError:
        response = "y"

    if response in ("", "y", "yes"):
        print_info("Cleaning up build container...")
        ctx.run(f"docker rm -f {container}", warn=True, hide=True)
    else:
        wip_image = f"{settings.base_docker_img}:wip"
        print_info(f"Committing container as WIP image: {wip_image}")
        ctx.run(f"docker stop {container}", warn=True, hide=True)
        ctx.run(f"docker commit {container} {wip_image}", hide=True)
        print_success("WIP image created!", Image=wip_image, Container=container)
        print_info(f"Container '{container}' kept for debugging. Remove with: docker rm -f {container}")
