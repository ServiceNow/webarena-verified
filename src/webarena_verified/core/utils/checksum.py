import hashlib
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def compute_evaluator_checksum() -> str:
    """Compute SHA256 hash of all Python files in src/webarena_verified/."""
    hasher = hashlib.sha256()

    # Get the webarena_verified package directory
    package_dir = Path(__file__).parent.parent.parent

    # Sort files for deterministic ordering
    py_files = sorted(package_dir.rglob("*.py"))

    for py_file in py_files:
        hasher.update(py_file.read_bytes())

    return hasher.hexdigest()


def compute_data_file_checksum(file_path: str | Path) -> str:
    """Compute SHA256 hash of a data file.

    Args:
        file_path: Path to the data file

    Returns:
        SHA256 hash of the file as a hexadecimal string

    Raises:
        FileNotFoundError: If the file does not exist
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    return hashlib.sha256(path.read_bytes()).hexdigest()
