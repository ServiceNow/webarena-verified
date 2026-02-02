"""WebArena Verified - Benchmark for web navigation agents"""

import warnings

warnings.filterwarnings("ignore", message="invalid escape sequence", module="geocoder")

from webarena_verified.api.webarena_verified import WebArenaVerified  # noqa: E402
from webarena_verified.core.utils import logger  # noqa: E402

__all__ = ["WebArenaVerified", "logger"]
