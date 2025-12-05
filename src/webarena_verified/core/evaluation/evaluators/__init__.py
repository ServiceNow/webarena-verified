from .agent_response_evaluator import AgentResponseEvaluator
from .base import BaseEvaluator
from .network_event_evaluator import NetworkEventEvaluator

EVALUATOR_REGISTRY: dict[str, type[BaseEvaluator]] = {
    AgentResponseEvaluator.__name__: AgentResponseEvaluator,
    NetworkEventEvaluator.__name__: NetworkEventEvaluator,
}

__all__ = [
    "AgentResponseEvaluator",
    "BaseEvaluator",
    "EVALUATOR_REGISTRY",
    "NetworkEventEvaluator",
]
