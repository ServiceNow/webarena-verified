"""Site handler protocol for executing commands on site instances."""

from typing import TYPE_CHECKING, Protocol

from webarena_verified.types.environment import SiteInstanceCommandResult

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext


class SiteInstanceHandler(Protocol):
    """Protocol for handling command execution and site operations.

    This abstraction allows patches to execute commands without knowing
    the underlying implementation (Docker, SSH, Kubernetes, etc.).

    Implementations should provide:
    - Command execution capabilities (exec_cmd)
    - Container lifecycle management (stop, start, init)
    - Environment reset functionality (reset)
    - Site reachability verification (verify)
    - Authentication/login capabilities (login)
    """

    def exec_cmd(
        self,
        cmd: list[str],
        input_data: str | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        **kwargs,
    ) -> SiteInstanceCommandResult:
        """Execute a command on the site instance.

        Args:
            cmd: Command and arguments to execute
            input_data: Optional input data for stdin
            capture_output: Whether to capture stdout/stderr
            text: Whether to decode output as text (vs bytes)
            check: Whether to raise exception on non-zero exit code
            **kwargs: Additional implementation-specific arguments

        Returns:
            SiteInstanceCommandResult containing stdout, stderr, and returncode

        Raises:
            Exception: If check=True and command fails (implementation-specific)
        """
        ...

    def stop(self) -> None:
        """Stop and delete the site container.

        Stops the running container and removes it from the system.
        Container state is destroyed and must be recreated with start().

        Raises:
            RuntimeError: If stop operation fails
        """
        ...

    def start(self) -> str:
        """Start the site container and initialize it.

        Creates and starts the container, then calls init() to apply
        configuration and patches. For containers that are already
        running, this will recreate them.

        Returns:
            The URL where the site is running

        Raises:
            RuntimeError: If start operation fails
        """
        ...

    def init(self, *, url: str | None = None) -> None:
        """Initialize the site container.

        Applies patches, configuration, and any site-specific setup.
        Called automatically by start() after container creation.

        Args:
            url: Optional URL override for initialization. If None, uses env_config.active_url.
                 This is typically passed by start() with the newly generated URL before the
                 runner updates the config file.

        Raises:
            RuntimeError: If initialization fails
        """
        ...

    def reset(self) -> None:
        """Reset the site environment to its initial state.

        Stops and deletes the container, then starts and initializes it.
        Equivalent to calling stop() followed by start().

        Uses base_url from the environment configuration provided during initialization.

        Raises:
            RuntimeError: If reset fails
        """
        ...

    def verify(self) -> None:
        """Verify the site is reachable and responding.

        Checks that the site is accessible via HTTP request to the base URL.
        Uses retry logic with timeout to handle startup delays.

        Raises:
            RuntimeError: If site is not reachable within timeout period
        """
        ...

    def login(
        self,
        context: "BrowserContext",
    ) -> dict[str, str] | None:
        """Authenticate to the site.

        Uses credentials and authentication method from the environment configuration
        provided during initialization.

        Args:
            context: Playwright browser context for UI-based login

        Returns:
            None for UI-based login, or dict of HTTP headers for header-based login
        """
        ...
