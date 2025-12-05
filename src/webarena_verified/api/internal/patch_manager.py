"""Patch manager for WebArena environment patches.

This module provides functionality to discover, manage, and apply patches to
WebArena environment containers. Patches are organized by site (reddit, shopping,
shopping_admin, etc.) and applied in order based on filename prefix.
"""

import importlib.util
import logging
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class PatchManager:
    """Manager for discovering and applying environment patches.

    Patches are organized in the following structure:
        patches/
            reddit/
                p01_remove_rate_limits.py
                p02_configure_http_client.py
            shopping/
                p01_contact_form.py
            shopping_admin/
                p01_autologin_session.py

    Patch files must follow the naming pattern p<int>_*.py (e.g., p01_example.py).
    Each patch module must expose an `apply_patch(handler) -> bool` function that receives
    a SiteInstanceHandler for executing commands on the target environment.
    """

    def __init__(self, exec_patch: Callable[..., bool], patches_dir: Path | None = None):
        """Initialize the patch manager.

        Args:
            exec_patch: Function to execute patches. Should have signature:
                       exec_patch(patch_fn: Callable, site: str, **kwargs) -> bool
                       The executor is responsible for Docker operations and calling patch_fn
            patches_dir: Path to the patches directory. If None, uses the default
                        patches directory relative to this module.
        """
        if patches_dir is None:
            # Default to patches directory in environments
            patches_dir = Path(__file__).parent.parent.parent / "environments" / "patches"

        self.exec_patch = exec_patch
        self.patches_dir = patches_dir
        logger.debug(f"Initialized PatchManager with patches directory: {patches_dir}")

    def discover_patches(self, site: str) -> list[tuple[str, Callable[[str], bool]]]:
        """Discover all patches for a given site.

        Args:
            site: Site identifier (e.g., "reddit", "shopping")

        Returns:
            List of (patch_name, apply_patch_function) tuples, sorted by filename

        Raises:
            ValueError: If a patch file matching p<int>_*.py pattern is invalid
                       (missing apply_patch function or apply_patch is not callable)
        """
        site_dir = self.patches_dir / site
        if not site_dir.exists() or not site_dir.is_dir():
            logger.warning(f"No patches directory found for site '{site}' at {site_dir}")
            return []

        patches = []

        # Find all Python files matching p<int>_*.py pattern
        for patch_file in sorted(site_dir.glob("p[0-9]*.py")):
            if patch_file.name.startswith("__"):
                continue

            # Load the module
            try:
                spec = importlib.util.spec_from_file_location(
                    f"webarena_verified.environments.patches.{site}.{patch_file.stem}",
                    patch_file,
                )
                if spec is None or spec.loader is None:
                    logger.warning(f"Could not load spec for patch: {patch_file}")
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Get the apply_patch function
                if not hasattr(module, "apply_patch"):
                    raise ValueError(
                        f"Patch {patch_file.name} does not have an 'apply_patch' function. "
                        f"All patches matching p<int>_*.py must expose an apply_patch(handler) -> bool function."
                    )

                apply_patch = module.apply_patch
                if not callable(apply_patch):
                    raise ValueError(
                        f"Patch {patch_file.name} has 'apply_patch' attribute but it's not callable. "
                        f"The apply_patch must be a function with signature: apply_patch(handler) -> bool"
                    )

                patches.append((patch_file.stem, apply_patch))
                logger.debug(f"Discovered patch: {site}/{patch_file.name}")

            except Exception as e:
                logger.error(f"Error loading patch {patch_file.name}: {e}")
                continue

        logger.info(f"Discovered {len(patches)} patch(es) for site '{site}'")
        return patches

    def apply_patches_for_site(self, site: str) -> bool:
        """Apply all patches for a given site.

        Args:
            site: Site identifier (e.g., "reddit", "shopping")

        Returns:
            True if all patches applied successfully, False otherwise

        Note:
            Patches are applied in alphabetical order by filename. Use numeric prefixes
            (e.g., 01_, 02_) to control ordering.

            If any patch fails, the process stops immediately and returns False.

            The exec_patch function provided during initialization is responsible for
            Docker operations (container discovery, docker exec, etc.) and calling the patch function.
        """
        # Discover patches
        patches = self.discover_patches(site)
        if not patches:
            logger.info(f"No patches to apply for site '{site}'")
            return True

        logger.info(f"Applying {len(patches)} patch(es) for site '{site}'")

        # Apply patches in order using the injected exec_patch function
        for patch_name, apply_patch in patches:
            logger.info(f"Applying patch: {site}/{patch_name}")
            try:
                success = self.exec_patch(apply_patch, site, patch_name=patch_name)
                if not success:
                    logger.error(f"Patch {site}/{patch_name} failed to apply")
                    return False
                logger.info(f"Successfully applied patch: {site}/{patch_name}")
            except Exception as e:
                logger.error(f"Error applying patch {site}/{patch_name}: {e}")
                return False

        logger.info(f"All patches applied successfully for site '{site}'")
        return True
