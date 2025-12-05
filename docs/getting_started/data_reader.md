# Data Reader

The `WebArenaVerified` facade provides easy access to benchmark tasks:

```python
from webarena_verified.api import WebArenaVerified

# Initialize with config
wa = WebArenaVerified()

# Get all tasks
tasks = wa.get_tasks()
print(len(tasks))  # 812 tasks in the full benchmark

# Get a specific task
task = wa.get_task(42)
print(task.intent_template_id)
print(task.expected_agent_response.task_type)
```
