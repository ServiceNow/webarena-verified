import argparse
import logging
import shutil
import sys
from enum import StrEnum
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateError, TemplateSyntaxError
from playwright.async_api import BrowserContext, async_playwright

logger = logging.getLogger(__name__)


# NOTE: These enums are duplicated from webarena_verified.types.agent_response
# to keep agent code independent of the benchmark library. This allows agents
# to be used as standalone reference implementations without requiring the
# evaluation framework as a dependency.


TASK_TYPE_OPTIONS = [
    "RETRIEVE",
    "MUTATE",
    "NAVIGATE",
]

STATUS_OPTIONS = [
    "SUCCESS",
    "ACTION_NOT_ALLOWED_ERROR",
    "PERMISSION_DENIED_ERROR",
    "NOT_FOUND_ERROR",
    "DATA_VALIDATION_ERROR",
    "UNKNOWN_ERROR",
]


def backup_output_dir(task_output_dir: Path, task_id: int) -> None:
    """
    Backup an existing output directory if it exists.

    Creates a backup with the naming pattern: {task_id}_bkp_{idx}
    where idx is incremented to avoid overwriting existing backups.

    Args:
        task_output_dir: Path to the output directory to backup
        task_id: Task ID for naming the backup directory

    Example:
        If task_output_dir is "output/123" and it exists:
        - First backup: "output/123_bkp_1"
        - Second backup: "output/123_bkp_2"
        - etc.
    """
    if not task_output_dir.exists():
        return

    parent_dir = task_output_dir.parent
    idx = 1

    # Find the next available backup index
    while True:
        backup_dir = parent_dir / f"{task_id}_bkp_{idx}"
        if not backup_dir.exists():
            break
        idx += 1

    # Move existing directory to backup
    shutil.move(str(task_output_dir), str(backup_dir))
    logger.info(f"Backed up existing output directory to: {backup_dir}")


def setup_logging(*, logger: logging.Logger, task_output_dir: Path):
    """
    Configure logging to write to both stdout and a file.

    Args:
        logger: Logger instance to configure
        task_output_dir: Directory where logs will be written
    """
    log_file = task_output_dir / f"{logger.name.lower().replace('-', '_')}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create formatter
    formatter = logging.Formatter("[%(name)s] [%(levelname)s] %(message)s")

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # File handler
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Configure logger
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # Remove any existing handlers to prevent duplicate logs
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False  # Don't propagate to root logger

    logger.info(f"Logging to file: {log_file.resolve()}")


def render_prompt_template(prompt_file_path: str | Path, **template_vars) -> str:
    """
    Render a Jinja2 template prompt file with the provided variables.

    Args:
        prompt_file_path: Path to the prompt template file (e.g., 'examples/prompts/admin.md')
        **template_vars: Variables to pass to the Jinja2 template context

    Returns:
        str: The rendered prompt text

    Raises:
        FileNotFoundError: If the prompt file doesn't exist
        TemplateSyntaxError: If the template has invalid Jinja2 syntax
        TemplateError: If there's an error during template rendering

    Example:
        >>> prompt = render_prompt_template(
        ...     "examples/prompts/admin.md",
        ...     INTENT="Find all products",
        ...     START_URLS=["https://example.com"],
        ...     FORMAT_DIRECTIVES=["Use JSON format"]
        ... )
    """
    prompt_path = Path(prompt_file_path)

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template file not found: {prompt_path}")

    # Set up Jinja2 environment with the directory containing the template
    env = Environment(
        loader=FileSystemLoader(prompt_path.parent),
        autoescape=False,  # We're rendering markdown/text, not HTML
        keep_trailing_newline=True,
    )

    try:
        # Load and render the template
        template = env.get_template(prompt_path.name)
        rendered = template.render(**template_vars)
        return rendered
    except TemplateSyntaxError as e:
        raise TemplateSyntaxError(
            f"Invalid Jinja2 syntax in {prompt_path} at line {e.lineno}: {e.message}",
            e.lineno,
            e.name,
            e.filename,
        ) from e
    except TemplateError as e:
        raise TemplateError(f"Error rendering template {prompt_path}: {e}") from e


def select_prompt_template(sites: list[str], prompts_dir: Path) -> Path:
    """Select the appropriate prompt template file based on sites.

    Args:
        sites: List of site names (e.g., ["shopping_admin"], ["shopping", "reddit"])
        prompts_dir: Directory containing prompt template files

    Returns:
        Path to the selected prompt template file

    Raises:
        FileNotFoundError: If the prompt template file doesn't exist

    Rules:
        - Sort sites alphabetically for consistent naming
        - Single site: use `{site}.md`
        - Multi-site: use `{site1}-{site2}.md`
        - Raise error if template doesn't exist
    """
    # Sort sites alphabetically for consistent naming
    sorted_sites = sorted(sites, key=lambda s: s.lower())

    if not sorted_sites:
        raise ValueError("No sites provided")

    # Build prompt filename
    if len(sorted_sites) == 1:
        prompt_filename = f"{sorted_sites[0]}.md"
    else:
        prompt_filename = "-".join(sorted_sites) + ".md"

    prompt_path = prompts_dir / prompt_filename

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {prompt_path}\n"
            f"Expected template for sites: {sorted_sites}\n"
            f"Please create the template file at: {prompt_path}"
        )

    return prompt_path


def parse_args():
    """Parse command-line arguments for agent execution."""
    parser = argparse.ArgumentParser(description="Browser-use agent with Azure OpenAI")
    parser.add_argument("--tasks-file", required=True, help="Path to JSON file with task data (from agent-input-get)")
    parser.add_argument("--task_output_dir", required=True, help="Output directory for task results")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode")
    parser.add_argument("--task_id", type=int, required=True, help="Task ID (for logging purposes)")
    parser.add_argument("--storage_state_file", type=str, help="Path to storage state file for browser authentication")
    parser.add_argument(
        "--config", type=str, default=None, help="Path to config file for authentication and environment setup"
    )
    return parser.parse_args()


async def ui_login(
    sites: list[str],
    config: dict,
    storage_state_file: Path,
) -> None:
    """Perform UI login for sites and save browser storage state.

    Note: We use a plain dict for config instead of the WebArenaVerifiedConfig model
    to showcase that agents can run in isolation without depending on the benchmark
    library types. The config dict should match the structure of WebArenaVerifiedConfig
    when serialized to JSON.

    Args:
        sites: List of site names (e.g., ["shopping", "gitlab"])
        config: Configuration dict with structure:
            {
                "environments": {
                    "site_name": {
                        "urls": ["http://..."],
                        "active_url_idx": 0,  # optional, defaults to 0
                        "credentials": {"username": "...", "password": "..."}
                    }
                }
            }
        storage_state_file: Path to save browser storage state (cookies, localStorage, etc.)
    """
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})

        try:
            for site_name in sites:
                # Access environments dict directly
                environments = config.get("environments", {})
                possible_name = [
                    site_name.lower(),
                    site_name.upper(),
                    f"__{site_name.upper()}__",
                    f"__{site_name.lower()}__",
                ]
                for site_name_candidate in possible_name:
                    env_config = environments.get(site_name_candidate)
                    if env_config:
                        break

                if not env_config:
                    raise ValueError(f"Environment config for site '{site_name}' not found in config")

                # Access URLs and determine active URL
                urls = env_config.get("urls", [])
                active_url_idx = env_config.get("active_url_idx")

                if active_url_idx is not None and 0 <= active_url_idx < len(urls):
                    base_url = urls[active_url_idx]
                else:
                    base_url = urls[0] if urls else None

                if not base_url:
                    raise ValueError(f"No active URL configured for site '{site_name}'")

                credentials = env_config.get("credentials", {})
                username = credentials.get("username", "")
                password = credentials.get("password", "")

                # Get site-specific login handler
                login_handler = _SITE_LOGIN_HANDLERS.get(site_name)
                if not login_handler:
                    raise ValueError(f"No login handler found for site '{site_name}'")

                logger.info(f"Performing UI login for site '{site_name}' at {base_url}")
                await login_handler(context, base_url, username, password)

            # Save browser storage state (cookies, localStorage, etc.)
            storage_state_file.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(storage_state_file))
            logger.info(f"Saved storage state to: {storage_state_file}")

        finally:
            await context.close()
            await browser.close()


async def _shopping_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    """Shopping site (Magento) login."""
    login_url = f"{base_url}/customer/account/login/"
    logger.info(f"Shopping login URL: {login_url}")

    page = await context.new_page()
    await page.goto(login_url)
    await page.get_by_label("Email", exact=True).fill(username)
    await page.get_by_label("Password", exact=True).fill(password)
    await page.get_by_role("button", name="Sign In").click()
    await page.close()


async def _shopping_admin_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    """Shopping admin site (Magento Admin) login."""
    login_url = base_url
    logger.info(f"Shopping admin login URL: {login_url}")

    page = await context.new_page()
    await page.goto(login_url)
    await page.get_by_label("Username").fill(username)
    await page.get_by_label("Password").fill(password)
    await page.get_by_role("button", name="Sign in").click()
    await page.close()


async def _gitlab_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    """GitLab site login."""
    login_url = f"{base_url}/users/sign_in"
    logger.info(f"GitLab login URL: {login_url}")

    page = await context.new_page()
    await page.goto(login_url)

    if username == "root":
        # Demo site login flow with test IDs
        await page.get_by_test_id("username-field").click()
        await page.get_by_test_id("username-field").fill(username)
        await page.get_by_test_id("username-field").press("Tab")
        await page.get_by_test_id("password-field").fill(password)
        await page.get_by_test_id("sign-in-button").click()
    else:
        await page.get_by_label("Username or email").click()
        await page.get_by_label("Username or email").fill(username, timeout=3000)
        await page.get_by_label("Password").click()
        await page.get_by_label("Password").fill(password)
        await page.get_by_role("button", name="Sign in").click()

    await page.close()


async def _reddit_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    """Reddit site (Postmill) login."""
    login_url = base_url
    logger.info(f"Reddit login URL: {login_url}")

    page = await context.new_page()
    await page.goto(login_url)
    await page.get_by_role("link", name="Log in").click()
    await page.get_by_label("Username").fill(username)
    await page.get_by_label("Password").fill(password)
    await page.get_by_role("button", name="Log in").click()
    await page.close()


async def _wikipedia_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    """Wikipedia - no login needed."""
    logger.info("Wikipedia does not require authentication, skipping login")


async def _map_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    """Map services - no login needed."""
    logger.info("Map services do not require authentication, skipping login")


_SITE_LOGIN_HANDLERS = {
    "shopping": _shopping_ui_login,
    "shopping_admin": _shopping_admin_ui_login,
    "gitlab": _gitlab_ui_login,
    "reddit": _reddit_ui_login,
    "wikipedia": _wikipedia_ui_login,
    "map": _map_ui_login,
}
