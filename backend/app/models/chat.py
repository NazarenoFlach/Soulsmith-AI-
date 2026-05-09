from pydantic import BaseModel, Field

from app.models.build import Build, ItemSummary


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    build: Build | None = None
    items: list[ItemSummary] = Field(default_factory=list)


class ItemSearchResponse(BaseModel):
    items: list[ItemSummary]
