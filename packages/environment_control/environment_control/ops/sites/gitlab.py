"""GitLab environment operations.

Discovered via exploration:
- Process manager: gitlab-ctl (runsvdir/runit)
- Services: postgresql, redis, puma, nginx, gitaly, gitlab-workhorse, sidekiq, etc.
- Cleanup paths: logs, prometheus data, tmp files, package caches
- Base URL config: Update external_url in /etc/gitlab/gitlab.rb + gitlab-ctl reconfigure

Image size breakdown (77.6GB original):
- /var/opt/gitlab/git-data/repositories = 13GB (git data - keep)
- /var/opt/gitlab/postgresql/data = 12GB (database - keep)
- /var/opt/gitlab/gitlab-rails/uploads = 3.4GB (uploads - keep)
- /var/opt/gitlab/prometheus/data = 1.9GB (can clean)
- /opt/gitlab/embedded = 2.7GB (binaries - keep)
"""

from __future__ import annotations

import os
from typing import Any, ClassVar

from ..base import BaseOps
from ..types import CommandExecutor, ExecLog, Health, Result, ServiceState


class GitlabOps(BaseOps):
    """Operations for GitLab environment.

    GitLab uses gitlab-ctl (runsvdir/runit) for service management.
    Services are managed via `gitlab-ctl start/stop/status` commands.
    """

    # ===========================================
    # Services discovered from gitlab-ctl status
    # ===========================================
    # Note: logrotate excluded - it's a periodic task, not a continuous service
    expected_services: ClassVar[frozenset[str]] = frozenset(
        {
            "alertmanager",
            "gitaly",
            "gitlab-exporter",
            "gitlab-kas",
            "gitlab-workhorse",
            "nginx",
            "postgres-exporter",
            "postgresql",
            "prometheus",
            "puma",
            "redis",
            "redis-exporter",
            "sidekiq",
            "sshd",
        }
    )

    # ===========================================
    # Cleanup paths for image optimization
    # ===========================================
    cleanup_paths: ClassVar[list[str]] = [
        # GitLab logs
        "/var/log/gitlab/*/*.log",
        "/var/log/gitlab/*/*/*.log",
        # System logs
        "/var/log/*.log",
        "/var/log/*/*.log",
        # Prometheus data (monitoring - not needed for testing)
        "/var/opt/gitlab/prometheus/data/*",
        # GitLab tmp/cache
        "/var/opt/gitlab/gitlab-rails/shared/tmp/*",
        "/var/opt/gitlab/gitlab-rails/shared/cache/*",
        # Backups
        "/var/opt/gitlab/backups/*",
        # Package caches
        "/var/cache/apt/archives/*",
        "/var/lib/apt/lists/*",
        # Temp files
        "/tmp/*",
    ]

    # ===========================================
    # Site constants
    # ===========================================
    GITLAB_CONFIG = "/etc/gitlab/gitlab.rb"
    DEFAULT_PORT = 8023

    # ===========================================
    # Subclassed methods (BaseOps implementations)
    # ===========================================

    @classmethod
    def _init(
        cls, exec_cmd: CommandExecutor | None = None, base_url: str = "", dry_run: bool = False, **kwargs: Any
    ) -> Result:
        """Initialize GitLab with base URL.

        Updates external_url in gitlab.rb and runs gitlab-ctl reconfigure.
        Note: reconfigure can take several minutes.

        If WA_ENV_CTRL_SKIP_RECONFIGURE=true, skips reconfigure to avoid 502 errors.
        This is useful when the image is pre-configured with the correct external_url.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            base_url: Base URL for GitLab (e.g., "http://localhost:8023")
            dry_run: If True, preview changes without applying them.
        """
        if not base_url:
            raise ValueError("base_url is required")

        # Check if reconfigure should be skipped
        skip_reconfigure = os.environ.get("WA_ENV_CTRL_SKIP_RECONFIGURE", "").lower() == "true"

        if skip_reconfigure:
            return Result(
                success=True,
                value={"message": "Skipped reconfigure (WA_ENV_CTRL_SKIP_RECONFIGURE=true)"},
                exec_logs=[],
            )

        commands = [
            f"sed -i \"s|^external_url.*|external_url '{base_url}'|\" {cls.GITLAB_CONFIG}",
            "gitlab-ctl reconfigure",
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
                return Result(success=False, exec_logs=logs)

        return Result(success=True, exec_logs=logs)

    @classmethod
    def _start(cls, exec_cmd: CommandExecutor | None = None, **kwargs: Any) -> Result:
        """Start all GitLab services via gitlab-ctl.

        Note: The container entrypoint runs /assets/wrapper which handles runsvdir
        startup and gitlab-ctl reconfigure. This method just ensures services are
        started if they're not already running.
        """
        all_logs: list[ExecLog] = []

        # Check current service status
        cmd = "gitlab-ctl status"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        all_logs.append(ExecLog(cmd, returncode, stdout, stderr))

        # If runsv not running, the container isn't ready yet (wrapper still starting)
        # Return success=True to let the wait loop poll until ready
        if "runsv not running" in stdout or "runsv not running" in stderr:
            return Result(success=True, exec_logs=all_logs)

        # Count running services
        running_count = stdout.count("run:")
        expected_count = len(cls.expected_services)

        # If most services are running, consider startup successful
        if running_count >= expected_count * 0.8:  # 80% threshold
            return Result(success=True, exec_logs=all_logs)

        # Some services are down, try to start them
        cmd = "gitlab-ctl start"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        all_logs.append(ExecLog(cmd, returncode, stdout, stderr))

        return Result(
            success=returncode == 0,
            exec_logs=all_logs,
        )

    @classmethod
    def _stop(cls, exec_cmd: CommandExecutor | None = None, **kwargs: Any) -> Result:
        """Stop all GitLab services via gitlab-ctl."""
        cmd = "gitlab-ctl stop"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        return Result(
            success=returncode == 0,
            exec_logs=[ExecLog(cmd, returncode, stdout, stderr)],
        )

    @classmethod
    def _get_health(cls, exec_cmd: CommandExecutor | None = None, http_url: str | None = None, **kwargs: Any) -> Result:
        """Check all GitLab services are healthy.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            http_url: Optional HTTP URL to check. Defaults to localhost:{DEFAULT_PORT}.

        Returns:
            Result with Health containing all service states.
        """
        all_logs: list[ExecLog] = []
        services: dict[str, ServiceState] = {}

        # Check gitlab-ctl status for all services
        svc_result = cls._check_gitlab_services(exec_cmd)
        if svc_result.value:
            services.update(svc_result.value)
        all_logs.extend(svc_result.exec_logs)

        # Additional health checks for core services
        if services.get("postgresql") == ServiceState.RUNNING:
            result = cls._check_postgresql(exec_cmd)
            all_logs.extend(result.exec_logs)
            services["postgresql"] = ServiceState.HEALTHY if result.value else ServiceState.UNHEALTHY

        if services.get("redis") == ServiceState.RUNNING:
            result = cls._check_redis(exec_cmd)
            all_logs.extend(result.exec_logs)
            services["redis"] = ServiceState.HEALTHY if result.value else ServiceState.UNHEALTHY

        # Check env-ctrl if enabled (custom runit service, not in gitlab-ctl)
        if cls._is_env_ctrl_enabled():
            result = cls._check_env_ctrl(exec_cmd)
            all_logs.extend(result.exec_logs)
            services["env-ctrl"] = ServiceState.HEALTHY if result.value else ServiceState.UNHEALTHY

        # HTTP check - verify GitLab redirects to login page
        # This ensures GitLab's Rails app is fully initialized (not just nginx returning 502)
        # We check that the root URL redirects to /users/sign_in which indicates GitLab is ready
        effective_url = http_url or f"http://localhost:{cls.DEFAULT_PORT}"
        http_result = cls._check_http_redirects_to_login(effective_url, exec_cmd)
        all_logs.extend(http_result.exec_logs)
        services["http"] = ServiceState.HEALTHY if http_result.value else ServiceState.UNHEALTHY

        health = Health(services=services)
        return Result(success=health.is_healthy, value=health, exec_logs=all_logs)

    # ===========================================
    # GitLab-specific helper methods
    # ===========================================

    @classmethod
    def _check_gitlab_services(cls, exec_cmd: CommandExecutor | None = None) -> Result:
        """Check gitlab-ctl status and parse service states.

        Returns:
            Result with dict mapping service names to ServiceState.
        """
        cmd = "gitlab-ctl status"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)

        services: dict[str, ServiceState] = {}

        # Parse gitlab-ctl status output
        # Format: "run: servicename: (pid XXXX) XXXXs; run: log: (pid XXXX) XXXXs"
        # or: "down: servicename: XXXs, normally up"
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            # Check for running service
            if line.startswith("run:"):
                # Extract service name: "run: nginx: (pid 409) 589s"
                parts = line.split(":")
                if len(parts) >= 2:
                    service_name = parts[1].strip()
                    # Skip "log" entries
                    if service_name != "log" and service_name in cls.expected_services:
                        services[service_name] = ServiceState.RUNNING

            # Check for down service
            elif line.startswith("down:"):
                parts = line.split(":")
                if len(parts) >= 2:
                    service_name = parts[1].strip()
                    if service_name in cls.expected_services:
                        services[service_name] = ServiceState.STOPPED

        return Result(
            success=returncode == 0,
            value=services,
            exec_logs=[ExecLog(cmd, returncode, stdout, stderr)],
        )

    @classmethod
    def _check_postgresql(cls, exec_cmd: CommandExecutor | None = None) -> Result:
        """Check if PostgreSQL is responding."""
        cmd = 'gitlab-psql -d gitlabhq_production -c "SELECT 1;"'
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        # Success if command returns 0 and output contains "1"
        ready = returncode == 0 and "1" in stdout
        return Result(
            success=ready,
            value=ready,
            exec_logs=[ExecLog(cmd, returncode, stdout, stderr)],
        )

    @classmethod
    def _check_redis(cls, exec_cmd: CommandExecutor | None = None) -> Result:
        """Check if Redis is responding."""
        cmd = "gitlab-redis-cli ping"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        ready = returncode == 0 and "PONG" in stdout.upper()
        return Result(
            success=ready,
            value=ready,
            exec_logs=[ExecLog(cmd, returncode, stdout, stderr)],
        )

    @classmethod
    def _check_env_ctrl(cls, exec_cmd: CommandExecutor | None = None) -> Result:
        """Check if env-ctrl process is running.

        env-ctrl runs as an independent background process (not a runit service),
        so we check it via pgrep.
        """
        cmd = "pgrep -f 'env-ctrl serve'"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        # pgrep returns 0 if process found, 1 if not found
        running = returncode == 0 and stdout.strip() != ""
        return Result(
            success=running,
            value=running,
            exec_logs=[ExecLog(cmd, returncode, stdout, stderr)],
        )

    @classmethod
    def _check_http_redirects_to_login(
        cls,
        url: str,
        exec_cmd: CommandExecutor | None = None,
    ) -> Result:
        """Check that GitLab root URL redirects to the login page.

        GitLab returns 502 during startup while Puma workers initialize.
        Once fully ready, the root URL redirects to /users/sign_in.
        This check ensures GitLab is fully operational before marking healthy.

        Args:
            url: Base URL to check (e.g., http://localhost:8023).
            exec_cmd: Optional executor function.

        Returns:
            Result with bool indicating if redirect to login page was detected.
        """
        # Use curl -L to follow redirects and -w to output the final URL
        # -s for silent, -o /dev/null to discard body, -w '%{url_effective}' for final URL
        cmd = f"curl -sL -o /dev/null -w '%{{url_effective}}' --max-time 10 {url}"
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)

        # Check if the final URL contains /users/sign_in (login page)
        ready = returncode == 0 and "/users/sign_in" in stdout

        return Result(
            success=ready,
            value=ready,
            exec_logs=[ExecLog(cmd, returncode, stdout, stderr)],
        )
