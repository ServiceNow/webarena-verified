"""Mixins for container operations.

This module is stdlib-only and can be used both:
- Inside container: by environment_control
- Outside container: by invoke tasks (wrapping commands with docker exec)
"""

from __future__ import annotations

from .supervisor import SupervisorMixin

__all__ = ["SupervisorMixin"]
