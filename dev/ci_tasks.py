"""CI helper tasks for automated testing."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from invoke import task

if TYPE_CHECKING:
    from invoke.context import Context

from dev.utils import logging_utils
from dev.utils.path_utils import get_repo_root

# CI-specific ZIM file for Wikipedia tests (tiny ~1MB file)
CI_WIKIPEDIA_ZIM_URL = "https://download.kiwix.org/zim/wikipedia/wikipedia_en_ray-charles_maxi_2024-10.zim"
CI_WIKIPEDIA_ZIM_NAME = "wikipedia_en_ray-charles_maxi_2024-10.zim"


@task(name="setup-wikipedia")
@logging_utils.with_banner()
def setup_wikipedia(ctx: Context, output_dir: str | None = None) -> None:
    """Download tiny Wikipedia ZIM file for CI testing.

    Downloads the Ray Charles ZIM (~1MB) instead of the full Wikipedia (~100GB).
    The ZIM file is saved to the output directory for use during Docker build.

    Args:
        output_dir: Directory to save the ZIM file (default: dev/environments/docker/sites/wikipedia/data).
    """
    repo_root = get_repo_root()
    default_dir = repo_root / "dev" / "environments" / "docker" / "sites" / "wikipedia" / "data"
    target_dir = Path(output_dir) if output_dir else default_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    zim_path = target_dir / CI_WIKIPEDIA_ZIM_NAME

    if zim_path.exists():
        logging_utils.print_info(f"ZIM file already exists: {zim_path}")
        return

    logging_utils.print_info("Downloading CI Wikipedia ZIM file...")
    logging_utils.print_info(f"  URL: {CI_WIKIPEDIA_ZIM_URL}")
    logging_utils.print_info(f"  To:  {zim_path}")

    ctx.run(f'curl -L -o "{zim_path}" "{CI_WIKIPEDIA_ZIM_URL}"')

    logging_utils.print_success(f"Downloaded: {zim_path}")


@task(name="build-wikipedia")
@logging_utils.with_banner()
def build_wikipedia(ctx: Context, tag: str = "test") -> None:
    """Build Wikipedia Docker image for CI with embedded tiny ZIM.

    Downloads the tiny ZIM if needed, then builds a Docker image with the
    ZIM file baked in for fast CI testing.

    Args:
        tag: Image tag (default: test).
    """
    repo_root = get_repo_root()
    data_dir = repo_root / "dev" / "environments" / "docker" / "sites" / "wikipedia" / "data"
    zim_path = data_dir / CI_WIKIPEDIA_ZIM_NAME

    # Download ZIM if not present
    if not zim_path.exists():
        setup_wikipedia(ctx)

    # Build with the CI Dockerfile
    dockerfile = repo_root / "dev" / "environments" / "docker" / "sites" / "wikipedia" / "Dockerfile.ci"
    image_name = f"am1n3e/webarena-verified-wikipedia:{tag}"

    logging_utils.print_info(f"Building {image_name} with CI ZIM...")
    ctx.run(f'docker build -t {image_name} -f "{dockerfile}" "{repo_root}"')

    logging_utils.print_success(f"Built: {image_name}")
