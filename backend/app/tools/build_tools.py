from app.models.build import ItemSummary
from app.services.build_state import BuildStateManager
from app.services.item_catalog import ItemCatalog
from app.services.rag import RagService


class BuildTools:
    def __init__(
        self,
        catalog: ItemCatalog,
        rag: RagService,
        state_manager: BuildStateManager,
    ):
        self.catalog = catalog
        self.rag = rag
        self.state_manager = state_manager

    def retrieve_context(self, query: str, limit: int = 4) -> list[str]:
        return self.rag.retrieve(query=query, limit=limit)

    def search_items(self, query: str, limit: int = 5) -> list[ItemSummary]:
        return [self.catalog.to_summary(item) for item in self.catalog.search(query=query, limit=limit)]

    def reset_build(self, conversation_id: str) -> None:
        self.state_manager.reset(conversation_id)
