"""Template rendering helpers for leaderboard sync comments."""

from __future__ import annotations

from pathlib import Path


class TemplateRenderer:
    """Load and render markdown templates used in status comments."""

    def render_markdown_template(self, template_path: str, **context: str) -> str:
        """Render template with named variables and trim surrounding whitespace."""
        template = Path(template_path).read_text(encoding="utf-8")
        try:
            return template.format(**context).strip()
        except KeyError as exc:
            raise RuntimeError(f"Missing template variable '{exc.args[0]}' in {template_path}") from exc
