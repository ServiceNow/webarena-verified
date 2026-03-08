"""Leaderboard infrastructure scripts (not part of the client-facing package).

This package contains the server-side pipeline that turns Hugging Face dataset
pull-request submissions into ranked leaderboard artifacts.  The pipeline is
triggered by GitHub Actions (``leaderboard-hf-ingest.yml``) and proceeds
through the following stages:

1. **Ingest** – ``submission_handler`` downloads a HF snapshot, validates
   the submission tree, and hands it to the evaluator.
2. **Evaluate** – ``submission_evaluator`` runs the WebArena-Verified
   evaluators against every task in the submission and produces per-mode
   (full / hard) scoring summaries.
3. **Build** – ``leaderboard_builder`` merges new scores into the existing
   leaderboard tables, re-ranks, and writes generation artifacts
   (``full.json``, ``hard.json``, ``latest.json``).
4. **CLI** – ``tasks`` exposes Invoke tasks that GitHub Actions and
   maintainers use to drive the above stages.

All modules here import from ``webarena_verified.submission`` (config,
models, validator) but the client package never imports from here, keeping a
strict one-way dependency.
"""

from .tasks import rebuild_leaderboard_artifacts

__all__ = ["rebuild_leaderboard_artifacts"]
