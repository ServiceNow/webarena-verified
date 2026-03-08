from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from webarena_verified.submission.models import (  # noqa: TC001
    RelativePath,
    Sha256Hex,
    SubmissionMode,
    SubmissionUid,
    UtcZ,
)
from webarena_verified.types.leaderboard._validators import validate_http_url


class ScoreField(StrEnum):
    """Canonical names for the per-site score columns on the leaderboard.

    Used by ``LeaderboardBuilder`` and ``SubmissionEvaluator`` to reference
    score dimensions consistently when building ``EvaluationScores`` and
    ``LeaderboardRow`` instances.
    """

    OVERALL = "overall"
    SHOPPING = "shopping"
    SHOPPING_ADMIN = "shopping_admin"
    GITLAB = "gitlab"
    MAP = "map"
    REDDIT = "reddit"
    MULTISITE = "multisite"
    GITLAB_REDDIT = "gitlab_reddit"


class OverallCounts(BaseModel):
    """Aggregate task-level counts across all sites for one evaluation mode.

    Produced by ``SubmissionEvaluator._build_counts`` as part of the
    ``EvaluationSummaryCounts`` breakdown.  Tracks how many tasks succeeded,
    failed, or errored, along with the expected total (so missing tasks can
    be detected).
    """

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    failed_or_error_count: int = Field(ge=0)
    expected_total: int = Field(ge=0, default=0)
    missing_count: int = Field(ge=0, default=0)


class SiteCounts(BaseModel):
    """Per-site task-level counts for one evaluation mode.

    Same shape as ``OverallCounts`` but scoped to a single site key (e.g.
    ``"shopping"``, ``"gitlab-reddit"``).  Collected in the ``per_site``
    dict of ``EvaluationSummaryCounts``.
    """

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    failed_or_error_count: int = Field(ge=0)
    expected_total: int = Field(ge=0, default=0)
    missing_count: int = Field(ge=0, default=0)


class EvaluationSummaryCounts(BaseModel):
    """Combined overall + per-site task counts for one evaluation run.

    Wraps ``OverallCounts`` and a ``per_site`` mapping of ``SiteCounts``.
    Embedded inside ``EvaluationSummaryPayload`` to give a complete
    statistical picture of the evaluation before scores are derived.
    """

    model_config = ConfigDict(extra="forbid")

    overall: OverallCounts
    per_site: dict[str, SiteCounts]


class EvaluationScores(BaseModel):
    """Normalised success-rate scores (0.0-1.0) broken down by site.

    Computed by ``SubmissionEvaluator._build_scores`` from raw task results.
    The ``overall`` field is the aggregate across all tasks; remaining fields
    are per-site ratios.  These scores are carried forward into
    ``LeaderboardRow`` for ranking.
    """

    model_config = ConfigDict(extra="forbid")

    overall: float = Field(ge=0.0, le=1.0)
    shopping: float = Field(ge=0.0, le=1.0)
    shopping_admin: float = Field(ge=0.0, le=1.0)
    gitlab: float = Field(ge=0.0, le=1.0)
    map: float = Field(ge=0.0, le=1.0)
    reddit: float = Field(ge=0.0, le=1.0)
    multisite: float = Field(ge=0.0, le=1.0)
    gitlab_reddit: float = Field(ge=0.0, le=1.0)


class EvaluationSummaryPayload(BaseModel):
    """Full evaluation output for one submission mode (full or hard).

    Created by ``SubmissionEvaluator._build_summary`` after all tasks have
    been evaluated.  Contains version/checksum metadata for reproducibility,
    the raw ``summary`` counts, and the derived ``scores``.  Passed to
    ``LeaderboardBuilder.apply_submission_result`` to update the leaderboard.
    """

    model_config = ConfigDict(extra="forbid")

    timestamp: UtcZ
    webarena_verified_version: str = Field(min_length=1)
    webarena_verified_evaluator_checksum: str = Field(min_length=1)
    webarena_verified_data_checksum: str = Field(min_length=1)
    summary: EvaluationSummaryCounts
    scores: EvaluationScores


class SubmissionEvaluationRecord(BaseModel):
    """Denormalised record linking a submission to its evaluation scores.

    Combines submission identity (uid, name, model, source URL) with the
    ``EvaluationScores`` produced during evaluation.  Used as an intermediate
    representation before the scores are merged into leaderboard rows.
    """

    model_config = ConfigDict(extra="forbid")

    submission_uid: SubmissionUid
    submission_mode: SubmissionMode
    generated_at_utc: UtcZ
    source_sha: str = Field(min_length=1)
    source: Annotated[str, AfterValidator(lambda value: validate_http_url(value, "source"))]
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    scores: EvaluationScores


class LeaderboardRow(BaseModel):
    """One ranked entry in a leaderboard generation artifact.

    Represents a single submission's position and scores on either the full
    or hard leaderboard.  Rows are ranked by ``overall`` score (descending)
    inside ``LeaderboardBuilder._rank_rows`` and serialised into the
    generation JSON files that the leaderboard UI consumes.
    """

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    submission_uid: SubmissionUid
    name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    overall: float = Field(ge=0.0, le=1.0)
    shopping: float = Field(ge=0.0, le=1.0)
    shopping_admin: float = Field(ge=0.0, le=1.0)
    gitlab: float = Field(ge=0.0, le=1.0)
    map: float = Field(ge=0.0, le=1.0)
    reddit: float = Field(ge=0.0, le=1.0)
    multisite: float = Field(ge=0.0, le=1.0)
    gitlab_reddit: float = Field(ge=0.0, le=1.0)
    source: Annotated[str, AfterValidator(lambda value: validate_http_url(value, "source"))]


class LeaderboardGenerationArtifact(BaseModel):
    """Versioned snapshot of a complete leaderboard table (full or hard).

    Written by ``LeaderboardBuilder._write_leaderboard_artifacts`` as
    ``full.json`` / ``hard.json`` inside a generation directory.  Contains
    all ranked rows, a generation ID, and a self-checksum for integrity
    verification.  The leaderboard UI reads this file to render the table.
    """

    model_config = ConfigDict(extra="forbid")

    generation_id: str = Field(min_length=1)
    leaderboard: SubmissionMode
    generated_at_utc: UtcZ
    rows_count: int = Field(ge=0)
    rows: list[LeaderboardRow]
    checksum: Sha256Hex
    checksum_algo: str = Field(min_length=1)


class LeaderboardLatestArtifact(BaseModel):
    """Pointer file (``latest.json``) that links to the current generation.

    Written alongside each generation by ``LeaderboardBuilder``.  Contains
    the ``generation_id``, relative paths to the full and hard generation
    files, their SHA-256 digests, and a self-checksum.  The leaderboard UI
    reads this file to locate the active generation.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    generated_at_utc: UtcZ
    full_file: RelativePath
    hard_file: RelativePath
    full_sha256: Sha256Hex
    hard_sha256: Sha256Hex
    checksum: Sha256Hex
    checksum_algo: str = Field(min_length=1)


class IngestResult(BaseModel):
    """Return value of ``ingest_hf_submission`` after a successful ingest.

    Carries the paths to the three files written by the leaderboard builder
    (``latest.json``, ``full.json``, ``hard.json``) so the calling CI job
    can commit exactly those paths to the ``leaderboard-submissions`` branch.
    """

    model_config = ConfigDict(extra="forbid")

    submission_uid: SubmissionUid
    leaderboard_latest_path: str = Field(min_length=1)
    full_artifact_path: str = Field(min_length=1)
    hard_artifact_path: str = Field(min_length=1)
