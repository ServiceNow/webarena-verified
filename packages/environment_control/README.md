# environment_control

Environment control package for WebArena Docker containers.

## Installation

```bash
pip install .
```

## Usage

### CLI

```bash
# List available environment types
env-ctrl list

# Check status
ENV_TYPE=dummy env-ctrl status

# Start server
ENV_TYPE=dummy env-ctrl serve --port 8877
```

### Python

```python
from environment_control import get_ops_class

ops = get_ops_class("dummy")
result = ops.get_health()
print(result.success)
```
