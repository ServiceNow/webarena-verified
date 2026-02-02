"""Shopping Admin environment operations.

Extends BaseOps with Magento/MySQL/Elasticsearch-specific functionality.
"""

from __future__ import annotations

import logging
import os
from typing import Any, ClassVar, Optional

from ..base import BaseOps
from ..mixins import SupervisorMixin
from ..types import CommandExecutor, ExecLog, Health, Result, ServiceState


class ShoppingAdminOps(SupervisorMixin, BaseOps):
    """Operations for Shopping Admin (Magento) environment."""

    # --- Class attributes ---

    # NOTE: elasticsearch removed - too slow under Rosetta emulation on ARM64
    expected_services: ClassVar[frozenset[str]] = frozenset(
        {
            "cron",
            # "elasticsearch",
            "mailcatcher",
            "mysqld",
            "nginx",
            "php-fpm",
            "redis-server",
        }
    )

    cleanup_paths: ClassVar[list[str]] = [
        # Elasticsearch logs
        "/usr/share/java/elasticsearch/logs/*",
        # Magento logs and caches
        "/var/www/magento2/var/log/*",
        "/var/www/magento2/var/cache/*",
        "/var/www/magento2/var/page_cache/*",
        "/var/www/magento2/var/session/*",
        "/var/www/magento2/var/view_preprocessed/*",
        "/var/www/magento2/generated/*",
        "/var/www/magento2/dev/tests",
        # Composer cache
        "/root/.composer/cache/*",
        "/var/www/.composer/cache/*",
        # System package manager caches
        "/var/cache/apt/archives/*",
        "/var/lib/apt/lists/*",
        # Service logs
        "/var/log/mysql/*",
        "/var/log/nginx/*",
        "/var/log/*.log",
        "/var/log/*/*.log",
        # Temp files
        "/tmp/*.log",
        "/tmp/magento*",
    ]

    # --- Site constants ---

    MAGENTO_ROOT = "/var/www/magento2"
    MAILCATCHER_URL = "http://localhost:88"
    SUPERVISOR_SOCKET = "/run/supervisord.sock"
    ENTRYPOINT_CMD = "/docker-entrypoint.sh supervisord -n -j /supervisord.pid"

    # Database credentials for test/development instance only.
    # DO NOT use these credentials in a production environment.
    DATABASE = "magentodb"
    MYSQL_USER = "magentouser"
    MYSQL_PASSWORD = "MyPassword"

    # --- Subclassed methods (BaseOps abstract implementations) ---

    @classmethod
    def _init(
        cls, exec_cmd: Optional[CommandExecutor] = None, base_url: str = "", dry_run: bool = False, **kwargs: Any
    ) -> Result:
        """Initialize Shopping Admin: set base URL, disable password policies, flush cache.

        Fails fast on first error. Retry is handled by init().

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            base_url: Base URL for Magento (e.g., "http://localhost:6680/").
                      Falls back to WA_ENV_CTRL_EXTERNAL_SITE_URL env var if not provided.
            dry_run: If True, preview changes without applying them.
        """
        # Get base_url from env var if not provided
        if not base_url:
            base_url = os.environ.get("WA_ENV_CTRL_EXTERNAL_SITE_URL", "")
        if not base_url:
            raise ValueError("base_url is required (set WA_ENV_CTRL_EXTERNAL_SITE_URL or pass --base-url)")

        # NOTE: SQL uses escaped double quotes to avoid quote issues with docker exec bash -c '...'
        commands = [
            f'php {cls.MAGENTO_ROOT}/bin/magento setup:store-config:set --base-url="{base_url}"',
            f"mysql -u {cls.MYSQL_USER} -p{cls.MYSQL_PASSWORD} {cls.DATABASE} -e "
            f'"UPDATE core_config_data SET value = \\"{base_url}\\" WHERE path = \\"web/secure/base_url\\";"',
            f"php {cls.MAGENTO_ROOT}/bin/magento config:set admin/security/password_is_forced 0",
            f"php {cls.MAGENTO_ROOT}/bin/magento config:set admin/security/password_lifetime 0",
            f"php {cls.MAGENTO_ROOT}/bin/magento cache:flush",
        ]

        if dry_run:
            return Result(
                success=True,
                value={
                    "dry_run": True,
                    "base_url": base_url,
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
                # Fail fast
                return Result(success=False, exec_logs=logs)

        return Result(success=True, exec_logs=logs)

    @classmethod
    def _start(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Start all supervisord services.

        If supervisord is not running (e.g., container started with custom cmd),
        runs the entrypoint first to start it.
        """
        all_logs: list[ExecLog] = []

        # Ensure supervisord is running (start via entrypoint if needed)
        entrypoint_result = cls._run_entrypoint(exec_cmd=exec_cmd)
        all_logs.extend(entrypoint_result.exec_logs)

        if not entrypoint_result.success:
            return Result(success=False, exec_logs=all_logs)

        # Now start all services
        start_result = cls.supervisor_start(exec_cmd)
        all_logs.extend(start_result.exec_logs)

        return Result(success=start_result.success, exec_logs=all_logs)

    @classmethod
    def _stop(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Stop all supervisord services."""
        return cls.supervisor_stop(exec_cmd)

    @classmethod
    def _run_entrypoint(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Run entrypoint to start supervisord if not already running.

        Used when container was started with a non-default command (e.g., /bin/bash)
        and supervisord is not running. Waits for supervisord to become ready.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with success=True if supervisor already running or entrypoint started
            and supervisord is ready.
        """
        logger = logging.getLogger(__name__)
        all_logs: list[ExecLog] = []

        # Check if supervisor is already running
        check_result = cls.is_supervisor_running(cls.SUPERVISOR_SOCKET, exec_cmd)
        all_logs.extend(check_result.exec_logs)

        if check_result.success:
            logger.debug("Supervisord already running (socket: %s)", cls.SUPERVISOR_SOCKET)
            return Result(success=True, value={"already_running": True}, exec_logs=all_logs)

        # Supervisor not running - start via entrypoint in background
        logger.info("Supervisord not running, starting via entrypoint...")
        # Run in background since supervisord -n blocks
        cmd = f"nohup {cls.ENTRYPOINT_CMD} > /dev/null 2>&1 &"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        all_logs.append(ExecLog(cmd, returncode, stdout, stderr))

        if returncode != 0:
            return Result(success=False, exec_logs=all_logs)

        # Wait for supervisord to become ready
        wait_result = cls.wait_for_supervisord(exec_cmd=exec_cmd)
        all_logs.extend(wait_result.exec_logs)

        return Result(
            success=wait_result.success,
            value={"already_running": False, "started": wait_result.success},
            exec_logs=all_logs,
        )

    @classmethod
    def _get_health(
        cls, exec_cmd: Optional[CommandExecutor] = None, http_url: Optional[str] = None, **kwargs: Any
    ) -> Result:
        """Site-specific health check for Shopping Admin environment.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            http_url: Optional HTTP URL to check.

        Returns:
            Result with Health containing all service states.
            Services use supervisor names (mysqld, elasticsearch, etc.).
            State is HEALTHY only if process is running AND responding.
        """
        all_logs: list[ExecLog] = []
        services: dict[str, ServiceState] = {}

        # Run each check and collect logs
        # NOTE: ES check commented out - too slow under Rosetta emulation on ARM64
        checks = [
            cls._check_services(services, exec_cmd),
            cls._check_mysqld_health(services, exec_cmd),
            # cls._check_elasticsearch_health(services, exec_cmd),
            cls._check_redis_health(services, exec_cmd),
            cls._check_mailcatcher_health(services, exec_cmd),
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
    def _check_mysql(cls, exec_cmd: Optional[CommandExecutor] = None) -> Result:
        """Check if MySQL is ready."""
        cmd = f"mysqladmin ping -u {cls.MYSQL_USER} -p{cls.MYSQL_PASSWORD}"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        ready = returncode == 0 and "alive" in stdout.lower()
        return Result(
            success=ready,
            value=ready,
            exec_logs=[ExecLog(cmd, returncode, stdout, stderr)],
        )

    @classmethod
    def _check_mysqld_health(
        cls, services: dict[str, ServiceState], exec_cmd: Optional[CommandExecutor] = None
    ) -> Result:
        """Upgrade mysqld from RUNNING to HEALTHY/UNHEALTHY if responding.

        Args:
            services: Dict to update with service state.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        if services.get("mysqld") != ServiceState.RUNNING:
            return Result(success=True, value=services, exec_logs=[])
        result = cls._check_mysql(exec_cmd)
        services["mysqld"] = ServiceState.HEALTHY if result.value else ServiceState.UNHEALTHY
        return Result(success=True, value=services, exec_logs=result.exec_logs)

    @classmethod
    def _check_redis(cls, exec_cmd: Optional[CommandExecutor] = None) -> Result:
        """Check if Redis is ready."""
        cmd = "redis-cli ping"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        ready = returncode == 0 and "PONG" in stdout.upper()
        return Result(
            success=ready,
            value=ready,
            exec_logs=[ExecLog(cmd, returncode, stdout, stderr)],
        )

    @classmethod
    def _check_redis_health(
        cls, services: dict[str, ServiceState], exec_cmd: Optional[CommandExecutor] = None
    ) -> Result:
        """Upgrade redis-server from RUNNING to HEALTHY/UNHEALTHY if responding.

        Args:
            services: Dict to update with service state.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        if services.get("redis-server") != ServiceState.RUNNING:
            return Result(success=True, value=services, exec_logs=[])
        result = cls._check_redis(exec_cmd)
        services["redis-server"] = ServiceState.HEALTHY if result.value else ServiceState.UNHEALTHY
        return Result(success=True, value=services, exec_logs=result.exec_logs)

    @classmethod
    def _check_mailcatcher(cls, exec_cmd: Optional[CommandExecutor] = None) -> Result:
        """Check if Mailcatcher HTTP interface is ready (port 88)."""
        return cls._check_http(f"{cls.MAILCATCHER_URL}/", exec_cmd)

    @classmethod
    def _check_mailcatcher_health(
        cls, services: dict[str, ServiceState], exec_cmd: Optional[CommandExecutor] = None
    ) -> Result:
        """Upgrade mailcatcher from RUNNING to HEALTHY/UNHEALTHY if responding.

        Args:
            services: Dict to update with service state.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        if services.get("mailcatcher") != ServiceState.RUNNING:
            return Result(success=True, value=services, exec_logs=[])
        result = cls._check_mailcatcher(exec_cmd)
        services["mailcatcher"] = ServiceState.HEALTHY if result.value else ServiceState.UNHEALTHY
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
