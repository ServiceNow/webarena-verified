# HF Dataset Release Spec: WebArena-Verified

## Scope
Define a reproducible release pipeline for publishing `WebArena-Verified` to Hugging Face as a dataset with:
- two splits: `full` and `hard`
- parquet artifacts only
- Hugging Face Dataset Viewer/Data Studio configuration
- strict version alignment with GitHub release tags

This document is a specification only. It does not require code changes yet.

## Inputs
- Full dataset source: `assets/dataset/webarena-verified.json`
- Hard subset definition: `assets/dataset/subsets/webarena-verified-hard.json`
- Existing CLI command for hard export:
  - `webarena-verified subset-export --path assets/dataset/subsets/webarena-verified-hard.json --output output/build/hf_dataset/hard.json`

## Outputs
All generated artifacts are written under:
- `output/build/hf_dataset`

Required files:
- `output/build/hf_dataset/full.parquet` (release artifact)
- `output/build/hf_dataset/hard.parquet` (release artifact)
- `output/build/hf_dataset/version.json` (release metadata)
- `README.md` (dataset card, uploaded with artifacts)

## Split Definitions
- `full` split:
  - all rows from `assets/dataset/webarena-verified.json`
- `hard` split:
  - rows whose `task_id` is included in `assets/dataset/subsets/webarena-verified-hard.json`
  - exported via `subset-export` command

## Pipeline
1. Generate `full.json` from `assets/dataset/webarena-verified.json`.
2. Generate `hard.json` via `subset-export`.
3. Load both JSON files with Hugging Face `datasets`.
4. Run strict split validations.
5. Export both splits to parquet, preserving input row order.
6. Write `version.json` metadata.
7. Upload artifacts to HF dataset repo.
8. Verify split visibility and loading in HF Viewer/Data Studio.

## Data Conversion (HF Datasets)
Use `datasets` library to load JSON and export parquet:
- load:
  - `load_dataset("json", data_files="output/build/hf_dataset/full.json", split="train")`
  - `load_dataset("json", data_files="output/build/hf_dataset/hard.json", split="train")`
- export:
  - `full.to_parquet("output/build/hf_dataset/full.parquet")`
  - `hard.to_parquet("output/build/hf_dataset/hard.parquet")`

## Validation
Validation is mandatory and fail-fast.

Required checks:
- `len(full) == 812`
- `len(hard) == 258`
- `set(hard.task_id) ⊆ set(full.task_id)`

Failure policy:
- stop release immediately if any validation fails
- do not upload partial/invalid artifacts

## Dataset Card and Viewer Configuration
Dataset card `README.md` must include manual split mapping:

```yaml
---
configs:
- config_name: default
  data_files:
  - split: full
    path: output/build/hf_dataset/full.parquet
  - split: hard
    path: output/build/hf_dataset/hard.parquet
---
```

Card content must include:
- dataset description
- schema notes
- split stats (`full=812`, `hard=258`)
- license and language/task metadata as applicable
- license target: `Apache-2.0` (pending confirmation that dataset redistribution terms match code license)
- version reference matching release tag

Compatibility fallback:
- if custom split names are not accepted by Viewer, use two configs (`full`, `hard`) each mapped to `train`

## Versioning and Release Contract
Version source of truth:
- GitHub release tag in format `vX.Y.Z`

Rules:
- dataset version must match GitHub release version exactly
- if auto-detecting version, require exact git tag on current commit
- reject invalid version format: must match `^v\d+\.\d+\.\d+([-.].+)?$`

Artifact stamping (`version.json`):
- `version`
- `git_commit` (full SHA)
- `generated_at` (UTC ISO-8601)

HF upload/tag policy:
- upload commit message: `dataset: vX.Y.Z`
- create/verify matching HF dataset tag `vX.Y.Z`
- hard fail if HF tag creation/verification does not succeed

## Upload Interface (Planned)
Planned Invoke task (draft):
- task name: `dev.release.upload-hf-dataset`
- implementation uses:
  - `from huggingface_hub import login, upload_folder`
  - `upload_folder(folder_path=".", repo_id="AmineHA/WebArena-Verified", repo_type="dataset")`

Planned parameters:
- `repo_id` (default: `AmineHA/WebArena-Verified`)
- `folder_path` (target folder; expected `output/build/hf_dataset`)
- `token` (optional; allow pre-existing `huggingface-cli login` session when omitted)
- `create_pr` (optional)

Upload behavior defaults:
- direct commit upload by default (`create_pr=False`)
- upload only `full.parquet`, `hard.parquet`, `version.json`, and `README.md`

Dependency requirement:
- add `huggingface_hub` to dev dependencies

## Acceptance Criteria
Release is successful only if all are true:
1. `full.parquet` and `hard.parquet` are generated under `output/build/hf_dataset`.
2. Validations pass (`812`, `258`, subset relation).
3. `version.json` exists and matches GitHub release tag/version.
4. HF upload completes to `AmineHA/WebArena-Verified`.
5. HF Viewer/Data Studio shows both splits and rows load correctly.
6. `load_dataset("AmineHA/WebArena-Verified", split="full")` and `split="hard"` work.
7. Build artifacts remain untracked in this repository (`output/build/hf_dataset` is build-only).

## Open Question
- Keep current split naming (`full`/`hard`) or switch to config-per-split fallback (`train`) if Viewer rejects custom split names.

## References
- https://huggingface.co/docs/hub/datasets-viewer-configure
- https://huggingface.co/docs/hub/datasets-manual-configuration
- https://huggingface.co/docs/hub/datasets-data-files-configuration
- https://huggingface.co/docs/hub/datasets-viewer
- https://huggingface.co/docs/hub/datasets-adding
