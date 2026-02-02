"""WebArena environment management utilities."""

from .site_handler import SiteInstanceHandler

MAGENTO_ADMIN_AUTO_LOGIN_HEADER = "X-M2-Admin-Auto-Login"

__all__ = [
    "MAGENTO_ADMIN_AUTO_LOGIN_HEADER",
    "SiteInstanceHandler",
    # Re-export subpackages for convenient access
    "container",
    "env_ctrl_client",
    "setup",
]
