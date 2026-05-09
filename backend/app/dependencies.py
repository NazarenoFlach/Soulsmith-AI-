from functools import lru_cache

from app.agent.soulsmith_agent import SoulsmithAgent
from app.core.config import Settings, get_settings
from app.services.build_crafter import BuildCraftService
from app.services.build_state import BuildStateManager
from app.services.build_templates import BuildTemplateCatalog
from app.services.image_service import ImageService
from app.services.item_catalog import ItemCatalog
from app.services.rag import RagService


@lru_cache
def get_item_catalog() -> ItemCatalog:
    settings = get_settings()
    return ItemCatalog(settings.data_dir / "items.json")


@lru_cache
def get_state_manager() -> BuildStateManager:
    return BuildStateManager()


@lru_cache
def get_build_templates() -> BuildTemplateCatalog:
    settings = get_settings()
    return BuildTemplateCatalog(settings.data_dir / "build_templates.json")


@lru_cache
def get_rag_service() -> RagService:
    settings = get_settings()
    return RagService(
        catalog=get_item_catalog(),
        guides_path=settings.data_dir / "build_guides.json",
        persist_dir=settings.chroma_dir,
        embedding_model=settings.openai_embedding_model,
        openai_api_key=settings.openai_api_key,
    )


@lru_cache
def get_build_crafter() -> BuildCraftService:
    return BuildCraftService(get_item_catalog(), get_build_templates())


@lru_cache
def get_image_service() -> ImageService:
    return ImageService()


@lru_cache
def get_agent() -> SoulsmithAgent:
    settings: Settings = get_settings()
    return SoulsmithAgent(
        catalog=get_item_catalog(),
        rag=get_rag_service(),
        state_manager=get_state_manager(),
        crafter=get_build_crafter(),
        openai_api_key=settings.openai_api_key,
        model=settings.openai_model,
        timeout_seconds=settings.request_timeout_seconds,
    )
