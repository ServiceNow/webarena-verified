# Configuration

## WebArenaVerifiedConfig

::: src.webarena_verified.types.config.WebArenaVerifiedConfig
    options:
      show_root_heading: true
      members: ["test_data_file", "environments", "agent_response_file_name", "trace_file_name", "eval_result_file_name", "storage_state_file_name"]

## EnvironmentConfig

::: src.webarena_verified.types.config.EnvironmentConfig
    options:
      show_root_heading: true
      members: ["urls", "active_url_idx", "credentials"]

## Supported Site Placeholders

| Placeholder | Description |
|------------|-------------|
| `__SHOPPING_ADMIN__` | Shopping admin dashboard |
| `__SHOPPING__` | Shopping customer site |
| `__REDDIT__` | Reddit-like forum |
| `__GITLAB__` | GitLab instance |
| `__WIKIPEDIA__` | Wikipedia instance |
| `__MAP__` | Map application |
| `__HOMEPAGE__` | Homepage/portal |
