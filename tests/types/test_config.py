"""Tests for WebArenaVerifiedConfig URL rendering and derendering with sites parameter."""

import pytest

from webarena_verified.types.config import WebArenaVerifiedConfig
from webarena_verified.types.task import WebArenaSite


def test_render_url_success():
    """Verify render_url with single site in list renders correctly."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {"urls": ["http://localhost:7770"]},
                "shopping_admin": {"urls": ["http://localhost:7780/admin"]},
                "reddit": {"urls": ["http://localhost:9999"]},
            }
        }
    )

    # Single site for SHOPPING_ADMIN
    result = config.render_url("__SHOPPING_ADMIN__/sales/", sites=[WebArenaSite.SHOPPING_ADMIN])
    assert result == "http://localhost:7780/admin/sales/"

    # Single site for SHOPPING
    result = config.render_url("__SHOPPING__/products", sites=[WebArenaSite.SHOPPING])
    assert result == "http://localhost:7770/products"


def test_render_url_multiple_sites():
    """Verify render_url tries multiple sites in order."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {"urls": ["http://localhost:7770"]},
                "shopping_admin": {"urls": ["http://localhost:7780/admin"]},
                "reddit": {"urls": ["http://localhost:9999"]},
            }
        }
    )

    # Try multiple sites - should match SHOPPING_ADMIN
    result = config.render_url(
        "__SHOPPING_ADMIN__/sales/", sites=[WebArenaSite.SHOPPING, WebArenaSite.SHOPPING_ADMIN, WebArenaSite.REDDIT]
    )
    assert result == "http://localhost:7780/admin/sales/"

    # Try multiple sites - should match REDDIT
    result = config.render_url("__REDDIT__/posts", sites=[WebArenaSite.SHOPPING, WebArenaSite.REDDIT])
    assert result == "http://localhost:9999/posts"


def test_render_url_strict_false():
    """Verify render_url with strict=False returns original when no match."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {"urls": ["http://localhost:7770"]},
                "reddit": {"urls": ["http://localhost:9999"]},
            }
        }
    )

    # No site matches - should return original
    result = config.render_url("__SHOPPING_ADMIN__/sales/", sites=[WebArenaSite.SHOPPING], strict=False)
    assert result == "__SHOPPING_ADMIN__/sales/"


def test_render_url_strict_true_fail():
    """Verify render_url with strict=True raises when no site matches."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {"urls": ["http://localhost:7770"]},
            }
        }
    )

    with pytest.raises(ValueError, match="No site in .* matched template"):
        config.render_url("__REDDIT__/posts", sites=[WebArenaSite.SHOPPING], strict=True)


def test_render_url_fail_site_not_found():
    """Verify ValueError is raised when site is not in environments."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {"urls": ["http://localhost:7770"]},
            }
        }
    )

    with pytest.raises(ValueError, match="Sites .* not found in environments"):
        config.render_url("__REDDIT__/posts", sites=[WebArenaSite.REDDIT])


@pytest.mark.parametrize(
    "method_name,url_or_template,sites",
    [
        ("render_url", "__REDDIT__/posts", [WebArenaSite.REDDIT]),
        ("derender_url", "http://localhost:9999/posts", [WebArenaSite.REDDIT]),
    ],
)
def test_fail_site_not_found(method_name, url_or_template, sites):
    """Verify ValueError is raised when site is not in environments."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {"urls": ["http://localhost:7770"]},
            }
        }
    )

    method = getattr(config, method_name)
    with pytest.raises(ValueError, match="Sites .* not found in environments"):
        method(url_or_template, sites=sites)


def test_url_list_success():
    """Verify methods work with list of URLs."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {"urls": ["http://localhost:7770"]},
                "reddit": {"urls": ["http://localhost:9999"]},
            }
        }
    )

    # render_url with multiple URL templates - partial match with strict=False
    urls = ["__SHOPPING__/products", "__REDDIT__/posts"]
    result = config.render_url(urls, sites=[WebArenaSite.SHOPPING], strict=False)
    assert isinstance(result, list)
    assert result == ["http://localhost:7770/products", "__REDDIT__/posts"]

    # derender_url with multiple URLs from same site
    urls = ["http://localhost:7770/products", "http://localhost:7770/cart"]
    result = config.derender_url(urls, sites=[WebArenaSite.SHOPPING])
    assert isinstance(result, list)
    assert result == ["__SHOPPING__/products", "__SHOPPING__/cart"]


def test_derender_url_success():
    """Verify derender_url with single site in list derenders correctly."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {"urls": ["http://localhost:7770"]},
                "shopping_admin": {"urls": ["http://localhost:7780/admin"]},
            }
        }
    )

    result = config.derender_url("http://localhost:7780/admin/sales/", sites=[WebArenaSite.SHOPPING_ADMIN])
    assert result == "__SHOPPING_ADMIN__/sales/"


def test_derender_url_multiple_sites():
    """Verify derender_url tries multiple sites by specificity."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {"urls": ["http://localhost:7780"]},
                "shopping_admin": {"urls": ["http://localhost:7780/admin"]},
            }
        }
    )

    # Should match SHOPPING_ADMIN (more specific URL) even though both could match
    result = config.derender_url(
        "http://localhost:7780/admin/users", sites=[WebArenaSite.SHOPPING, WebArenaSite.SHOPPING_ADMIN]
    )
    assert result == "__SHOPPING_ADMIN__/users"


def test_derender_url_strict_false():
    """Verify derender_url with strict=False returns original when no match."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {"urls": ["http://localhost:7770"]},
                "shopping_admin": {"urls": ["http://localhost:7780/admin"]},
            }
        }
    )

    # URL doesn't match SHOPPING - should return original
    result = config.derender_url("http://localhost:7780/admin/sales/", sites=[WebArenaSite.SHOPPING], strict=False)
    assert result == "http://localhost:7780/admin/sales/"


@pytest.mark.parametrize(
    "url,sites,error_match",
    [
        (
            "http://localhost:7780/admin/sales/",
            [WebArenaSite.SHOPPING],
            "does not match any configured URLs for sites",
        ),
        (
            ["http://localhost:7770/products", "http://localhost:7780/admin/sales/"],
            [WebArenaSite.SHOPPING],
            "does not match any configured URLs for sites",
        ),
    ],
)
def test_derender_url_strict_true_fail(url, sites, error_match):
    """Verify ValueError is raised when URL doesn't match and strict=True."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {"urls": ["http://localhost:7770"]},
                "shopping_admin": {"urls": ["http://localhost:7780/admin"]},
            }
        }
    )

    with pytest.raises(ValueError, match=error_match):
        config.derender_url(url, sites=sites, strict=True)


def test_active_url_idx():
    """Verify url_idx works correctly with sites parameter."""
    config = WebArenaVerifiedConfig.model_validate(
        {
            "environments": {
                "shopping": {
                    "urls": ["http://prod.example.com", "http://staging.example.com"],
                    "active_url_idx": 0,
                },
            }
        }
    )

    # Use default (active_url_idx=0)
    result = config.render_url("__SHOPPING__/products", sites=[WebArenaSite.SHOPPING])
    assert result == "http://prod.example.com/products"

    # Explicitly use url_idx=1
    result = config.render_url("__SHOPPING__/products", sites=[WebArenaSite.SHOPPING], url_idx=1)
    assert result == "http://staging.example.com/products"


def test_active_url_idx_auto_initialization():
    """Verify active_url_idx is automatically set to 0 when not specified."""
    from webarena_verified.types.config import EnvironmentConfig

    # When urls list is not empty and active_url_idx is not specified
    env = EnvironmentConfig(urls=["http://example.com", "http://staging.example.com"])
    assert env.active_url_idx == 0  # Should be auto-initialized to 0
    assert env.active_url == "http://example.com"

    # When urls list is empty
    env_empty = EnvironmentConfig(urls=[])
    assert env_empty.active_url_idx is None  # Should remain None
    assert env_empty.active_url is None
