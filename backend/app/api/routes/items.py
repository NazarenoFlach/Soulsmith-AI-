from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse, Response

from app.dependencies import get_image_service, get_item_catalog
from app.models.build import ItemCategory, ItemSummary
from app.models.chat import ItemSearchResponse
from app.services.image_service import ImageService
from app.services.item_catalog import ItemCatalog

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=ItemSearchResponse)
async def search_items(
    q: str = Query(default="", max_length=200),
    category: ItemCategory | None = None,
    catalog: ItemCatalog = Depends(get_item_catalog),
) -> ItemSearchResponse:
    items = catalog.search(q, category=category, limit=12)
    return ItemSearchResponse(items=[catalog.to_summary(item) for item in items])


@router.get("/{item_id}", response_model=ItemSummary)
async def get_item(
    item_id: str,
    catalog: ItemCatalog = Depends(get_item_catalog),
) -> ItemSummary:
    return catalog.to_summary(catalog.get(item_id))


@router.get("/{item_id}/image")
async def get_item_image(
    item_id: str,
    catalog: ItemCatalog = Depends(get_item_catalog),
    image_service: ImageService = Depends(get_image_service),
):
    item = catalog.get(item_id)
    if item.image_url:
        return RedirectResponse(item.image_url)
    return Response(content=image_service.fallback_svg(item), media_type="image/svg+xml")
