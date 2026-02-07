# HF Dataset Process

## 1) Build Local HF Artifacts (No Upload)

Run:

```bash
uv run inv dev.release.upload-hf-dataset --version vX.Y.Z --dry-run --skip-tag-check [--folder-path <dir>]
```

What it does:
- Validates version format.
- Auto-builds missing artifacts in the target folder:
  - `full.parquet`
  - `hard.parquet`
  - `version.json`
  - `README.md`
- Validates counts/subset rules.
- Computes `dataset_hash`.
- Determines upload mode (`full` vs `metadata-only`).
- Skips actual HF upload/tagging because `--dry-run` is set.

## 2) Test Dataset Parity (Local or Remote)

Run:

```bash
# Local artifacts
uv run pytest tests/dataset/test_hf_dataset.py -v --hf-dataset-ref output/build/hf_dataset

# Official HF dataset
uv run pytest tests/dataset/test_hf_dataset.py -v --hf-dataset-ref AmineHA/WebArena-Verified
```

Test behavior:
- Loads `full` and `hard` using `load_dataset(..., split=..., cache_dir=..., download_mode="force_redownload")`.
- `test_hf_dataset_full_exact_content`:
  - compares HF/local `full` split to `assets/dataset/webarena-verified.json`.
- `test_hf_dataset_hard_subset_exact_content`:
  - validates IDs exactly match subset `task_ids`.
  - compares HF/local `hard` split to subset-export-generated hard data.
- Deep comparisons use `DeepDiff` after normalization.

## 3) Upload for Real (Release Run)

Run:

```bash
uv run inv dev.release.upload-hf-dataset --version vX.Y.Z
```

What it does:
- Enforces tag/version checks.
- Uploads artifacts to the HF dataset repo.
- Creates/verifies matching HF tag.

## Key Options

- `--skip-tag-check` is only allowed with `--dry-run`.
- `--hf-dataset-ref` can be an HF repo id or a local dataset path.
