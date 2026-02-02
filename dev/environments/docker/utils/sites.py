"""Site-related helpers for Docker tasks."""

from __future__ import annotations

from dev.environments.settings import BaseSiteSettings, get_settings
from webarena_verified.types.task import WebArenaSite

# Sites that support Docker operations
_DOCKER_SITES: frozenset[WebArenaSite] = frozenset(
    {
        WebArenaSite.SHOPPING,
        WebArenaSite.SHOPPING_ADMIN,
        WebArenaSite.REDDIT,
        WebArenaSite.GITLAB,
        WebArenaSite.WIKIPEDIA,
        WebArenaSite.MAP,
    }
)


def _list_sites() -> list[str]:
    """List all available site names."""
    return sorted(site.value for site in _DOCKER_SITES)


def _get_site_settings(site: str) -> BaseSiteSettings:
    """Get settings for a site, validating it exists."""
    available = _list_sites()
    if site not in available:
        raise ValueError(f"Unknown site '{site}'. Available: {', '.join(available)}")
    return getattr(get_settings(), site)


def _get_container_name(site: str) -> str:
    """Get container name for a site.

    Args:
        site: Site name (e.g., 'shopping_admin').

    Returns:
        Container name in format 'webarena-verified-<site>'.
    """
    return f"webarena-verified-{site}"
