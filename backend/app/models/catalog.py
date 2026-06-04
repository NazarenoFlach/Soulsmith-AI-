from pydantic import BaseModel, Field


class AliasConflict(BaseModel):
    alias: str
    normalized_alias: str
    item_ids: list[str]
    kinds: list[str]


class CatalogCategoryCoverage(BaseModel):
    total: int = 0
    with_source_url: int = 0
    with_location: int = 0
    with_acquisition: int = 0
    with_manual_aliases: int = 0


class CatalogQualityReport(BaseModel):
    total_items: int
    indexed_aliases: int
    generated_aliases: int
    ignored_ambiguous_aliases: int
    categories: dict[str, CatalogCategoryCoverage] = Field(default_factory=dict)
    alias_conflicts: list[AliasConflict] = Field(default_factory=list)
