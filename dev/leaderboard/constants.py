"""Shared constants for leaderboard submission validators."""

# Hugging Face artifact archive containing all submission task outputs.
HF_SUBMISSION_ARCHIVE_FILE = "submission-payload.tar.zst"
# Checksum sidecar file for the submission archive.
HF_SUBMISSION_SHA256_FILE = "payload.sha256"
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
# Regex pattern used to extract a SHA256 checksum token from payload.sha256.
HF_SHA256_CAPTURE_PATTERN = r"([0-9a-f]{64})"

# Marker file indicating a task has no artifacts.
TASK_MISSING_SENTINEL_FILE = ".missing"
# Agent response payload file required for non-missing tasks.
TASK_AGENT_RESPONSE_FILE = "agent_response.json"
# Network HAR payload file required for non-missing tasks.
TASK_NETWORK_HAR_FILE = "network.har"
