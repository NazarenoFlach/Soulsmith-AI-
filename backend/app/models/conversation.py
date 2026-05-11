from typing import Literal

from pydantic import BaseModel, Field


PlayStyle = Literal["melee", "ranged", "hybrid", "balanced"]
MobilityPreference = Literal["fast", "medium", "tank"]
ExperienceLevel = Literal["new", "experienced"]


class BuildPreferences(BaseModel):
    play_style: PlayStyle | None = None
    mobility: MobilityPreference | None = None
    experience_level: ExperienceLevel | None = None
    target_archetype: str | None = None
    considered_archetypes: list[str] = Field(default_factory=list)


class ConversationState(BaseModel):
    preferences: BuildPreferences = Field(default_factory=BuildPreferences)
    pending_question: str | None = None
    pending_archetypes: list[str] = Field(default_factory=list)
    last_user_message: str | None = None
