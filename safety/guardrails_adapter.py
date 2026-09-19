"""Optional Guardrails AI structural validation on the same grounded result schema."""

import json
from typing import Literal
from pydantic import BaseModel, Field


class Answer(BaseModel):
    status: Literal["answered", "review", "blocked"]
    route: Literal["training_summary", "latest_workout", "signal_inventory", "knowledge", "review"]
    answer: str = Field(max_length=10000)
    citations: list[str]


def validate(result):
    from guardrails import Guard

    payload = {k: result[k] for k in Answer.model_fields}
    guard = Guard.for_pydantic(output_class=Answer)
    guard.configure(allow_metrics_collection=False)
    outcome = guard.parse(json.dumps(payload), num_reasks=0)
    if not outcome.validation_passed:
        raise ValueError("Guardrails AI rejected answer shape")
    # A schema cannot establish grounding. Compare citations to actual tool/retrieval evidence.
    allowed = {e["id"] for e in result["evidence"]}
    if result["status"] == "answered" and (not result["citations"] or set(result["citations"]) - allowed):
        raise ValueError("Evidence citation validation failed")
    return outcome.validated_output
