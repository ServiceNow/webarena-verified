# Configuration

WebArena-Verified uses a JSON configuration file to:

- Specify the dataset location
- Configure environment URLs for each site
- Provide authentication credentials
- Select which environment to use when running tasks

## Example

```json
{
  "test_data_file": "assets/dataset/webarena-verified.json",
  "environments": {
    "__SHOPPING_ADMIN__": {
      "urls": ["http://localhost:7780/admin"],
      "active_url_idx": 0,
      "credentials": {
        "username": "admin",
        "password": "admin1234"
      }
    },
    "__SHOPPING__": {
      "urls": ["http://localhost:7780"],
      "credentials": {
        "username": "user@example.com",
        "password": "password123"
      }
    },
    "__REDDIT__": {
      "urls": ["http://localhost:9999"],
      "credentials": {
        "username": "testuser",
        "password": "testpass"
      }
    }
  }
}
```

## See Also

- [API Reference: Configuration](../api_reference/data_types/config.md) - Detailed field descriptions
- [Getting Started Guide](../index.md)
- [Evaluation Guide](../evaluation/index.md)
