from typing import Literal

from pydantic import BaseModel, Field


ItemCategory = Literal["weapon", "shield", "armor", "ring", "spell", "tool"]


class Item(BaseModel):
    id: str
    name: str
    category: ItemCategory
    weight: float | None = None
    requirements: dict[str, int] = Field(default_factory=dict)
    scaling: dict[str, str] = Field(default_factory=dict)
    damage_type: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    image_url: str | None = None
    description: str


class ItemSummary(BaseModel):
    id: str
    name: str
    category: ItemCategory
    weight: float | None = None
    image_url: str | None = None


class Stats(BaseModel):
    vitality: int
    attunement: int
    endurance: int
    strength: int
    dexterity: int
    resistance: int
    intelligence: int
    faith: int


class StatsPatch(BaseModel):
    vitality: int | None = None
    attunement: int | None = None
    endurance: int | None = None
    strength: int | None = None
    dexterity: int | None = None
    resistance: int | None = None
    intelligence: int | None = None
    faith: int | None = None


class Equipment(BaseModel):
    weapon: str
    offhand: str
    armor: str
    rings: list[str] = Field(default_factory=list)
    spells: list[str] = Field(default_factory=list)


class EquipmentPatch(BaseModel):
    weapon: str | None = None
    offhand: str | None = None
    armor: str | None = None
    rings: list[str] | None = None
    spells: list[str] | None = None


class Build(BaseModel):
    archetype: str
    level: int
    stats: Stats
    equipment: Equipment
    playstyle: str
    upgrade_path: str
    notes: list[str] = Field(default_factory=list)
    relevant_items: list[ItemSummary] = Field(default_factory=list)


class BuildPatch(BaseModel):
    archetype: str | None = None
    level: int | None = None
    stats: StatsPatch | None = None
    equipment: EquipmentPatch | None = None
    playstyle: str | None = None
    upgrade_path: str | None = None
    notes: list[str] | None = None
    relevant_items: list[ItemSummary] | None = None
