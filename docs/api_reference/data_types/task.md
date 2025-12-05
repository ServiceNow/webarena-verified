# WebArenaVerifiedTask

## Attributes

::: src.webarena_verified.types.task.WebArenaVerifiedTask
    options:
      show_docstring_description: false
      members: ["sites", "task_id", "start_urls", "intent", "intent_template", "instantiation_dict", "start_url_context", "eval", "revision"]

## Example Task

```json
{
  "task_id": 7,
  "intent_template_id": 79,
  "sites": ["map"],
  "start_urls": ["__MAP__"],
  "intent": "Get the name, state, and zip code of all international airports that are within a driving distance of 50 km to Carnegie Mellon University. Use \"name\" for the name, \"state\" for the state, and \"postcode\" for the postcode.",
  "intent_template": "Get the name, state, and zip code of all {{airport_type}} that are within a driving distance of {{radius}} to {{start}}. {{retrieved_data_format_spec}}.",
  "instantiation_dict": {
    "airport_type": "international airports",
    "start": "Carnegie Mellon University",
    "radius": "50 km",
    "retrieved_data_format_spec": "Use \"name\" for the name, \"state\" for the state, and \"postcode\" for the postcode"
  },
  "eval": [
    {
      "evaluator": "AgentResponseEvaluator",
      "ordered": false,
      "results_schema": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {"type": "string"},
            "state": {"type": "string"},
            "postcode": {"type": "string"}
          }
        }
      },
      "expected": {
        "task_type": "retrieve",
        "status": "SUCCESS",
        "retrieved_data": [
          {
            "name": "Pittsburgh International Airport",
            "state": "Pennsylvania",
            "postcode": "15231"
          }
        ]
      }
    }
  ],
  "revision": 2
}
```
