#!/usr/bin/env python3
"""
Remove rate limiting from Reddit (Postmill) submissions.

This script removes the rate limiting annotations from the SubmissionData class
to allow unlimited post submissions without waiting periods.

Usage:
    As module: apply_patch(handler)
    As script: python p01_remove_rate_limits.py
"""

import logging

from webarena_verified.environments import SiteInstanceHandler

logger = logging.getLogger(__name__)


def backup_submission_data(handler: SiteInstanceHandler) -> None:
    """Backup the SubmissionData.php file."""
    file_path = "/var/www/html/src/DataObject/SubmissionData.php"
    backup_path = f"{file_path}.bak"

    handler.exec_cmd(
        ["cp", file_path, backup_path],
        check=True,
    )
    logger.info(f"Backed up {file_path} to {backup_path}")


def remove_rate_limits(handler: SiteInstanceHandler) -> None:
    """Remove rate limit annotations from SubmissionData.php."""
    file_path = "/var/www/html/src/DataObject/SubmissionData.php"

    # Read the current file
    result = handler.exec_cmd(
        ["cat", file_path],
        capture_output=True,
        text=True,
        check=True,
    )

    content = result.stdout
    lines = content.split("\n")
    new_lines = []
    skip_next = False

    for _i, line in enumerate(lines):
        # Skip lines with @RateLimit annotation
        if "@RateLimit" in line:
            # Check if this is a single-line or multi-line annotation
            if line.strip().endswith(")"):
                # Single line, skip it
                continue
            else:
                # Multi-line annotation, mark to skip until we find the closing paren
                skip_next = True
                continue

        if skip_next:
            # Continue skipping until we find the end of the annotation
            if ")" in line:
                skip_next = False
            continue

        new_lines.append(line)

    # Write the modified content back
    new_content = "\n".join(new_lines)

    handler.exec_cmd(
        ["tee", file_path],
        input_data=new_content,
        capture_output=True,
        check=True,
    )
    logger.info(f"Removed rate limit annotations from {file_path}")


def clear_symfony_cache(handler: SiteInstanceHandler) -> None:
    """Clear Symfony cache to apply changes."""
    handler.exec_cmd(
        ["php", "bin/console", "cache:clear"],
        capture_output=True,
        check=True,
    )
    logger.info("Cleared Symfony cache")


def verify_changes(handler: SiteInstanceHandler) -> bool:
    """Verify that rate limits were removed."""
    file_path = "/var/www/html/src/DataObject/SubmissionData.php"

    result = handler.exec_cmd(
        ["grep", "-c", "@RateLimit", file_path],
        capture_output=True,
        text=True,
    )

    # grep returns exit code 1 if no matches found (which is what we want)
    if result.returncode == 1:
        logger.info("Rate limit annotations successfully removed")
        return True
    else:
        count = result.stdout.strip()
        logger.warning(f"Still found {count} @RateLimit annotation(s)")
        return False


def restart_php_fpm(handler: SiteInstanceHandler) -> None:
    """Restart PHP-FPM to reload the code."""
    handler.exec_cmd(
        ["supervisorctl", "restart", "php-fpm"],
        check=True,
    )
    logger.info("Restarted PHP-FPM")


def apply_patch(handler: SiteInstanceHandler) -> bool:
    """Apply the rate limit removal patch.

    Args:
        handler: SiteInstanceHandler for executing commands

    Returns:
        True if patch was applied successfully, False otherwise
    """
    try:
        logger.info("Removing Reddit post rate limiting...")

        # Backup original file
        backup_submission_data(handler)

        # Remove rate limits
        remove_rate_limits(handler)

        # Clear cache
        clear_symfony_cache(handler)

        # Verify
        if not verify_changes(handler):
            logger.error("Patch verification failed")
            return False

        # Restart PHP-FPM
        restart_php_fpm(handler)

        logger.info("Rate limiting removal patch applied successfully")
        return True

    except Exception as e:
        logger.error(f"Error applying patch: {e}")
        return False
