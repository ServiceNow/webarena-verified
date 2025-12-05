import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from playwright.async_api import async_playwright

from examples.agents.utils import STATUS_OPTIONS, TASK_TYPE_OPTIONS, backup_output_dir, parse_args, setup_logging

logger = logging.getLogger("HUMAN-AGENT")


def load_agent_input(tasks_file: Path, task_id: int) -> dict:
    """Load agent input data for a specific task from agent-input-get output.

    Args:
        tasks_file: Path to JSON file with agent inputs (from agent-input-get)
        task_id: Task ID to load

    Returns:
        Dict with keys: task_id, intent_template_id, sites, start_urls, intent

    Raises:
        ValueError: If task_id not found in file or file is empty
        json.JSONDecodeError: If file is not valid JSON
        FileNotFoundError: If file does not exist
    """
    if not tasks_file.exists():
        raise FileNotFoundError(f"Tasks file not found: {tasks_file}")

    try:
        tasks_data = json.loads(tasks_file.read_text())
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in tasks file: {e.msg}", e.doc, e.pos) from e

    if not isinstance(tasks_data, list):
        raise ValueError(f"Tasks file must contain a JSON array, got {type(tasks_data).__name__}")

    if not tasks_data:
        raise ValueError("Tasks file is empty")

    for task in tasks_data:
        if task.get("task_id") == task_id:
            return task

    available_ids = [task.get("task_id") for task in tasks_data]
    raise ValueError(f"Task ID {task_id} not found in tasks file. Available task IDs: {available_ids}")


def print_and_flush(*args, **kwargs) -> None:
    """Print and immediately flush stdout to avoid buffering issues when running as a subprocess."""
    print(*args, **kwargs)
    sys.stdout.flush()


async def init_browser(
    playwright,
    args,
    task_output_dir,
    storage_state_file: Path | None,
):
    """Initialize browser with storage state for authentication."""
    browser = await playwright.chromium.launch(
        headless=False,  # User needs to see the browser
        slow_mo=500,
        args=[
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )

    # Calculate HAR file path in trace directory
    har_path = str(task_output_dir / "network.har")

    # Create context with storage state if provided
    context_kwargs = {
        "viewport": None,  # No fixed viewport - browser will expand to window size
        "no_viewport": True,
        "record_har_path": har_path,
        "record_har_content": "embed",
    }

    if storage_state_file and storage_state_file.exists():
        context_kwargs["storage_state"] = str(storage_state_file)
        logger.info(f"Using storage state from: {storage_state_file}")
    else:
        logger.warning("No storage state file provided - browser will not be authenticated")

    context = await browser.new_context(**context_kwargs)

    # Load and apply headers if they exist (for header-based authentication)
    if storage_state_file and storage_state_file.exists():
        headers_file = Path(str(storage_state_file) + ".headers.json")
        if headers_file.exists():
            logger.info(f"Loading headers from: {headers_file}")
            with open(headers_file) as f:
                headers = json.load(f)
            logger.info(f"Setting {len(headers)} header(s) on context: {list(headers.keys())}")
            await context.set_extra_http_headers(headers)
        else:
            logger.info(f"No headers file found at: {headers_file}")

    return browser, context


async def wait_for_all_pages_closed(context):
    """Wait in a loop until all pages in the context are closed."""
    logger.info("Waiting for all pages to be closed...")

    while True:
        pages = context.pages
        if len(pages) == 0:
            logger.info("All pages closed. Terminating.")
            break

        logger.info(f"Currently {len(pages)} page(s) open. Waiting...")
        await asyncio.sleep(5)


def prompt_choice(label: str, options: list[str]) -> str:
    """Prompt the user to pick an option from a list."""
    print_and_flush(f"{label}:\n")
    for idx, option in enumerate(options, start=1):
        print_and_flush(f"{idx}. {option}")

    while True:
        print_and_flush("\nEnter choice number > ", end="")
        try:
            choice_str = input()
            choice = int(choice_str)
            if 1 <= choice <= len(options):
                print_and_flush()  # Add blank line after valid input
                return options[choice - 1]
            else:
                print_and_flush(f"Error: Please enter a number between 1 and {len(options)}")
        except ValueError:
            print_and_flush(f"Error: Invalid input. Please enter a number between 1 and {len(options)}")


def prompt_yes_no(question: str) -> bool:
    """Prompt the user for a yes/no decision."""
    print_and_flush(f"{question}")
    print_and_flush("  1. Yes")
    print_and_flush("  2. No")

    while True:
        print_and_flush("> ", end="")
        try:
            choice_str = input()
            choice = int(choice_str)
            if choice in [1, 2]:
                print_and_flush()
                return choice == 1
            else:
                print_and_flush("Error: Please enter 1 or 2")
        except ValueError:
            print_and_flush("Error: Invalid input. Please enter 1 or 2")


def prompt_input(label: str) -> str | None:
    """Prompt for a single input value.

    Args:
        label: The prompt label to display

    Returns:
        The input string, or None if empty
    """
    print_and_flush(f"{label} > ", end="")
    value = input().strip()
    print_and_flush()
    return value if value else None


def display_banner(message: str) -> None:
    """Render an attention banner in the CLI."""
    border = "=" * len(message)
    print_and_flush()
    print_and_flush(border)
    print_and_flush(message)
    print_and_flush(border)
    print_and_flush()


def collect_agent_response(task_output_dir: Path) -> None:
    """Ask the operator for final task details and persist the agent response."""
    # Check if AUTO_RESPONSE env var is set
    auto_response = os.environ.get("AUTO_RESPONSE")

    if auto_response:
        logger.info("AUTO_RESPONSE env var detected, using provided response")
        output_path = task_output_dir / "agent_response.json"
        output_path.write_text(auto_response)
        logger.info(f"Wrote agent response from AUTO_RESPONSE to: {output_path.resolve()!s}")
        return

    # Interactive mode
    display_banner("Browser closed. Generating the agent response questionnaire...")

    try:
        while True:
            print_and_flush("-" * 60)
            operation = prompt_choice("Select the performed operation", TASK_TYPE_OPTIONS)

            print_and_flush("-" * 60)
            status = prompt_choice("Select the task status", STATUS_OPTIONS)

            retrieved_data: list[str] | None = None
            if operation == "RETRIEVE":
                print_and_flush("-" * 60)
                data = prompt_input("Enter retrieved data (empty if not applicable)")
                retrieved_data = [data] if data else None

            response_payload = {
                "task_type": operation,
                "status": status,
                "retrieved_data": retrieved_data,
                "error_details": None,
            }

            print_and_flush("\n" + "-" * 60)
            print_and_flush("Proposed agent response:")
            print_and_flush(json.dumps(response_payload, indent=2))
            print_and_flush("-" * 60)

            if prompt_yes_no("Confirm and save this response?"):
                output_path = task_output_dir / "agent_response.json"
                output_path.write_text(json.dumps(response_payload, indent=2))
                logger.info(f"Wrote agent response to: {output_path.resolve()!s}")
                break

            print_and_flush("\nDiscarded response. Restarting questionnaire...")
    except KeyboardInterrupt:
        print_and_flush("\n\nQuestionnaire cancelled by user.")
        logger.warning("Agent response collection cancelled by user (Ctrl+C)")


async def setup_storage_state(args, task_output_dir: Path, agent_input: dict) -> Path | None:
    """Set up storage state file with UI login if config provided.

    Priority:
    1. If --storage-state-file provided: use existing file
    2. If --config provided: perform UI login and generate new storage state
    3. Otherwise: return None (no authentication)

    Args:
        args: Parsed command-line arguments
        task_output_dir: Task output directory
        agent_input: Agent input dict containing 'sites' list

    Returns:
        Path to storage state file, or None if not available
    """
    # Priority 1: Use explicit storage state file if provided
    if args.storage_state_file:
        return Path(args.storage_state_file)

    # Priority 2: Perform UI login if config provided
    if args.config:
        import json

        from examples.agents.utils import ui_login

        # Load config as dict (ui_login uses plain dicts, not Pydantic models)
        with open(args.config) as f:
            config = json.load(f)

        # Define storage state path (default filename from config, or fallback)
        storage_state_filename = config.get("storage_state_file_name", ".storage_state.json")
        storage_state_file = task_output_dir / storage_state_filename

        # Perform UI login (generates storage_state_file)
        sites = agent_input["sites"]  # Already strings, no enum conversion needed
        logger.info(f"Performing UI login for sites: {sites}")
        await ui_login(
            sites=sites,
            config=config,
            storage_state_file=storage_state_file,
        )
        logger.info(f"Storage state saved to: {storage_state_file}")

        return storage_state_file

    # Priority 3: No authentication
    return None


async def main():
    args = parse_args()

    task_output_dir = Path(args.task_output_dir)

    # Backup existing output directory if it exists
    backup_output_dir(task_output_dir, args.task_id)

    task_output_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(logger=logger, task_output_dir=task_output_dir)

    logger.info("Human Agent started")

    logger.info(f"Loading agent input for task {args.task_id}")
    agent_input = load_agent_input(Path(args.tasks_file), args.task_id)

    logger.info(f"Task sites: {agent_input['sites']}")
    logger.info(f"Task intent: {agent_input['intent']}")
    logger.info(f"Start URLs: {agent_input['start_urls']}")

    storage_state_file = await setup_storage_state(args, task_output_dir, agent_input)

    async with async_playwright() as p:
        browser, context = await init_browser(p, args, task_output_dir, storage_state_file)

        try:
            logger.info("Navigating to start URLs")
            for url in agent_input["start_urls"]:
                page = await context.new_page()
                logger.info(f"Navigating to {url}")
                await page.goto(url)

            if not os.environ.get("AUTO_RESPONSE"):
                display_banner("Browser setup complete. It's your turn to work on the task.")

            await wait_for_all_pages_closed(context)
            logger.info("Browser terminated")

        except Exception as e:
            logger.error(f"Error during execution: {e}")
        finally:
            har_path = task_output_dir / "network.har"
            logger.info(f"Wrote HAR file to: {str(har_path.resolve())!r}")

            await context.close()
            await browser.close()
            logger.info("Browser closed")

    collect_agent_response(task_output_dir)

    logger.info("Human Agent terminated")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
