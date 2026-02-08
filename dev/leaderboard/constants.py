"""Shared constants for leaderboard submission validators."""

import re
from pathlib import Path

# Hugging Face artifact archive containing all submission task outputs.
HF_SUBMISSION_ARCHIVE_FILE = "submission-payload.tar.gz"
# Checksum sidecar file for the submission archive.
HF_SUBMISSION_SHA256_FILE = "submission-payload.sha256"
# Submission metadata payload file.
HF_SUBMISSION_METADATA_FILE = "metadata.json"
# Submission manifest payload file.
HF_SUBMISSION_MANIFEST_FILE = "manifest.json"
# Required files expected in each linked HF submission payload directory.
HF_REQUIRED_SUBMISSION_FILES = (
    HF_SUBMISSION_ARCHIVE_FILE,
    HF_SUBMISSION_SHA256_FILE,
    HF_SUBMISSION_METADATA_FILE,
    HF_SUBMISSION_MANIFEST_FILE,
)
# Regex pattern used to extract a SHA256 checksum token from the checksum sidecar file.
HF_SHA256_CAPTURE_PATTERN = r"([0-9a-f]{64})"

# Validation regex used by leaderboard model helpers.
RFC3339_UTC_Z_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Marker file indicating a task has no artifacts.
TASK_MISSING_SENTINEL_FILE = ".missing"
# Agent response payload file required for non-missing tasks.
TASK_AGENT_RESPONSE_FILE = "agent_response.json"
# Network HAR payload file required for non-missing tasks.
TASK_NETWORK_HAR_FILE = "network.har"

# Required HF discussion title prefix for leaderboard submission pull requests.
HF_SUBMISSION_DISCUSSION_TITLE_PREFIX = "Leaderboard Submission: "

# Root directory for submission control-plane records.
LEADERBOARD_SUBMISSIONS_ROOT = Path("leaderboard/data/submissions")

# Markers used to classify transient validation failures that should be retried.
HF_SYNC_TRANSIENT_ERROR_MARKERS = ("fail-closed", "unable to verify", "timeout", "temporar", "connection")
