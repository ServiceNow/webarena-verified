"""Site-specific operations modules."""

from __future__ import annotations

from .dummy import DummyOps
from .gitlab import GitlabOps
from .map import MapOps
from .reddit import RedditOps
from .shopping import ShoppingOps
from .shopping_admin import ShoppingAdminOps
from .wikipedia import WikipediaOps

__all__ = ["DummyOps", "GitlabOps", "MapOps", "RedditOps", "ShoppingAdminOps", "ShoppingOps", "WikipediaOps"]
