"""Docker container and image management tasks.

Provides envs.docker.* namespace for container lifecycle, image management,
and optimization operations.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from invoke import Collection, task

if TYPE_CHECKING:
    from invoke.context import Context

from dev.environments.docker.utils import SEMVER_PATTERN, containers, downloads, sites
from dev.environments.docker.utils.create_base_img import create_base_img
from dev.utils import logging_utils
from dev.utils.network_utils import find_free_port
from dev.utils.path_utils import get_repo_root
from webarena_verified.environments.env_ctrl_client import EnvCtrlDockerClient

# =============================================================================
# Task definitions
# =============================================================================


@task
@logging_utils.with_banner()
def start(
    ctx: Context,
    site: str,
    port: int | None = None,
    hostname: str = "localhost",
    image: str | None = None,
    idle: bool = False,
    original: bool = False,
) -> None:
    """Start container for a site.

    Args:
        site: Site name (e.g., shopping-admin, wikipedia).
        port: Port to expose (default: finds a free port).
        hostname: Hostname for base URL (default: localhost).
        image: Image name to use (default: from settings).
        idle: Start with tail -f /dev/null for exploration.
        original: Use the original unoptimized image.
    """
    settings = sites._get_site_settings(site)
    docker_image = settings.original_docker_img if original else settings.docker_img
    effective_image = image or docker_image
    effective_port = port if port is not None else find_free_port()
    container_name = sites._get_container_name(site)

    containers._container_remove(ctx, container_name)
    containers._docker_run(ctx, settings, effective_image, container_name, effective_port, idle=idle)

    if idle:
        logging_utils.print_info("Container started in idle mode (tail -f /dev/null).")
    else:
        containers._wait_and_configure(container_name, effective_port, hostname=hostname)

    logging_utils.print_success("Container started!", URL=f"http://{hostname}:{effective_port}")
    logging_utils.print_list(
        [
            "Useful commands:",
            f"inv envs.docker.stop --site={site}  - Stop and remove container",
        ]
    )


@task
@logging_utils.with_banner()
def stop(ctx: Context, site: str) -> None:
    """Stop and remove container for a site.

    Args:
        site: Site name (e.g., shopping-admin).
    """
    container = sites._get_container_name(site)

    if not containers._container_exists(ctx, container):
        logging_utils.print_info(f"Container '{container}' does not exist.")
        return

    with logging_utils.StepContext.create(f"docker rm -f {container}", desc="Removing container"):
        ctx.run(f"docker rm -f {container}", hide=True)

    logging_utils.print_success("Container removed")


@task
@logging_utils.with_banner()
def check(ctx: Context, site: str) -> None:
    """Check if container is healthy.

    Args:
        site: Site name (e.g., shopping-admin).
    """
    container = sites._get_container_name(site)

    if not containers._container_running(ctx, container):
        logging_utils.print_error(f"Container '{container}' is not running")
        raise SystemExit(1)

    logging_utils.print_info(f"Container '{container}' is running")

    client = EnvCtrlDockerClient.create(container)
    result = client.status()

    if not result.success:
        logging_utils.print_error(f"Failed to get health status: {result.message}")
        raise SystemExit(1)

    details = result.details
    services = details.get("services", {})

    if not services:
        logging_utils.print_warning("No service status available")
        return

    health_data = {}
    all_healthy = True
    for svc_name, state in services.items():
        is_healthy = str(state).upper() in ("RUNNING", "HEALTHY")
        health_data[svc_name] = f"{'✓' if is_healthy else '✗'} {state}"
        if not is_healthy:
            all_healthy = False

    logging_utils.print_table(health_data)

    if not all_healthy:
        logging_utils.print_failure("Some services are not healthy")
        raise SystemExit(1)

    logging_utils.print_success("All checks passed!")


@task
@logging_utils.with_banner()
def pull(
    ctx: Context,
    site: str,
    tag: str = "latest",
    force: bool = False,
    original: bool = False,
    output_dir: str | None = None,
    dry_run: bool = False,
) -> None:
    """Pull image from Docker Hub or download original from URL.

    Use --site=all to download all original images without loading them.

    Args:
        site: Site name (e.g., shopping-admin), or 'all' to pull all original images.
        tag: Image tag to pull (default: latest).
        force: Always pull/download even if exists locally.
        original: Download original image from URL.
        output_dir: Directory to save downloaded tar file.
        dry_run: Show what would be downloaded without downloading (only with --site=all).
    """
    # Handle --site=all
    if site.lower() == "all":
        if dry_run:
            logging_utils.print_info("Dry run - showing what would be downloaded:\n")

        for site_name in sites._list_sites():
            settings = sites._get_site_settings(site_name)

            if dry_run:
                info = downloads._get_download_info(settings, output_dir)
                if not info["url"]:
                    logging_utils.print_info(f"  [SKIP - no URL] {site_name}")
                    continue
                status = "[SKIP - exists]" if info["exists"] and not force else "[DOWNLOAD]"
                if force and info["exists"]:
                    status = "[DOWNLOAD - force]"
                logging_utils.print_info(f"  {status} {site_name}")
                logging_utils.print_info(f"    URL: {info['url']}")
                logging_utils.print_info(f"    To:  {info['output_path']}\n")
            else:
                logging_utils.print_info(f"Downloading {site_name}...")
                downloads._pull_original(ctx, settings, force=force, output_dir=output_dir, load=False)
        return

    # Single site
    settings = sites._get_site_settings(site)

    if original:
        downloads._pull_original(ctx, settings, force=force, output_dir=output_dir, load=True)
    else:
        downloads._pull_slim(ctx, settings, force=force)


@task(name="data-download")
@logging_utils.with_banner()
def data_download(
    ctx: Context,
    site: str | None = None,
    force: bool = False,
    output_dir: str | None = None,
    dry_run: bool = False,
) -> None:
    """Download data files (non-Docker artifacts) for sites.

    Downloads files specified in data_urls settings (e.g., Wikipedia ZIM files).

    Args:
        site: Site name (e.g., wikipedia), or omit to download all.
        force: Re-download even if file exists locally.
        output_dir: Directory to save files (default: from settings or downloads/).
        dry_run: Show what would be downloaded without downloading.
    """
    # Determine which sites to process
    if site:
        site_list = [site]
    else:
        site_list = sites._list_sites()

    if dry_run:
        logging_utils.print_info("Dry run - showing what would be downloaded:\n")

    any_downloads = False
    for site_name in site_list:
        settings = sites._get_site_settings(site_name)
        infos = downloads._get_data_download_info(settings, output_dir)

        if not infos:
            continue

        any_downloads = True
        for info in infos:
            if dry_run:
                status = "[SKIP - exists]" if info["exists"] and not force else "[DOWNLOAD]"
                if force and info["exists"]:
                    status = "[DOWNLOAD - force]"
                logging_utils.print_info(f"  {status} {site_name}")
                logging_utils.print_info(f"    URL: {info['url']}")
                logging_utils.print_info(f"    To:  {info['output_path']}\n")
            else:
                logging_utils.print_info(f"Downloading data for {site_name}...")
                downloads._download_data(ctx, settings, force=force, output_dir=output_dir)
                break  # _download_data handles all URLs for the site

    if not any_downloads:
        logging_utils.print_info("No sites have data_urls configured.")


@task
@logging_utils.with_banner()
def build(ctx: Context, site: str, tag: str | None = None, no_cache: bool = False) -> None:
    """Build Docker image for a site from its Dockerfile.

    Args:
        site: Site name (e.g., shopping-admin).
        tag: Image tag (default: latest).
        no_cache: Build without using cache.
    """
    settings = sites._get_site_settings(site)

    if not settings.dockerfile:
        logging_utils.print_error(f"No dockerfile configured for site '{site}' in settings")
        raise SystemExit(1)

    repo_root = get_repo_root()
    dockerfile = repo_root / settings.dockerfile

    if not dockerfile.exists():
        logging_utils.print_error(f"Dockerfile not found: {dockerfile}")
        raise SystemExit(1)

    # Build image name
    image_name = settings.docker_img
    if tag:
        image_name = f"{image_name}:{tag}"

    cache_flag = "--no-cache" if no_cache else ""
    cmd = f"docker build {cache_flag} -t {image_name} -f {dockerfile} {repo_root}".strip()

    logging_utils.print_info(f"Building {image_name} from {dockerfile}")
    ctx.run(cmd)


@task
@logging_utils.with_banner()
def publish(
    ctx: Context,
    site: str,
    tag: str,
    image: str | None = None,
    name: str | None = None,
    yes: bool = False,
) -> None:
    """Publish optimized image to Docker Hub.

    Tag must be a valid semver (e.g., 1.0.0, 2.1.3).
    Pushes both the semver tag and latest.

    Args:
        site: Site name (e.g., shopping-admin).
        tag: Semver tag (required, e.g., 1.0.0).
        image: Local image name to publish (default: {docker_img}:dev-latest).
        name: Image name in repository (default: from settings).
        yes: Skip confirmation prompt.
    """
    if not SEMVER_PATTERN.match(tag):
        raise SystemExit(f"Invalid tag '{tag}'. Must be semver format (e.g., 1.0.0)")

    settings = sites._get_site_settings(site)

    # Local image defaults to the provided tag
    local_image = image or f"{settings.docker_img}:{tag}"

    # Remote name defaults to docker_img from settings
    remote_name = name or settings.docker_img

    # Push both semver tag and latest
    tags_to_push = [tag, "latest"]
    remote_images = [f"{remote_name}:{t}" for t in tags_to_push]

    logging_utils.print_info(f"Local image:  {local_image}")
    for ri in remote_images:
        logging_utils.print_info(f"Remote image: {ri}")

    # Tag images for remote
    for ri in remote_images:
        ctx.run(f"docker tag {local_image} {ri}", hide=True)

    # Use shared publish utility
    if containers.publish_images(ctx, remote_images, yes=yes):
        logging_utils.print_success("PUBLISH COMPLETE")


@task(name="test")
@logging_utils.with_banner()
def docker_test(
    ctx: Context,
    site: str,
    tag: str = "latest",
    headed: bool = False,
    remote_img: bool = False,
) -> None:
    """Run integration tests against a Docker image.

    Stops any existing container, starts from the specified image, and runs
    pytest with the site's marker (e.g., -m integration_docker_shopping_admin).

    Args:
        site: Site name (e.g., shopping-admin).
        tag: Image tag (default: latest).
        headed: Run browser tests in headed mode.
        remote_img: Delete local image first to force pull from registry.
    """
    settings = sites._get_site_settings(site)

    # Build image name with tag
    image_name = f"{settings.docker_img}:{tag}"
    container_name = sites._get_container_name(site)

    # Marker uses underscores (same as site)
    marker = f"integration_docker_{site}"

    # Stop and remove any existing container
    containers._container_remove(ctx, container_name, quiet=True)

    # Delete local image and pull from registry
    if remote_img:
        logging_utils.print_info(f"Removing local image {image_name}...")
        ctx.run(f"docker rmi {image_name}", warn=True)
        logging_utils.print_info(f"Pulling {image_name} from registry...")
        ctx.run(f"docker pull {image_name}")

    port = find_free_port()
    env_ctrl_port = find_free_port()
    try:
        # Start container
        logging_utils.print_info(f"Starting container {container_name} from {image_name}")
        containers._container_remove(ctx, container_name, quiet=True)

        # GitLab: skip reconfigure during init to avoid 502 errors after startup
        # Also mount local env-ctrl code to test latest changes before image rebuild
        extra_args = ""
        if site == "gitlab":
            env_ctrl_path = get_repo_root() / "packages" / "environment_control" / "environment_control"
            extra_args = f"-e WA_ENV_CTRL_SKIP_RECONFIGURE=true -v {env_ctrl_path}:/usr/local/environment_control"

        containers._docker_run(
            ctx, settings, image_name, container_name, port, env_ctrl_port=env_ctrl_port, extra_args=extra_args
        )
        containers._wait_and_configure(container_name, port)

        # Run tests
        logging_utils.print_info(f"Running tests with marker: {marker}")
        headed_flag = " --headed" if headed else ""
        site_url = f"http://localhost:{port}"
        env_ctrl_url = f"http://localhost:{env_ctrl_port}"
        pytest_args = f"--{site}_url={site_url} --{site}_env_ctrl_url={env_ctrl_url}"
        ctx.run(f"uv run pytest tests/integration/environments/ -m {marker} -v {pytest_args}{headed_flag}")
    finally:
        # Cleanup: stop and remove container
        logging_utils.print_info(f"Cleaning up container {container_name}")
        containers._container_remove(ctx, container_name, quiet=True)


@task(name="create-base-img")
@logging_utils.with_banner()
def create_base_img_task(
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
    3. Squash to output image (unless --no-squash)

    Args:
        site: Site name (e.g., shopping-admin).
        timeout: Timeout for service startup in seconds (default: 300).
        dry_run: Run scripts with BUILD_DRY_RUN=true but skip squash.
        no_squash: Skip squashing - just commit the image directly.
    """
    create_base_img(ctx, site, timeout=timeout, dry_run=dry_run, no_squash=no_squash)


@task(name="setup")
@logging_utils.with_banner()
def setup_task(
    ctx: Context,
    site: str,
    data_dir: str,
    dry_run: bool = False,
    keep_downloads: bool = False,
) -> None:
    """Set up Docker volumes and data for a site.

    Downloads required data files (if not present in data-dir) and loads them
    into Docker volumes. Site-specific setup logic is in sites/<site>/scripts/docker_setup.py.

    Args:
        site: Site name (e.g., wikipedia, map).
        data_dir: Directory to store/find data files.
        dry_run: Show what would be done without doing it.
        keep_downloads: Don't delete downloaded files after loading.
    """
    # Validate site exists
    sites._get_site_settings(site)

    # Try to import site-specific setup module
    try:
        module = importlib.import_module(f"dev.environments.docker.sites.{site}.scripts.docker_setup")
    except ModuleNotFoundError:
        logging_utils.print_warning(f"Site '{site}' has no setup configured")
        return  # exit 0, not error

    module.setup(ctx, Path(data_dir), dry_run=dry_run, keep_downloads=keep_downloads)


# =============================================================================
# Collection
# =============================================================================

ns = Collection()
ns.add_task(start)  # ty: ignore[invalid-argument-type]
ns.add_task(stop)  # ty: ignore[invalid-argument-type]
ns.add_task(check)  # ty: ignore[invalid-argument-type]
ns.add_task(pull)  # ty: ignore[invalid-argument-type]
ns.add_task(data_download)
ns.add_task(build)  # ty: ignore[invalid-argument-type]
ns.add_task(publish)  # ty: ignore[invalid-argument-type]
ns.add_task(docker_test)
ns.add_task(create_base_img_task)
ns.add_task(setup_task)
