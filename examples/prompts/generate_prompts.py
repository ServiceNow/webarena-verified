"""Utility to generate prompt files from templates.

This module provides utilities to generate WebArena agent prompt files from a Jinja2 template
and site-specific configuration. The prompts are automatically generated for all site combinations
found in the webarena-verified.json dataset.

Architecture:
- base_template.md.jinja2: Single Jinja2 template for all prompts (single-site and multi-site)
- site_config.py: Site metadata (platform names, descriptions, authentication messages)
- generate_prompts.py: Generation logic (this file)

Usage:
    # Generate all prompts from dataset
    python examples/prompts/generate_prompts.py

    # Or from Python
    from examples.prompts.generate_prompts import generate_all_prompts, generate_prompt
    from webarena_verified.types.config import WebArenaSite

    # Generate all prompts
    generate_all_prompts()

    # Generate specific prompt
    prompt = generate_prompt([WebArenaSite.SHOPPING, WebArenaSite.REDDIT])

Modifying prompts:
1. To change common sections (Task Input, Operational Constraints):
   Edit base_template.md.jinja2

2. To change site-specific info (descriptions, auth messages):
   Edit SITE_METADATA in site_config.py

3. To add a new site:
   Add entry to SITE_METADATA in site_config.py

4. After changes, regenerate all prompts:
   python examples/prompts/generate_prompts.py

SECURITY NOTE:
    Credentials in SITE_METADATA (site_config.py) are for LOCAL TEST INSTANCES ONLY.
    These prompts are used with Docker-based test environments.
"""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from webarena_verified.types.config import WebArenaSite

# Handle both module and script imports
try:
    from .site_config import SITE_METADATA
except ImportError:
    from site_config import SITE_METADATA


def generate_prompt(sites: list[WebArenaSite]) -> str:
    """Generate a prompt for given site(s).

    Args:
        sites: List of WebArenaSite enums to generate prompt for

    Returns:
        Generated prompt content as string
    """
    # Load template
    template_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("base_template.md.jinja2")

    # Prepare site data
    site_data = [SITE_METADATA[site] for site in sorted(sites, key=lambda s: s.value)]

    # Render template
    return template.render(sites=site_data)


def generate_all_prompts(output_dir: Path | None = None) -> None:
    """Generate all prompt files from dataset site combinations.

    Scans the webarena-verified.json dataset to find all unique site combinations
    and generates a prompt file for each.

    Args:
        output_dir: Directory to write prompt files to. Defaults to prompts directory.
    """
    if output_dir is None:
        output_dir = Path(__file__).parent

    # Get all unique site combinations from dataset
    dataset_path = Path(__file__).parent.parent.parent / "assets" / "dataset" / "webarena-verified.json"
    with open(dataset_path) as f:
        data = json.load(f)

    site_combinations = set()
    for task in data:
        sites = task.get("sites", [])
        if sites:
            site_combination = tuple(sorted([WebArenaSite(s) for s in sites], key=lambda s: s.value))
            site_combinations.add(site_combination)

    # Generate each prompt file
    for sites in sorted(site_combinations):
        filename = "-".join(sorted([s.value for s in sites])) + ".md"
        prompt_content = generate_prompt(list(sites))

        output_path = output_dir / filename
        output_path.write_text(prompt_content)
        print(f"Generated: {filename}")

    print(f"\nTotal prompts generated: {len(site_combinations)}")


if __name__ == "__main__":
    generate_all_prompts()
