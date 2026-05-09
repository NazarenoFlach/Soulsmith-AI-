import json
from pathlib import Path

from app.core.errors import NotFoundError
from app.models.build import Item, ItemCategory, ItemSummary


class ItemCatalog:
    def __init__(self, data_path: Path):
        self._items = self._load_items(data_path)
        self._by_id = {item.id: item for item in self._items}
        self._by_name = {self._normalize(item.name): item for item in self._items}

    @staticmethod
    def _load_items(path: Path) -> list[Item]:
        with path.open("r", encoding="utf-8") as file:
            raw_items = json.load(file)
        return [Item.model_validate(item) for item in raw_items]

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(char.lower() for char in value if char.isalnum())

    def all(self) -> list[Item]:
        return list(self._items)

    def get(self, item_id: str) -> Item:
        try:
            return self._by_id[item_id]
        except KeyError as exc:
            raise NotFoundError(f"Unknown item: {item_id}") from exc

    def find_by_name(self, name: str) -> Item | None:
        return self._by_name.get(self._normalize(name))

    def summary_for_name(self, name: str) -> ItemSummary | None:
        item = self.find_by_name(name)
        return self.to_summary(item) if item else None

    def summaries_for_names(self, names: list[str]) -> list[ItemSummary]:
        summaries: list[ItemSummary] = []
        for name in names:
            summary = self.summary_for_name(name)
            if summary:
                summaries.append(summary)
        return summaries

    def search(
        self,
        query: str,
        category: ItemCategory | None = None,
        limit: int = 8,
    ) -> list[Item]:
        terms = [term.lower() for term in query.split() if term.strip()]
        if not terms and not category:
            return self._items[:limit]

        scored: list[tuple[int, Item]] = []
        for item in self._items:
            if category and item.category != category:
                continue

            haystack = " ".join(
                [
                    item.name,
                    item.description,
                    " ".join(item.tags),
                    item.category,
                ]
            ).lower()
            score = 0
            for term in terms:
                if term in item.name.lower():
                    score += 8
                if term in item.tags:
                    score += 5
                if term in haystack:
                    score += 2
            if score or not terms:
                scored.append((score, item))

        scored.sort(key=lambda pair: (pair[0], -(pair[1].weight or 0)), reverse=True)
        return [item for _, item in scored[:limit]]

    def recommend_for_archetype(
        self,
        archetype: str,
        category: ItemCategory | None = None,
        limit: int = 6,
    ) -> list[Item]:
        query = archetype.lower()
        return self.search(query=query, category=category, limit=limit)

    def lighter_weapons_for(
        self,
        current_weapon: str,
        archetype: str,
        limit: int = 3,
    ) -> list[Item]:
        current = self.find_by_name(current_weapon)
        max_weight = current.weight if current and current.weight is not None else 8.0
        candidates = [
            item
            for item in self.search(archetype, category="weapon", limit=20)
            if item.weight is not None and item.weight < max_weight
        ]
        candidates.sort(key=lambda item: (-self._archetype_score(item, archetype), item.weight or 99))
        return candidates[:limit]

    def to_summary(self, item: Item) -> ItemSummary:
        return ItemSummary(
            id=item.id,
            name=item.name,
            category=item.category,
            weight=item.weight,
            image_url=item.image_url,
        )

    def _archetype_score(self, item: Item, archetype: str) -> int:
        return sum(1 for tag in item.tags if tag in archetype.lower())
