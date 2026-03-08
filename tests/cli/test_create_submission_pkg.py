import argparse
import json
import shutil
from pathlib import Path

import pytest

from webarena_verified.__main__ import create_parser, create_submission_pkg
from webarena_verified.api import WebArenaVerified
from webarena_verified.types.data import TaskSubset
from webarena_verified.utils import get_package_assets_path


@pytest.fixture
def create_task_output(har_file_example: Path):
    def _create(
        base_dir: Path,
        task_id: int,
        *,
        include_agent_response: bool = True,
        include_har: bool = True,
        invalid_har: bool = False,
        empty_agent_response: bool = False,
    ) -> Path:
        task_dir = base_dir / str(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        if include_agent_response:
            agent_response = {} if empty_agent_response else {"answer": f"test answer {task_id}"}
            task_dir.joinpath("agent_response.json").write_text(json.dumps(agent_response, indent=2), encoding="utf-8")

        if include_har:
            if invalid_har:
                task_dir.joinpath("network.har").write_text("invalid json {{{", encoding="utf-8")
            else:
                shutil.copy2(har_file_example, task_dir / "network.har")

        return task_dir

    return _create


@pytest.fixture
def leaderboard_task_ids() -> dict[str, int]:
    wa = WebArenaVerified()
    full_ids = sorted(task.task_id for task in wa.get_tasks())

    hard_subset_path = get_package_assets_path() / "dataset" / "subsets" / "webarena-verified-hard.json"
    hard_ids = sorted(TaskSubset.from_file(hard_subset_path).task_ids)

    non_hard_ids = sorted(set(full_ids) - set(hard_ids))
    if not hard_ids or not non_hard_ids:
        pytest.skip("Unable to resolve hard/non-hard task IDs for leaderboard packaging tests")

    return {
        "full_a": full_ids[0],
        "full_b": full_ids[1],
        "full_c": full_ids[2],
        "hard": hard_ids[0],
        "non_hard": non_hard_ids[0],
    }


@pytest.fixture
def mock_args():
    def _create(run_output_dir, output, *, force: bool = False, leaderboard: str = "full"):
        if isinstance(run_output_dir, (str, Path)):
            run_output_dir = [str(run_output_dir)]
        else:
            run_output_dir = [str(d) for d in run_output_dir]

        return argparse.Namespace(
            run_output_dir=run_output_dir,
            output=str(output),
            force=force,
            leaderboard=leaderboard,
        )

    return _create


def test_create_submission_single_directory_full_success(tmp_path, create_task_output, mock_args, leaderboard_task_ids):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    create_task_output(output_dir, leaderboard_task_ids["full_a"])
    create_task_output(output_dir, leaderboard_task_ids["full_b"])
    create_task_output(output_dir, leaderboard_task_ids["full_c"])

    submission_dir = tmp_path / "submission"
    args = mock_args(run_output_dir=output_dir, output=submission_dir, leaderboard="full")

    exit_code = create_submission_pkg(args)
    assert exit_code == 0

    assert submission_dir.is_dir()
    assert not (submission_dir / "summary.json").exists()
    assert (submission_dir / "submission.json").exists()
    assert (submission_dir / "manifest.json").exists()

    payload = json.loads((submission_dir / "submission.json").read_text(encoding="utf-8"))
    assert payload["leaderboard"] == "full"
    assert payload["packaged_tasks"]["full"]["valid"] == 3
    assert payload["packaged_tasks"]["full"]["incomplete"] == 0


def test_create_submission_direct_output_path(tmp_path, create_task_output, mock_args, leaderboard_task_ids):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    create_task_output(output_dir, leaderboard_task_ids["full_a"])

    submission_path = tmp_path / "my-submission"
    args = mock_args(run_output_dir=output_dir, output=submission_path, leaderboard="full")

    exit_code = create_submission_pkg(args)
    assert exit_code == 0

    payload = json.loads((submission_path / "submission.json").read_text(encoding="utf-8"))
    assert payload["name"].startswith("<EDIT:")
    assert payload["reference"].startswith("<EDIT:")
    assert payload["leaderboard"] == "full"
    assert set(payload["packaged_tasks"].keys()) == {"full"}


def test_create_submission_multiple_directories(tmp_path, create_task_output, mock_args, leaderboard_task_ids):
    output_dir1 = tmp_path / "output1"
    output_dir2 = tmp_path / "output2"
    output_dir1.mkdir()
    output_dir2.mkdir()

    create_task_output(output_dir1, leaderboard_task_ids["full_a"])
    create_task_output(output_dir2, leaderboard_task_ids["full_b"])

    submission_dir = tmp_path / "submission"
    args = mock_args(run_output_dir=[output_dir1, output_dir2], output=submission_dir, leaderboard="full")

    exit_code = create_submission_pkg(args)
    assert exit_code == 0

    assert (submission_dir / str(leaderboard_task_ids["full_a"]) / "agent_response.json").exists()
    assert (submission_dir / str(leaderboard_task_ids["full_b"]) / "agent_response.json").exists()


def test_create_submission_missing_agent_response_counts_incomplete(
    tmp_path, create_task_output, mock_args, leaderboard_task_ids
):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    create_task_output(output_dir, leaderboard_task_ids["full_a"])
    create_task_output(output_dir, leaderboard_task_ids["full_b"], include_agent_response=False)

    submission_dir = tmp_path / "submission"
    args = mock_args(run_output_dir=output_dir, output=submission_dir, leaderboard="full")

    exit_code = create_submission_pkg(args)
    assert exit_code == 0

    payload = json.loads((submission_dir / "submission.json").read_text(encoding="utf-8"))
    assert payload["packaged_tasks"]["full"]["valid"] == 1
    assert payload["packaged_tasks"]["full"]["incomplete"] == 1


def test_create_submission_missing_har_counts_incomplete(tmp_path, create_task_output, mock_args, leaderboard_task_ids):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    create_task_output(output_dir, leaderboard_task_ids["full_a"])
    create_task_output(output_dir, leaderboard_task_ids["full_b"], include_har=False)

    submission_dir = tmp_path / "submission"
    args = mock_args(run_output_dir=output_dir, output=submission_dir, leaderboard="full")

    exit_code = create_submission_pkg(args)
    assert exit_code == 0

    payload = json.loads((submission_dir / "submission.json").read_text(encoding="utf-8"))
    assert payload["packaged_tasks"]["full"]["valid"] == 1
    assert payload["packaged_tasks"]["full"]["incomplete"] == 1


def test_create_submission_invalid_har_is_copied_without_trimming(
    tmp_path, create_task_output, mock_args, leaderboard_task_ids
):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    create_task_output(output_dir, leaderboard_task_ids["full_a"])
    create_task_output(output_dir, leaderboard_task_ids["full_b"], invalid_har=True)

    submission_dir = tmp_path / "submission"
    args = mock_args(run_output_dir=output_dir, output=submission_dir, leaderboard="full")

    exit_code = create_submission_pkg(args)
    assert exit_code == 0
    assert (submission_dir / str(leaderboard_task_ids["full_b"]) / "network.har").read_text(encoding="utf-8") == (
        "invalid json {{{"
    )


def test_create_submission_output_exists_without_force(tmp_path, create_task_output, mock_args, leaderboard_task_ids):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    create_task_output(output_dir, leaderboard_task_ids["full_a"])

    submission_dir = tmp_path / "duplicate-test"
    args = mock_args(run_output_dir=output_dir, output=submission_dir, leaderboard="full")

    assert create_submission_pkg(args) == 0
    assert create_submission_pkg(args) == 1


def test_create_submission_output_exists_with_force(tmp_path, create_task_output, mock_args, leaderboard_task_ids):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    create_task_output(output_dir, leaderboard_task_ids["full_a"])

    submission_dir = tmp_path / "force-test"
    args = mock_args(run_output_dir=output_dir, output=submission_dir, leaderboard="full")
    assert create_submission_pkg(args) == 0

    stale_file = submission_dir / "stale.txt"
    stale_file.write_text("stale", encoding="utf-8")

    force_args = mock_args(run_output_dir=output_dir, output=submission_dir, force=True, leaderboard="full")
    assert create_submission_pkg(force_args) == 0
    assert not stale_file.exists()


def test_create_submission_no_valid_tasks_fails(tmp_path, mock_args):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    submission_dir = tmp_path / "no-tasks"
    args = mock_args(run_output_dir=output_dir, output=submission_dir, leaderboard="full")

    exit_code = create_submission_pkg(args)
    assert exit_code == 1


def test_create_submission_hard_only_packages_hard_tasks(tmp_path, create_task_output, mock_args, leaderboard_task_ids):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    create_task_output(output_dir, leaderboard_task_ids["hard"])
    create_task_output(output_dir, leaderboard_task_ids["non_hard"])

    submission_dir = tmp_path / "hard-only"
    args = mock_args(run_output_dir=output_dir, output=submission_dir, leaderboard="hard")

    exit_code = create_submission_pkg(args)
    assert exit_code == 0

    assert (submission_dir / str(leaderboard_task_ids["hard"]) / "agent_response.json").exists()
    assert not (submission_dir / str(leaderboard_task_ids["non_hard"]) / "agent_response.json").exists()

    payload = json.loads((submission_dir / "submission.json").read_text(encoding="utf-8"))
    assert payload["leaderboard"] == "hard"
    assert set(payload["packaged_tasks"].keys()) == {"hard"}
    assert payload["packaged_tasks"]["hard"]["valid"] == 1


def test_create_submission_both_fails_when_hard_has_zero_valid(
    tmp_path, create_task_output, mock_args, leaderboard_task_ids
):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    create_task_output(output_dir, leaderboard_task_ids["non_hard"])

    submission_dir = tmp_path / "both-no-hard"
    args = mock_args(run_output_dir=output_dir, output=submission_dir, leaderboard="both")

    exit_code = create_submission_pkg(args)
    assert exit_code == 1
    assert not submission_dir.exists()


def test_create_submission_parser_defaults_to_both():
    parser = create_parser()
    args = parser.parse_args(
        [
            "create-submission-pkg",
            "--run-output-dir",
            "./output",
            "--output",
            "./submission",
        ]
    )

    assert args.command == "create-submission-pkg"
    assert args.leaderboard == "both"
