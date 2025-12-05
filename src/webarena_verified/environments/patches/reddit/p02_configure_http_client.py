#!/usr/bin/env python3
"""
Configure Reddit (Postmill) Symfony HTTP client to allow localhost and host.docker.internal.

This script modifies the http_client.yaml configuration to whitelist localhost
and host.docker.internal hosts, allowing the Reddit container to fetch metadata
from local GitLab instances.

It also creates a custom HTTP client decorator that rewrites localhost:9999 URLs
to localhost (no port), allowing the container to handle submission URLs that
reference the external port mapping.

Usage:
    As module: apply_patch(handler)
    As script: python p02_configure_http_client.py
"""

import logging
import textwrap

from webarena_verified.environments import SiteInstanceHandler

logger = logging.getLogger(__name__)


def backup_config(handler: SiteInstanceHandler) -> None:
    """Backup the existing HTTP client configuration."""
    config_path = "/var/www/html/config/packages/http_client.yaml"
    backup_path = f"{config_path}.bak"

    handler.exec_cmd(
        ["cp", config_path, backup_path],
        check=True,
    )
    logger.info(f"Backed up config to {backup_path}")


def update_http_client_config(handler: SiteInstanceHandler) -> None:
    """Update HTTP client configuration to allow localhost and host.docker.internal.

    This removes the NoPrivateNetworkHttpClient wrapper entirely to allow
    connections to private IPs like host.docker.internal.

    Also adds a custom HTTP client decorator that rewrites localhost:9999 URLs
    to localhost (no port) to handle same-container URL submissions.
    """

    # New configuration without NoPrivateNetworkHttpClient restriction
    new_config = textwrap.dedent("""
        parameters:
            postmill.http_client.default_user_agent: "Postmill/%env(APP_VERSION)% (https://postmill.xyz)"
            postmill.http_client.external_client_options:
                headers:
                    User-Agent: "%postmill.http_client.default_user_agent%"
                base_uri: null

        services:
            _defaults:
                public: false

            Symfony\\Contracts\\HttpClient\\HttpClientInterface $externalClient: "@postmill.http_client.external_client"

            postmill.http_client.default:
                class: Symfony\\Contracts\\HttpClient\\HttpClientInterface
                factory: ['@Symfony\\Contracts\\HttpClient\\HttpClientInterface', withOptions]
                arguments:
                    - "%postmill.http_client.external_client_options%"

            # Decorator to rewrite localhost:9999 URLs to localhost (same container)
            postmill.http_client.url_rewriter:
                class: App\\HttpClient\\UrlRewritingHttpClient
                arguments: ['@.inner']
                decorates: postmill.http_client.default
                decoration_priority: 10

            # Use the default client directly without NoPrivateNetworkHttpClient wrapper
            postmill.http_client.external_client:
                alias: postmill.http_client.default

            postmill.http_client.external_client.psr18:
                class: Symfony\\Component\\HttpClient\\Psr18Client
                arguments: ['@postmill.http_client.external_client']
        """).strip()

    # Write the new configuration
    config_path = "/var/www/html/config/packages/http_client.yaml"

    # Use exec_cmd with input_data to write the file
    handler.exec_cmd(
        ["tee", config_path],
        input_data=new_config,
        capture_output=True,
        check=True,
    )
    logger.info(f"Updated {config_path} - removed NoPrivateNetworkHttpClient restriction")


def create_url_rewriting_client(handler: SiteInstanceHandler) -> None:
    """Create the UrlRewritingHttpClient PHP class."""

    php_code = textwrap.dedent("""
        <?php

        namespace App\\HttpClient;

        use Symfony\\Contracts\\HttpClient\\HttpClientInterface;
        use Symfony\\Contracts\\HttpClient\\ResponseInterface;
        use Symfony\\Contracts\\HttpClient\\ResponseStreamInterface;

        /**
         * HTTP client decorator that rewrites localhost:9999 URLs to localhost.
         *
         * This allows the Reddit container to handle submission URLs that reference
         * the external port (9999) by rewriting them to the internal address.
         */
        class UrlRewritingHttpClient implements HttpClientInterface
        {
            private HttpClientInterface $client;

            public function __construct(HttpClientInterface $client)
            {
                $this->client = $client;
            }

            public function request(string $method, string $url, array $options = []): ResponseInterface
            {
                // Rewrite localhost:9999 to localhost (internal container address)
                $rewrittenUrl = preg_replace('/^http:\\/\\/localhost:9999\\//', 'http://localhost/', $url);

                return $this->client->request($method, $rewrittenUrl, $options);
            }

            public function stream($responses, float $timeout = null): ResponseStreamInterface
            {
                return $this->client->stream($responses, $timeout);
            }

            public function withOptions(array $options): static
            {
                $clone = clone $this;
                $clone->client = $this->client->withOptions($options);
                return $clone;
            }
        }
        """).strip()

    # Write the PHP class
    class_path = "/var/www/html/src/HttpClient/UrlRewritingHttpClient.php"
    class_dir = "/var/www/html/src/HttpClient"

    # Create directory if it doesn't exist
    handler.exec_cmd(
        ["mkdir", "-p", class_dir],
        check=True,
    )

    # Write the file
    handler.exec_cmd(
        ["tee", class_path],
        input_data=php_code,
        capture_output=True,
        check=True,
    )
    logger.info(f"Created {class_path}")


def clear_symfony_cache(handler: SiteInstanceHandler) -> None:
    """Clear Symfony cache completely and warm up production cache."""
    # Remove all cached files
    handler.exec_cmd(
        ["sh", "-c", "rm -rf /var/www/html/var/cache/*"],
        check=True,
    )
    logger.info("Removed all cached files")

    # Warm up production cache
    handler.exec_cmd(
        ["sh", "-c", "APP_ENV=prod php bin/console cache:warmup"],
        capture_output=True,
        check=True,
    )
    logger.info("Warmed up production cache")


def verify_configuration(handler: SiteInstanceHandler) -> bool:
    """Verify the configuration was applied correctly."""
    result = handler.exec_cmd(
        ["cat", "/var/www/html/config/packages/http_client.yaml"],
        capture_output=True,
        text=True,
        check=True,
    )

    if "alias: postmill.http_client.default" in result.stdout:
        logger.info("Configuration verified successfully")
        return True
    else:
        logger.error("Configuration verification failed")
        return False


def apply_patch(handler: SiteInstanceHandler) -> bool:
    """Apply the HTTP client configuration patch.

    Args:
        handler: SiteInstanceHandler for executing commands

    Returns:
        True if patch was applied successfully, False otherwise
    """
    try:
        logger.info("Configuring Reddit HTTP client to allow localhost and host.docker.internal...")

        # Backup existing configuration
        backup_config(handler)

        # Create URL rewriting HTTP client
        create_url_rewriting_client(handler)

        # Update configuration
        update_http_client_config(handler)

        # Clear cache
        clear_symfony_cache(handler)

        # Verify
        if not verify_configuration(handler):
            logger.error("Patch verification failed")
            return False

        logger.info("HTTP client configuration patch applied successfully")
        return True

    except Exception as e:
        logger.error(f"Error applying patch: {e}")
        return False
