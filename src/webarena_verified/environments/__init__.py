"""WebArena environment management utilities and patches."""

from .site_handler import SiteInstanceHandler

MAGENTO_ADMIN_AUTO_LOGIN_HEADER = "X-M2-Admin-Auto-Login"

__all__ = ["SiteInstanceHandler", "MAGENTO_ADMIN_AUTO_LOGIN_HEADER"]
