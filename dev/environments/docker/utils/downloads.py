"""Download helpers for Docker tasks."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from dev.utils import logging_utils
from dev.utils.path_utils import get_repo_root

if TYPE_CHECKING:
    from invoke.context import Context

    from dev.environments.settings import BaseSiteSettings


def download_file_in_container(ctx: Context, url: str, output_dir: Path) -> Path:
    """Download file using aria2c in alpine container.

    Returns path to downloaded file.
    """
    filename = url.rsplit("/", 1)[-1]
    output_path = output_dir / filename

    # Use alpine container with aria2c for consistent, fast downloads
    cmd = (
        f"docker run --rm -v {output_dir}:/data alpine sh -c "
        f"'apk add --no-cache aria2 && aria2c -x 16 -s 16 --file-allocation=none -d /data -o {filename} \"{url}\"'"
    )

    with logging_utils.StepContext.create(f"Downloading {filename}", desc="Downloading"):
        ctx.run(cmd, pty=True)

    return output_path


def _get_download_info(settings: BaseSiteSettings, output_dir: str | None = None) -> dict:
    """Get download information without downloading."""
    url = settings.original_docker_url
    if not url:
        return {"url": None, "filename": None, "output_path": None, "exists": False}
    filename = url.rsplit("/", 1)[-1]

    if output_dir:
        effective_dir = Path(output_dir)
    else:
        effective_dir = get_repo_root() / "downloads"

    output_path = effective_dir / filename
    return {"url": url, "filename": filename, "output_path": output_path, "exists": output_path.exists()}


def _get_data_download_info(settings: BaseSiteSettings, output_dir: str | None = None) -> list[dict]:
    """Get download information for data URLs without downloading.

    Returns a list of dicts, one per data URL.
    """
    if not settings.data_urls:
        return []

    if output_dir:
        effective_dir = Path(output_dir)
    elif settings.data_dir:
        effective_dir = get_repo_root() / settings.data_dir
    else:
        effective_dir = get_repo_root() / "downloads"

    results = []
    for url in settings.data_urls:
        filename = url.rsplit("/", 1)[-1]
        output_path = effective_dir / filename
        results.append({"url": url, "filename": filename, "output_path": output_path, "exists": output_path.exists()})
    return results


def _download_data(
    ctx: Context,
    settings: BaseSiteSettings,
    force: bool = False,
    output_dir: str | None = None,
) -> None:
    """Download data files for a site."""
    infos = _get_data_download_info(settings, output_dir)
    if not infos:
        logging_utils.print_info(f"No data_urls configured for {settings.site.value}")
        return

    for info in infos:
        url, filename, output_path = info["url"], info["filename"], Path(info["output_path"])

        if not force and output_path.exists():
            logging_utils.print_info(f"File {output_path} already exists. Use --force to re-download.")
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        _download_file(ctx, url, output_path, filename)
        logging_utils.print_success("Download complete!", Path=str(output_path))


def _download_file(ctx: Context, url: str, output_path: Path, filename: str) -> None:
    """Download file using best available tool."""
    if shutil.which("aria2c"):
        cmd = f"aria2c -x 16 -s 16 --file-allocation=none -d {output_path.parent} -o {filename} {url}"
        tool = "aria2c"
    elif shutil.which("wget"):
        cmd = f"wget -O {output_path} {url}"
        tool = "wget"
    elif shutil.which("curl"):
        cmd = f"curl -L -o {output_path} {url}"
        tool = "curl"
    else:
        logging_utils.print_error("No download tool available. Install aria2c, wget, or curl.")
        raise SystemExit(1)

    with logging_utils.StepContext.create(cmd, desc=f"Downloading with {tool}"):
        ctx.run(cmd, pty=True)


def _load_docker_image(ctx: Context, tar_path: Path, image_name: str) -> None:
    """Load a tar file into Docker."""
    if shutil.which("pv"):
        cmd = f"pv {tar_path} | docker load"
        with logging_utils.StepContext.create(cmd, desc="Loading Docker image"):
            ctx.run(cmd, pty=True)
    else:
        cmd = f"docker load -i {tar_path}"
        with logging_utils.StepContext.create(cmd, desc="Loading Docker image"):
            ctx.run(cmd, hide=False)

    logging_utils.print_success("Image loaded!", Image=image_name)


def _pull_slim(ctx: Context, settings: BaseSiteSettings, force: bool = False) -> None:
    """Pull slim image from Docker Hub."""
    full_image = settings.docker_img

    if not force:
        result = ctx.run(f"docker images -q {full_image}", hide=True, warn=True)
        if result and result.stdout.strip():
            logging_utils.print_info(f"Image {full_image} already exists. Use --force to pull anyway.")
            return

    with logging_utils.StepContext.create(f"docker pull {full_image}", desc="Pulling from Docker Hub"):
        ctx.run(f"docker pull {full_image}", pty=True)

    logging_utils.print_success("Pull complete!", Image=full_image)


def _pull_original(
    ctx: Context,
    settings: BaseSiteSettings,
    force: bool = False,
    output_dir: str | None = None,
    load: bool = True,
) -> None:
    """Download original image from URL."""
    info = _get_download_info(settings, output_dir)
    if not info["url"]:
        logging_utils.print_warning(f"No original_docker_url configured for {settings.site.value}")
        return

    url, filename, output_path = info["url"], info["filename"], Path(info["output_path"])
    is_docker_image = filename.endswith(".tar")

    if not force:
        if load and is_docker_image:
            result = ctx.run(f"docker images -q {settings.original_docker_img}", hide=True, warn=True)
            if result and result.stdout.strip():
                logging_utils.print_info("Image already exists. Use --force to download.")
                return
        elif output_path.exists():
            logging_utils.print_info(f"File {output_path} already exists. Use --force to download.")
            return

    if force or not output_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _download_file(ctx, url, output_path, filename)
        logging_utils.print_success("Download complete!", Path=str(output_path))
    else:
        logging_utils.print_info(f"Using existing file: {output_path}")

    if load and is_docker_image:
        _load_docker_image(ctx, output_path, settings.original_docker_img)
    elif not is_docker_image:
        logging_utils.print_info(f"Data file downloaded: {output_path}")
