import json
import re
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from webarena_verified.core.utils import logger
from webarena_verified.utils import get_package_assets_path

from .task import WebArenaSite


class EnvironmentConfig(BaseModel):
    """Configuration for a single environment/site.

    Supports multiple environment variations (e.g., staging, production) for the same site.
    When evaluating across multiple test environments, any URL in the list can be mapped back
    to the template placeholder, allowing you to evaluate logs from different environments
    using the same task definitions.

    Attributes:
        urls: List of all possible URLs for this environment (e.g., production, staging, dev instances).
            During evaluation, any URL in this list can be derendered to the same template placeholder.
            Example: Both `https://gitlab-staging.com` and `https://gitlab-prod.com` can map to `__GITLAB__`.

        active_url_idx: Selects which URL from the `urls` array to use when running tasks (default: 0).
            This determines which environment the task will execute against. When transforming template
            URLs (e.g., `__GITLAB__`) back to real URLs (e.g., `https://gitlab.example.com`), the URL at
            this index is used. Defaults to 0 (first URL) if not specified.

        use_header_login: Optional flag to enable header-based authentication for this environment.
            When True, authentication is performed via HTTP headers (e.g., X-M2-Admin-Auto-Login-User) instead of
            traditional UI login. Only supported for certain sites (e.g., shopping_admin). Defaults to False.

        credentials: Optional authentication credentials for this environment (e.g., username, password).
            Used for automated login before task execution.

        extra: Additional configuration data for this environment as a flexible key-value store.
            Can hold any site-specific configuration (e.g., {"container_name": "my-container"}).

    Example:
        If you have logs from staging (`https://gitlab-staging.com`) and production
        (`https://gitlab-prod.com`), both can be derendered to `__GITLAB__` during evaluation.
        The `active_url_idx` determines which variant is used when rendering templates to real URLs.
    """

    urls: list[str]

    active_url_idx: int | None = None

    use_header_login: bool = False

    credentials: dict[str, str] | None = None

    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def set_default_active_url_idx(self) -> Self:
        """Set active_url_idx to 0 if None and urls list is not empty."""
        if self.active_url_idx is None and self.urls:
            self.active_url_idx = 0
        return self

    @property
    def active_url(self) -> str | None:
        """Get the active URL for this environment.

        Returns:
            The active URL string, or None if urls list is empty.
        """
        if not self.urls or self.active_url_idx is None:
            return None
        return self.urls[self.active_url_idx]

    def set_active_url(self, new_url: str) -> None:
        """Set the active URL by adding it to urls if not present and updating the index.

        If the URL already exists in the list, it will be set as active without duplication.

        Args:
            new_url: The URL to set as active
        """
        if new_url in self.urls:
            self.active_url_idx = self.urls.index(new_url)
        else:
            self.urls.append(new_url)
            self.active_url_idx = len(self.urls) - 1

    def render_url(self, url_template: str, site: WebArenaSite, url_idx: int | None = None) -> str:
        """Render a URL template by replacing the site template with this environment's URL.

        Args:
            url_template: URL template string (e.g., "__GITLAB__/api/v1")
            site: The site enum for this environment
            url_idx: Optional URL index to use. If None, uses active_url_idx.

        Returns:
            Rendered URL with template replaced by actual URL from this environment.
            Returns original template unchanged if it doesn't match this site's template.
        """
        if not url_template.startswith(site.url_name_template):
            return url_template

        idx = url_idx if url_idx is not None else self.active_url_idx
        if idx is None or idx < 0 or idx >= len(self.urls):
            raise ValueError(
                f"Invalid environment URL index {idx} for site {site.name}. Verify that config file has url for {site}."
            )

        url = self.urls[idx]  # currently active URL
        return url_template.replace(site.url_name_template, url)

    def derender_url(self, url: str, site: WebArenaSite, is_ssh: bool = False) -> str | None:
        """Derender a URL by replacing the actual URL with the site template.

        Args:
            url: URL string to derender
            site: The site enum for this environment
            is_ssh: If True, treat as SSH URL and use SSH-specific derendering

        Returns:
            Derendered URL with actual URL replaced by site template, or None if no match found.
        """
        for site_url in self.urls:
            if is_ssh:
                host_name = urlparse(site_url).hostname
                if host_name:
                    result = self._derender_ssh_url(url, host_name, site.url_name_template)
                    if result is not None:
                        return result
            elif site_url in url:
                return url.replace(site_url.rstrip("/"), site.url_name_template)
        return None

    def _derender_ssh_url(self, ssh_url: str, hostname: str, template: str) -> str | None:
        """Derender SSH URL by replacing hostname with __ssh_host__ and converting to short format.

        Args:
            ssh_url: SSH URL to derender (e.g., "ssh://git@localhost:2222/path/to/repo.git")
            hostname: Hostname to match and replace (e.g., "localhost")
            template: Present for interface consistency; ignored for SSH URLs, which always use the fixed __ssh_host__ template

        Returns:
            Derendered URL in short format (e.g., "git@__ssh_host__:path/to/repo.git") or None if hostname not found
        """
        # Pattern: capture ssh://user@, hostname, optional port, and path
        # We need to match the specific hostname and replace it with template
        pattern = rf"(ssh://([^@]+)@){re.escape(hostname)}(:[0-9]+)?(/.*)?$"
        match = re.match(pattern, ssh_url)

        if not match:
            return None

        # Extract components
        user = match.group(2)  # git
        path = match.group(4) or ""  # /path/to/repo.git

        # Remove leading slashes from path for short format
        path = path.lstrip("/")

        # Convert to short SCP-like format with generic __ssh_host__ template
        # Use __ssh_host__ instead of site-specific template for SSH URLs
        return f"{user}@__ssh_host__:{path}"


class TaskOutputDirMeta(BaseModel):
    """Metadata for task output directory structure.

    All file paths are pre-computed from WebArenaVerifiedConfig file names.
    This is a simple data holder with no business logic.
    """

    task_output_dir: Path
    task_id: int
    agent_response_file: Path
    trace_file: Path
    eval_result_file: Path
    storage_state_file: Path

    @property
    def is_run_output_valid(self) -> bool:
        """Check if the run outputs (agent response and trace files) exist and are valid."""
        try:
            self.ensure_run_outputs()
            return True
        except (FileNotFoundError, ValueError):
            return False

    @property
    def is_task_output_exists(self) -> bool:
        """Check if the task output directory exists and is non-empty."""
        return self.task_output_dir.exists() and any(self.task_output_dir.iterdir())

    def ensure_run_outputs(self) -> None:
        """Ensure that the agent response and trace files exist.

        Raises:
            FileNotFoundError: If agent response or trace file doesn't exist
            ValueError: If agent response file is empty
        """
        if not self.agent_response_file.exists():
            raise FileNotFoundError(f"Agent response file not found: {self.agent_response_file}")
        if not self.trace_file.exists():
            raise FileNotFoundError(f"Trace file not found: {self.trace_file}")

    @classmethod
    def create(cls, config: "WebArenaVerifiedConfig", output_dir: Path, task_id: int) -> "TaskOutputDirMeta":
        """Create TaskOutputDirMeta for a task using the config's file names.

        Creates the task output directory and computes all file paths from file names.

        Args:
            config: WebArenaVerifiedConfig instance with file path templates
            output_dir: Base output directory
            task_id: Task identifier

        Returns:
            TaskOutputDirMeta instance with all paths pre-computed
        """
        # Create task output directory
        task_output_dir = output_dir / str(task_id)
        task_output_dir.mkdir(parents=True, exist_ok=True)

        # Compute all file paths using file names directly
        agent_response_file = task_output_dir / config.agent_response_file_name
        trace_file = task_output_dir / config.trace_file_name
        eval_result_file = task_output_dir / config.eval_result_file_name
        storage_state_file = task_output_dir / config.storage_state_file_name

        return cls(
            task_output_dir=task_output_dir,
            task_id=task_id,
            agent_response_file=agent_response_file,
            trace_file=trace_file,
            eval_result_file=eval_result_file,
            storage_state_file=storage_state_file,
        )


class WebArenaVerifiedConfig(BaseModel):
    """Main configuration for WebArena-Verified evaluation framework.

    Specifies dataset location, environment configurations for each site, and file names
    for task outputs.

    Attributes:
        test_data_file: Path to the WebArena-Verified dataset JSON file. Can be absolute or relative
            to project root (directory containing `.webarena_verified_root` or `pyproject.toml`).
            Defaults to `assets/dataset/webarena-verified.json`.

        environments: Maps site placeholder names (e.g., `__SHOPPING__`, `__GITLAB__`) to their
            environment configurations. Each environment contains URLs, credentials, and URL selection.
            Required for most operations. If None, evaluation operations requiring URL rendering will fail.

        agent_response_file_name: Filename for agent response JSON file containing the agent's
            final answer. Used directly without modification.

        trace_file_name: Filename for network trace file in HAR format, containing recorded browser
            network activity. Used directly without modification.

        eval_result_file_name: Filename for evaluation result JSON file containing pass/fail status
            and evaluation details. Used directly without modification.

        storage_state_file_name: Filename for browser storage state JSON file containing cookies
            and auth tokens for pre-login. Used directly without modification.

    Example:
        ```python
        config = WebArenaVerifiedConfig.from_file("config.json")
        env = config.get_environment(WebArenaSite.SHOPPING)
        rendered = config.render_url("__SHOPPING__/products", [WebArenaSite.SHOPPING])
        ```
    """

    test_data_file: Path = get_package_assets_path() / "dataset/webarena-verified.json"
    environments: dict[WebArenaSite, EnvironmentConfig] | None = None

    agent_response_file_name: str = "agent_response.json"

    trace_file_name: str = "network.har"

    eval_result_file_name: str = "eval_result.json"

    storage_state_file_name: str = ".storage_state.json"

    @model_validator(mode="after")
    def validate_data(self) -> Self:
        if not self.test_data_file.exists():
            # Handle cases where the run was done on a different machine or mount point
            logger.warning(f"test_data_file {self.test_data_file} does not exist. Falling back to default dataset.")
            self.test_data_file = get_package_assets_path() / "dataset/webarena-verified.json"
        else:
            logger.info(f"Using test_data_file: {self.test_data_file}")

        return self

    @classmethod
    def from_file(cls, config_file: Path | str, test_data_file_override: Path | str | None = None) -> Self:
        """Load config from file with optional test_data_file override.

        Args:
            config_file: Path to config JSON file
            test_data_file_override: Optional path to override test_data_file after loading

        Returns:
            Loaded and validated config instance
        """
        config_path = Path(config_file).resolve()
        if not config_path.exists():
            raise FileNotFoundError(f"Config file {str(config_path)!r} does not exist.")
        try:
            logger.info(f"Loading config from: {str(config_path)!r}")
            raw = json.loads(config_path.read_text())
            config = cls.model_validate(raw)

            # Apply test_data_file override if provided
            if test_data_file_override is not None:
                config.test_data_file = Path(test_data_file_override)
                logger.info(f"Overriding test_data_file with: {test_data_file_override}")

            return config
        except Exception:
            logger.error(f"Failed to load config. Check your configuration {str(config_path)!r}.")
            raise

    def to_file(self, config_file: Path | str) -> None:
        """Save configuration to JSON file.

        Args:
            config_file: Path to save the config file. Can be absolute or relative path.

        Raises:
            OSError: If file cannot be written (e.g., permission issues, invalid path)
        """
        config_path = Path(config_file).resolve()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving config to: {str(config_path)!r}")
        with open(config_path, "w") as f:
            json.dump(self.model_dump(mode="json"), f, indent=2)
        logger.info(f"Config saved successfully to: {str(config_path)!r}")

    def get_environment(self, site: WebArenaSite) -> EnvironmentConfig | None:
        """Get environment configuration for a specific site."""
        if self.environments is None:
            return None
        return self.environments.get(site)

    def render_url(
        self,
        url_w_template: str | list[str],
        sites: list[WebArenaSite] | tuple[WebArenaSite, ...],
        url_idx: int | None = None,
        strict: bool = True,
    ) -> str | list[str]:
        """Render a URL by replacing the site template with the actual URL from the map.

        Args:
            url_w_template: URL template string or list of strings
            sites: List or tuple of sites to try for rendering (in order)
            url_idx: Optional URL index to use. If None, uses active_url_idx from environment config.
            strict: If True, raise ValueError when no site matches. If False, return original template.

        Returns:
            Rendered URL with template replaced by actual URL. Returns same type as input (string or list).

        Raises:
            ValueError: If no environments configured, site not found in environments, or (when strict=True) no site matches
        """
        if self.environments is None:
            raise ValueError("No environments configured")

        # Validate all sites exist in environments
        if any(site not in self.environments for site in sites):
            missing_sites = [site.name for site in sites if site not in self.environments]
            raise ValueError(f"Sites {missing_sites} not found in environments")

        # Convert input to list for uniform processing
        was_single = not isinstance(url_w_template, list)
        urls_to_process = [url_w_template] if was_single else url_w_template

        # Process all URLs
        results = []
        for url_template in urls_to_process:
            rendered = None

            # Try each site in order until one matches
            for site in sites:
                env_config = self.environments[site]
                rendered_url = env_config.render_url(url_template, site, url_idx)
                # Check if rendering actually happened (different from original)
                if rendered_url != url_template:
                    rendered = rendered_url
                    break

            if rendered is None:
                if strict:
                    raise ValueError(f"No site in {[s.name for s in sites]} matched template: {url_template}")
                else:
                    rendered = url_template  # Return original

            results.append(rendered)

        # Return single string if input was single, otherwise return list
        return results[0] if was_single else results

    def derender_url(
        self,
        url: str | list[str],
        sites: list[WebArenaSite] | tuple[WebArenaSite, ...],
        strict: bool = True,
        is_ssh: bool = False,
    ) -> str | list[str]:
        """Derender a URL by replacing the actual URL with the site template from the map.

        Args:
            url: URL string or list of URL strings to derender
            sites: List or tuple of sites to try for derendering (tried in order of URL specificity - longest first)
            strict: If True, raise ValueError when no site matches. If False, return original URL.

        Returns:
            Derendered URL(s) with actual URL replaced by site template. Returns same type as input (string or list).

        Raises:
            ValueError: If no environments configured, site not found, or (when strict=True) URL doesn't match any site
        """
        if self.environments is None:
            raise ValueError("No environments configured")

        # Use local variable to narrow type for type checker
        environments = self.environments

        # Validate all sites exist in environments
        if any(site not in environments for site in sites):
            missing_sites = [site.name for site in sites if site not in environments]
            raise ValueError(f"Sites {missing_sites} not found in environments")

        # Sort sites by URL specificity (longest URL first) for accurate matching
        sites_by_specificity = sorted(sites, key=lambda s: max(len(url) for url in environments[s].urls), reverse=True)

        # Convert input to list for uniform processing
        was_single = not isinstance(url, list)
        urls_to_process = [url] if was_single else url

        # Process all URLs
        results = []
        for url_to_derender in urls_to_process:
            derendered = None

            # Try each site (in specificity order) until one matches
            for site in sites_by_specificity:
                env_config = environments[site]
                derendered_url = env_config.derender_url(url_to_derender, site, is_ssh=is_ssh)
                if derendered_url is not None:
                    derendered = derendered_url
                    break

            if derendered is None:
                if strict:
                    raise ValueError(
                        f"URL '{url_to_derender}' does not match any configured URLs for sites {[s.name for s in sites]}"
                    )
                else:
                    derendered = url_to_derender  # Return original

            results.append(derendered)

        # Return single string if input was single, otherwise return list
        return results[0] if was_single else results

    def get_task_output_dir_metadata(self, output_dir: Path, task_id: int) -> TaskOutputDirMeta:
        """Create TaskOutputDirMeta for a task using this config's file names.

        Creates the task output directory and computes all file paths from file names.

        Args:
            output_dir: Base output directory
            task_id: Task identifier

        Returns:
            TaskOutputDirMeta instance with all paths pre-computed

        Note:
            This method is maintained for backward compatibility. New code should use
            TaskOutputDirMeta.create(config, output_dir, task_id) directly.
        """
        return TaskOutputDirMeta.create(self, output_dir, task_id)
