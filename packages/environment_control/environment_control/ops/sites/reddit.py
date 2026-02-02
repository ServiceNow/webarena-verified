"""Reddit (Postmill) environment operations.

Discovered via exploration:
- Process manager: supervisord
- Services: nginx (port 80), php-fpm (port 9000), postgres (port 5432)
- Cleanup paths: cache, logs, node_modules, temp files
- Base URL config: Symfony .env APP_SITE_NAME and PHP/Symfony cache
- Database: PostgreSQL (user=postmill, db=postmill)
"""

from __future__ import annotations

import re
from typing import Any, ClassVar, Optional

from ..base import BaseOps
from ..mixins import SupervisorMixin
from ..types import CommandExecutor, ExecLog, Health, Result, ServiceState


class RedditOps(SupervisorMixin, BaseOps):
    """Operations for Reddit (Postmill) forum environment."""

    # --- Class attributes ---

    expected_services: ClassVar[frozenset[str]] = frozenset(
        {
            "nginx",
            "php-fpm",
            "postgres",
        }
    )

    cleanup_paths: ClassVar[list[str]] = [
        # Symfony application caches
        "/var/www/html/var/cache/*",
        "/var/www/html/var/log/*",
        # Node modules (not needed at runtime)
        "/var/www/html/node_modules",
        # System logs
        "/var/log/*.log",
        "/var/log/*/*.log",
        # Temp files
        "/tmp/*",
    ]

    # --- Site constants ---

    APP_ROOT = "/var/www/html"
    POSTGRES_USER = "postmill"
    POSTGRES_DB = "postmill"

    # --- Subclassed methods (BaseOps abstract implementations) ---

    @classmethod
    def _init(
        cls, exec_cmd: Optional[CommandExecutor] = None, base_url: str = "", dry_run: bool = False, **kwargs: Any
    ) -> Result:
        """Initialize Reddit/Postmill: set site name and clear cache.

        Postmill is a Symfony application. The base URL is configured via
        APP_SITE_NAME in the .env file and requires cache clear.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            base_url: Base URL for the site (e.g., "http://localhost:9999/")
            dry_run: If True, preview changes without applying them.
        """
        if not base_url:
            raise ValueError("base_url is required")

        # Extract hostname from base_url for site name
        # e.g., "http://localhost:9999/" -> "localhost:9999"
        match = re.match(r"https?://([^/]+)", base_url)
        site_name = match.group(1) if match else "localhost"

        commands = [
            # Update APP_SITE_NAME in .env
            f'sed -i "s/^APP_SITE_NAME=.*/APP_SITE_NAME={site_name}/" {cls.APP_ROOT}/.env',
            # Clear Symfony cache to pick up new config
            f"rm -rf {cls.APP_ROOT}/var/cache/*",
        ]

        if dry_run:
            return Result(
                success=True,
                value={
                    "dry_run": True,
                    "base_url": base_url,
                    "site_name": site_name,
                    "commands_to_run": commands,
                    "command_count": len(commands),
                },
                exec_logs=[],
            )

        logs: list[ExecLog] = []
        for cmd in commands:
            returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
            logs.append(ExecLog(cmd, returncode, stdout, stderr))
            if returncode != 0:
                return Result(success=False, exec_logs=logs)

        return Result(success=True, exec_logs=logs)

    @classmethod
    def _start(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Start all supervisord services."""
        return cls.supervisor_start(exec_cmd)

    @classmethod
    def _stop(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Stop all supervisord services."""
        return cls.supervisor_stop(exec_cmd)

    @classmethod
    def _get_health(
        cls, exec_cmd: Optional[CommandExecutor] = None, http_url: Optional[str] = None, **kwargs: Any
    ) -> Result:
        """Site-specific health check for Reddit/Postmill environment.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            http_url: Optional HTTP URL to check.

        Returns:
            Result with Health containing all service states.
            Services use supervisor names (nginx, php-fpm, postgres).
            State is HEALTHY only if process is running AND responding.
        """
        all_logs: list[ExecLog] = []
        services: dict[str, ServiceState] = {}

        # Run each check and collect logs
        checks = [
            cls._check_services(services, exec_cmd),
            cls._check_postgres_health(services, exec_cmd),
        ]

        for result in checks:
            all_logs.extend(result.exec_logs)

        # Optional HTTP check
        if http_url:
            http_result = cls._check_http_health(services, http_url, exec_cmd)
            all_logs.extend(http_result.exec_logs)

        health = Health(services=services)

        return Result(
            success=health.is_healthy,
            value=health,
            exec_logs=all_logs,
        )

    # --- Private helpers ---

    @classmethod
    def _check_services(cls, services: dict[str, ServiceState], exec_cmd: Optional[CommandExecutor] = None) -> Result:
        """Check supervisor services status.

        Args:
            services: Dict to update with service states.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        svc_result = cls.services_running(exec_cmd)
        if svc_result.value:
            services.update(svc_result.value)
        return Result(success=svc_result.success, value=services, exec_logs=svc_result.exec_logs)

    @classmethod
    def _check_postgres(cls, exec_cmd: Optional[CommandExecutor] = None) -> Result:
        """Check if PostgreSQL is ready."""
        cmd = "pg_isready -h localhost"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        ready = returncode == 0
        return Result(
            success=ready,
            value=ready,
            exec_logs=[ExecLog(cmd, returncode, stdout, stderr)],
        )

    @classmethod
    def _check_postgres_health(
        cls, services: dict[str, ServiceState], exec_cmd: Optional[CommandExecutor] = None
    ) -> Result:
        """Upgrade postgres from RUNNING to HEALTHY/UNHEALTHY if responding.

        Args:
            services: Dict to update with service state.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        if services.get("postgres") != ServiceState.RUNNING:
            return Result(success=True, value=services, exec_logs=[])
        result = cls._check_postgres(exec_cmd)
        services["postgres"] = ServiceState.HEALTHY if result.value else ServiceState.UNHEALTHY
        return Result(success=True, value=services, exec_logs=result.exec_logs)

    @classmethod
    def _check_http_health(
        cls, services: dict[str, ServiceState], http_url: str, exec_cmd: Optional[CommandExecutor] = None
    ) -> Result:
        """Check HTTP endpoint and add to services dict.

        Args:
            services: Dict to update with service state.
            http_url: URL to check.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        result = cls._check_http(http_url, exec_cmd)
        services["http"] = ServiceState.HEALTHY if result.value else ServiceState.UNHEALTHY
        return Result(success=True, value=services, exec_logs=result.exec_logs)
