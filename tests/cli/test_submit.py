import argparse
from pathlib import Path
from unittest.mock import Mock, patch

from webarena_verified.__main__ import submit_cmd
from webarena_verified.types.submit_result import SubmitResult


def _args(
    *,
    submission_dir: str,
    name: str = "TeamX/ModelY",
    leaderboard: str = "both",
    reference: str = "https://example.com/paper",
    version: str | None = None,
    contact_info: str | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        submission_dir=submission_dir,
        name=name,
        leaderboard=leaderboard,
        reference=reference,
        version=version,
        contact_info=contact_info,
    )


def test_submit_missing_submission_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test_token")
    args = _args(submission_dir=str(tmp_path / "missing"))

    exit_code = submit_cmd(args)

    assert exit_code == 1


def test_submit_success_output(monkeypatch, capsys):
    monkeypatch.setenv("HF_TOKEN", "hf_test_token")
    monkeypatch.setenv("WEBARENA_VERIFIED_LEADERBOARD_SUBMISSION_HF_REPO", "org/repo")

    result = SubmitResult(
        pr_url="https://huggingface.co/datasets/org/repo/discussions/42",
        pr_number=42,
        submission_uid="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
        hf_repo="org/repo",
        submission_dir="/tmp/submission",
        tasks_submitted=12,
    )

    handler_instance = Mock()
    handler_instance.submit.return_value = result

    with patch("webarena_verified.__main__.SubmitHandler", return_value=handler_instance):
        exit_code = submit_cmd(_args(submission_dir="./submissions/sample"))

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "https://huggingface.co/datasets/org/repo/discussions/42" in output


def test_submit_parser_registration():
    from webarena_verified.__main__ import create_parser

    parser = create_parser()
    args = parser.parse_args(
        [
            "submit",
            "--submission-dir",
            "./submissions/sample",
            "--name",
            "TeamX/ModelY",
            "--leaderboard",
            "both",
            "--reference",
            "https://example.com/paper",
        ]
    )

    assert args.command == "submit"
    assert args.submission_dir == "./submissions/sample"
    assert args.reference == "https://example.com/paper"
