"""File lock helpers for dev scripts."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from filelock import FileLock

if TYPE_CHECKING:
    from collections.abc import Iterator


def lock_path_for(target_path: Path) -> Path:
    """Return the lock-file path used to guard writes to ``target_path``.

    Example:
        >>> lock_path_for(Path("a/b/data.json"))
        PosixPath('a/b/data.json.lock')
    """
    return target_path.with_suffix(f"{target_path.suffix}.lock")


@contextmanager
def guarded_file_lock(target_path: Path, timeout_seconds: float = 30.0) -> Iterator[None]:
    """Acquire a lock dedicated to one target file.

    Args:
        target_path: File path whose writes should be serialized.
        timeout_seconds: Max time to wait for lock acquisition.

    Example:
        >>> with guarded_file_lock(Path("leaderboard/data/submissions/pending/sub-1.json")):
        ...     pass
    """
    lock_path = lock_path_for(target_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(lock_path), timeout=timeout_seconds)
    with lock:
        yield


@contextmanager
def guarded_file_locks(target_paths: list[Path], timeout_seconds: float = 30.0) -> Iterator[None]:
    """Acquire multiple file locks in deterministic order.

    Sorting lock paths prevents deadlocks when two processes request the same
    locks in different call-site orders.

    Args:
        target_paths: Paths that must be updated atomically as one operation.
        timeout_seconds: Max time to wait per lock acquisition.

    Example:
        >>> paths = [Path("processed/sub-1.json"), Path("pending/sub-1.json")]
        >>> with guarded_file_locks(paths):
        ...     pass
    """
    unique_targets = sorted(set(target_paths))
    locks = [FileLock(str(lock_path_for(path)), timeout=timeout_seconds) for path in unique_targets]
    for lock in locks:
        Path(lock.lock_file).parent.mkdir(parents=True, exist_ok=True)
        lock.acquire()
    try:
        yield
    finally:
        for lock in reversed(locks):
            lock.release()
