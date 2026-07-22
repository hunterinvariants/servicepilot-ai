from dataclasses import dataclass

from app.ai import AIProvider
from app.schemas import ServiceRequest


@dataclass(frozen=True)
class EvaluationCase:
    message: str
    expected_category: str
    expected_urgency: str


DATASET = [
    EvaluationCase("Water is leaking from a pipe below the sink", "plumbing", "medium"),
    EvaluationCase("Urgent sparking electrical socket and smoke", "electrical", "emergency"),
    EvaluationCase("The boiler stopped heating the house", "hvac", "medium"),
    EvaluationCase("The dishwasher will not turn on", "appliance", "medium"),
]


def run_evaluation(provider: AIProvider) -> dict:
    category_hits = urgency_hits = 0
    latency = 0.0
    for case in DATASET:
        request = ServiceRequest(name="Evaluation", email="eval@example.com",
                                 address="Test address 1", message=case.message)
        result, metrics = provider.classify(request)
        category_hits += result.category == case.expected_category
        urgency_hits += result.urgency == case.expected_urgency
        latency += metrics["latency_ms"]
    size = len(DATASET)
    return {"cases": size, "category_accuracy": category_hits / size,
            "urgency_accuracy": urgency_hits / size, "average_latency_ms": latency / size}
