from enum import Enum

from pydantic import BaseModel, Field


class AgentIntent(str, Enum):
    clarify = "clarify"
    explore = "explore"
    generate = "generate"
    refine = "refine"
    explain = "explain"
    item_info = "item_info"
    recommend = "recommend"
    reset = "reset"
    unknown = "unknown"


class AgentPlan(BaseModel):
    intent: AgentIntent
    archetype: str | None = None
    refinement_targets: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    item_query: str | None = None
