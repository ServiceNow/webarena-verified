"""Docker operations for volume setup and data management.

This module provides low-level operations for Docker volume management,
file downloads, and tar extraction used during site setup.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path  # noqa: TC003 - Path is used at runtime


def volume_exists(name: str) -> bool:
    """Check if Docker volume exists.

    Args:
        name: Volume name to check.

    Returns:
        True if volume exists, False otherwise.
    """
    result = subprocess.run(
        ["docker", "volume", "ls", "-q", "-f", f"name=^{name}$"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def volume_is_empty(name: str) -> bool:
    """Check if Docker volume is empty (has no files).

    Args:
        name: Volume name to check.

    Returns:
        True if volume is empty, False if it has content.
    """
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{name}:/vol:ro",
            "alpine",
            "sh",
            "-c",
            "ls -A /vol | head -1",
        ],
        capture_output=True,
        text=True,
    )
    return not bool(result.stdout.strip())


def create_volume(name: str) -> bool:
    """Create Docker volume if it doesn't exist.

    Args:
        name: Volume name to create.

    Returns:
        True if volume was created, False if it already existed.
    """
    if volume_exists(name):
        return False

    result = subprocess.run(
        ["docker", "volume", "create", name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create volume {name}: {result.stderr}")
    return True


def remove_volume(name: str) -> bool:
    """Remove Docker volume if it exists.

    Args:
        name: Volume name to remove.

    Returns:
        True if volume was removed, False if it didn't exist.

    Raises:
        RuntimeError: If volume is in use or removal fails.
    """
    if not volume_exists(name):
        return False

    result = subprocess.run(
        ["docker", "volume", "rm", name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to remove volume {name}: {result.stderr}")
    return True


def list_volumes(prefix: str) -> list[str]:
    """List all Docker volumes with the given prefix.

    Args:
        prefix: Volume name prefix to filter by.

    Returns:
        List of volume names matching the prefix.
    """
    result = subprocess.run(
        ["docker", "volume", "ls", "-q", "-f", f"name={prefix}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [v for v in result.stdout.strip().split("\n") if v]


def download_file(url: str, output_dir: Path, filename: str | None = None) -> Path:
    """Download a file using the best available tool.

    Prefers aria2c for parallel downloads, falls back to wget or curl.

    Args:
        url: URL to download from.
        output_dir: Directory to save the file.
        filename: Optional filename override. If None, uses filename from URL.

    Returns:
        Path to the downloaded file.

    Raises:
        RuntimeError: If no download tool is available or download fails.
    """
    if filename is None:
        filename = url.rsplit("/", 1)[-1]

    output_path = output_dir / filename
    output_dir.mkdir(parents=True, exist_ok=True)

    if shutil.which("aria2c"):
        cmd = [
            "aria2c",
            "-x",
            "16",
            "-s",
            "16",
            "--file-allocation=none",
            "-d",
            str(output_dir),
            "-o",
            filename,
            url,
        ]
        tool = "aria2c"
    elif shutil.which("wget"):
        cmd = ["wget", "-O", str(output_path), url]
        tool = "wget"
    elif shutil.which("curl"):
        cmd = ["curl", "-L", "-o", str(output_path), url]
        tool = "curl"
    else:
        raise RuntimeError("No download tool available. Install aria2c, wget, or curl.")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"Download with {tool} failed for {url}")

    return output_path


def download_with_aria2c_container(urls: list[str], data_dir: Path) -> None:
    """Download files using aria2c in an Alpine container.

    This is useful when aria2c is not installed on the host system.
    Uses 16 parallel connections for faster downloads.

    Args:
        urls: List of URLs to download.
        data_dir: Directory to save downloaded files.

    Raises:
        RuntimeError: If download fails.
    """
    data_dir.mkdir(parents=True, exist_ok=True)

    for url in urls:
        filename = url.rsplit("/", 1)[-1]
        output_path = data_dir / filename

        if output_path.exists():
            continue

        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{data_dir}:/data",
            "alpine",
            "sh",
            "-c",
            f'apk add --no-cache aria2 && aria2c -x 16 -s 16 --file-allocation=none -d /data -o {filename} "{url}"',
        ]

        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to download {url}")


def extract_tar_to_volume(
    tar_file: Path,
    volume_name: str,
    extract_path: str | None = None,
    strip_components: int = 0,
) -> None:
    """Extract tar contents to a Docker volume.

    Uses an Alpine container to perform the extraction.

    Args:
        tar_file: Path to the tar file on the host.
        volume_name: Name of the target Docker volume.
        extract_path: Optional path within tar to extract. If None, extracts all.
        strip_components: Number of leading path components to strip.

    Raises:
        RuntimeError: If extraction fails.
    """
    tar_dir = tar_file.parent
    tar_name = tar_file.name

    # Build tar extraction command
    tar_cmd = f"tar -xf /tar/{tar_name}"
    if strip_components > 0:
        tar_cmd += f" --strip-components={strip_components}"
    tar_cmd += " -C /vol"
    if extract_path:
        tar_cmd += f" {extract_path}"

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{tar_dir}:/tar:ro",
        "-v",
        f"{volume_name}:/vol",
        "alpine",
        "sh",
        "-c",
        tar_cmd,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to extract {tar_file} to volume {volume_name}: {result.stderr}")


def copy_file_to_volume(file_path: Path, volume_name: str, dest_path: str = ".") -> None:
    """Copy a file from host to a Docker volume.

    Uses an Alpine container to perform the copy.

    Args:
        file_path: Path to the file on the host.
        volume_name: Name of the target Docker volume.
        dest_path: Destination path within the volume (default: root).

    Raises:
        RuntimeError: If copy fails.
    """
    file_dir = file_path.parent
    file_name = file_path.name

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{file_dir}:/src:ro",
        "-v",
        f"{volume_name}:/vol",
        "alpine",
        "cp",
        f"/src/{file_name}",
        f"/vol/{dest_path}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to copy {file_path} to volume {volume_name}: {result.stderr}")


__all__ = [
    "copy_file_to_volume",
    "create_volume",
    "download_file",
    "download_with_aria2c_container",
    "extract_tar_to_volume",
    "list_volumes",
    "remove_volume",
    "volume_exists",
    "volume_is_empty",
]
