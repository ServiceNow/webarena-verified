"""OpenStreetMap website environment operations.

Multi-service environment managed by supervisord:
- PostgreSQL instances: postgresql-14 (website), postgresql-15 (tiles), postgresql-nominatim (geocoding)
- Web services: rails (OSM website), apache2 (tile server + routing proxy)
- Tile rendering: renderd
- Routing: osrm-car, osrm-bike, osrm-foot
"""

from __future__ import annotations

from typing import Any, ClassVar, Optional

from ..base import BaseOps
from ..mixins import SupervisorMixin
from ..types import CommandExecutor, ExecLog, Health, Result, ServiceState


class MapOps(SupervisorMixin, BaseOps):
    """Operations for OpenStreetMap website environment.

    Map runs multiple services managed by supervisord:
    - 3 PostgreSQL instances for website, tiles, and geocoding
    - Rails app for the OSM website
    - Apache2 for tile serving and routing proxy
    - renderd for tile rendering
    - 3 OSRM instances for car/bike/foot routing
    """

    # Supervisor-managed services (env-ctrl is added dynamically via _get_expected_services if enabled)
    expected_services: ClassVar[frozenset[str]] = frozenset(
        {
            "postgresql-14",  # Website database (port 5433)
            "postgresql-15",  # Tile server database (port 5432)
            "postgresql-nominatim",  # Geocoding database (port 5434)
            "rails",  # OSM website (port 3000)
            "apache2",  # Tile server + routing proxy (port 8080)
            "renderd",  # Tile rendering daemon
            "osrm-car",  # Car routing API (port 5000)
            "osrm-bike",  # Bike routing API (port 5001)
            "osrm-foot",  # Foot routing API (port 5002)
        }
    )

    cleanup_paths: ClassVar[list[str]] = [
        "/var/log/supervisor/*.log",
        "/var/log/apache2/*.log",
        "/app/log/*.log",
        "/tmp/*",
    ]

    # --- Service configuration ---

    # PostgreSQL services with their ports
    PG_SERVICES: ClassVar[list[tuple[str, int]]] = [
        ("postgresql-14", 5433),  # Website DB
        ("postgresql-15", 5432),  # Tile DB
        ("postgresql-nominatim", 5434),  # Geocoding DB
    ]

    # OSRM routing services with their ports
    OSRM_SERVICES: ClassVar[list[tuple[str, int]]] = [
        ("osrm-car", 5000),
        ("osrm-bike", 5001),
        ("osrm-foot", 5002),
    ]

    # Test coordinates for OSRM health checks (NYC area - known to be in US Northeast dataset)
    OSRM_TEST_COORDS: ClassVar[str] = "-74.006,40.7128;-73.95,40.72"

    # Tile coordinates for rendering health check (NYC area at zoom 12)
    TILE_TEST_URL: ClassVar[str] = "http://localhost:8080/tile/12/1205/1539.png"

    # Nominatim test query
    NOMINATIM_TEST_URL: ClassVar[str] = "http://localhost:8080/nominatim/search?q=New+York&format=json&limit=1"

    # Rails app URL
    RAILS_URL: ClassVar[str] = "http://localhost:3000/"

    # --- Subclassed methods (BaseOps abstract implementations) ---

    @classmethod
    def _init(
        cls, exec_cmd: Optional[CommandExecutor] = None, base_url: str = "", dry_run: bool = False, **kwargs: Any
    ) -> Result:
        """Initialize OpenStreetMap environment.

        The map site uses relative URLs in settings.local.yml (proxied through Apache),
        so no URL configuration is needed.

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            base_url: Base URL (unused - site uses relative URLs).
            dry_run: If True, preview changes without applying them.
        """
        if dry_run:
            return Result(
                success=True,
                value={
                    "dry_run": True,
                    "message": "No initialization required - site uses relative URLs",
                    "commands_to_run": [],
                    "command_count": 0,
                },
                exec_logs=[],
            )
        return Result(
            success=True,
            exec_logs=[ExecLog("init", 0, "No initialization required - site uses relative URLs", "")],
        )

    @classmethod
    def _start(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Start all supervisord services."""
        return cls.supervisor_start(exec_cmd)

    @classmethod
    def _stop(cls, exec_cmd: Optional[CommandExecutor] = None, **kwargs: Any) -> Result:
        """Stop all supervisord services (except env-ctrl)."""
        return cls.supervisor_stop(exec_cmd)

    @classmethod
    def _get_health(
        cls, exec_cmd: Optional[CommandExecutor] = None, http_url: Optional[str] = None, **kwargs: Any
    ) -> Result:
        """Site-specific health check for OpenStreetMap environment.

        Checks:
        1. Supervisor services are running
        2. PostgreSQL instances are ready (pg_isready)
        3. OSRM routing services are responding
        4. Tile rendering is working (apache2 + renderd)
        5. Nominatim geocoding is responding

        Args:
            exec_cmd: Executor function. Defaults to subprocess.
            http_url: Optional HTTP URL to check (unused, services checked internally).

        Returns:
            Result with Health containing all service states.
            Services use supervisor names with HEALTHY/UNHEALTHY states.
        """
        all_logs: list[ExecLog] = []
        services: dict[str, ServiceState] = {}

        # 1. Check supervisor services (sets RUNNING state)
        svc_result = cls._check_services(services, exec_cmd)
        all_logs.extend(svc_result.exec_logs)

        # 2. Upgrade PostgreSQL to HEALTHY/UNHEALTHY via pg_isready
        pg_result = cls._check_postgres_health(services, exec_cmd)
        all_logs.extend(pg_result.exec_logs)

        # 3. Upgrade Rails to HEALTHY/UNHEALTHY via HTTP
        rails_result = cls._check_rails_health(services, exec_cmd)
        all_logs.extend(rails_result.exec_logs)

        # 4. Upgrade Apache to HEALTHY/UNHEALTHY via HTTP
        apache_result = cls._check_apache_health(services, exec_cmd)
        all_logs.extend(apache_result.exec_logs)

        # 5. Upgrade OSRM services to HEALTHY/UNHEALTHY
        osrm_result = cls._check_osrm_health(services, exec_cmd)
        all_logs.extend(osrm_result.exec_logs)

        # 6. Check tile rendering (upgrades renderd)
        tile_result = cls._check_tile_health(services, exec_cmd)
        all_logs.extend(tile_result.exec_logs)

        # 7. Check Nominatim geocoding
        nominatim_result = cls._check_nominatim_health(services, exec_cmd)
        all_logs.extend(nominatim_result.exec_logs)

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
    def _check_rails_health(
        cls, services: dict[str, ServiceState], exec_cmd: Optional[CommandExecutor] = None
    ) -> Result:
        """Upgrade Rails from RUNNING to HEALTHY/UNHEALTHY via HTTP check.

        Args:
            services: Dict to update with service states.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        if services.get("rails") != ServiceState.RUNNING:
            return Result(success=True, value=services, exec_logs=[])

        cmd = f'curl -sf --max-time 10 "{cls.RAILS_URL}"'
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        log = ExecLog(cmd, returncode, stdout, stderr)

        services["rails"] = ServiceState.HEALTHY if returncode == 0 else ServiceState.UNHEALTHY
        return Result(success=True, value=services, exec_logs=[log])

    @classmethod
    def _check_apache_health(
        cls, services: dict[str, ServiceState], exec_cmd: Optional[CommandExecutor] = None
    ) -> Result:
        """Upgrade Apache from RUNNING to HEALTHY/UNHEALTHY via HTTP check.

        Args:
            services: Dict to update with service states.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        if services.get("apache2") != ServiceState.RUNNING:
            return Result(success=True, value=services, exec_logs=[])

        # Check Apache via the main port (proxies to Rails)
        cmd = 'curl -sf --max-time 10 "http://localhost:8080/"'
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        log = ExecLog(cmd, returncode, stdout, stderr)

        services["apache2"] = ServiceState.HEALTHY if returncode == 0 else ServiceState.UNHEALTHY
        return Result(success=True, value=services, exec_logs=[log])

    @classmethod
    def _check_postgres_health(
        cls, services: dict[str, ServiceState], exec_cmd: Optional[CommandExecutor] = None
    ) -> Result:
        """Upgrade PostgreSQL services from RUNNING to HEALTHY/UNHEALTHY.

        Args:
            services: Dict to update with service states.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        all_logs: list[ExecLog] = []

        for svc_name, port in cls.PG_SERVICES:
            if services.get(svc_name) != ServiceState.RUNNING:
                continue

            cmd = f"pg_isready -h localhost -p {port}"
            returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
            all_logs.append(ExecLog(cmd, returncode, stdout, stderr))

            services[svc_name] = ServiceState.HEALTHY if returncode == 0 else ServiceState.UNHEALTHY

        return Result(success=True, value=services, exec_logs=all_logs)

    @classmethod
    def _check_osrm_health(
        cls, services: dict[str, ServiceState], exec_cmd: Optional[CommandExecutor] = None
    ) -> Result:
        """Upgrade OSRM services from RUNNING to HEALTHY/UNHEALTHY.

        Tests each routing service with a simple route request.

        Args:
            services: Dict to update with service states.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        all_logs: list[ExecLog] = []

        for svc_name, port in cls.OSRM_SERVICES:
            if services.get(svc_name) != ServiceState.RUNNING:
                continue

            # Extract profile from service name (osrm-car -> car)
            profile = svc_name.replace("osrm-", "")
            url = f"http://localhost:{port}/route/v1/{profile}/{cls.OSRM_TEST_COORDS}"
            cmd = f'curl -sf --max-time 5 "{url}"'
            returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
            all_logs.append(ExecLog(cmd, returncode, stdout, stderr))

            # Check for successful response with "code": "Ok"
            is_healthy = returncode == 0 and '"code":"Ok"' in stdout.replace(" ", "")
            services[svc_name] = ServiceState.HEALTHY if is_healthy else ServiceState.UNHEALTHY

        return Result(success=True, value=services, exec_logs=all_logs)

    @classmethod
    def _check_tile_health(
        cls, services: dict[str, ServiceState], exec_cmd: Optional[CommandExecutor] = None
    ) -> Result:
        """Check tile rendering health (renderd).

        Fetches a known tile and verifies it's a valid PNG image.

        Args:
            services: Dict to update with service states.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        all_logs: list[ExecLog] = []

        # Only check if renderd is running and apache2 is healthy (needed to serve tiles)
        if services.get("renderd") != ServiceState.RUNNING:
            return Result(success=True, value=services, exec_logs=all_logs)
        if services.get("apache2") not in (ServiceState.RUNNING, ServiceState.HEALTHY):
            return Result(success=True, value=services, exec_logs=all_logs)

        # Fetch tile and check HTTP status + content type
        cmd = f'curl -sf --max-time 10 -o /dev/null -w "%{{http_code}}:%{{content_type}}" "{cls.TILE_TEST_URL}"'
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        all_logs.append(ExecLog(cmd, returncode, stdout, stderr))

        # Check for HTTP 200 and image/png content type
        is_healthy = returncode == 0 and stdout.startswith("200:") and "image/png" in stdout
        services["renderd"] = ServiceState.HEALTHY if is_healthy else ServiceState.UNHEALTHY

        return Result(success=True, value=services, exec_logs=all_logs)

    @classmethod
    def _check_nominatim_health(
        cls, services: dict[str, ServiceState], exec_cmd: Optional[CommandExecutor] = None
    ) -> Result:
        """Check Nominatim geocoding health.

        Performs a simple search query and verifies the response.

        Args:
            services: Dict to update with service states.
            exec_cmd: Executor function. Defaults to subprocess.

        Returns:
            Result with updated services dict.
        """
        all_logs: list[ExecLog] = []

        # Nominatim depends on postgresql-nominatim and apache2
        pg_nominatim = services.get("postgresql-nominatim")
        apache2 = services.get("apache2")

        # Skip if dependencies aren't healthy
        if pg_nominatim not in (ServiceState.RUNNING, ServiceState.HEALTHY):
            return Result(success=True, value=services, exec_logs=all_logs)
        if apache2 not in (ServiceState.RUNNING, ServiceState.HEALTHY):
            return Result(success=True, value=services, exec_logs=all_logs)

        cmd = f'curl -sf --max-time 10 "{cls.NOMINATIM_TEST_URL}"'
        returncode, stdout, stderr = cls._run_cmd(cmd, exec_cmd)
        all_logs.append(ExecLog(cmd, returncode, stdout, stderr))

        # Check for HTTP 200 and non-empty JSON array
        is_healthy = returncode == 0 and stdout.strip().startswith("[") and len(stdout.strip()) > 2

        # Upgrade postgresql-nominatim to HEALTHY if geocoding works
        if is_healthy and pg_nominatim == ServiceState.RUNNING:
            services["postgresql-nominatim"] = ServiceState.HEALTHY

        return Result(success=True, value=services, exec_logs=all_logs)
