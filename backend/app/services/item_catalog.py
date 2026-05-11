import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from app.core.errors import NotFoundError
from app.models.build import Item, ItemCategory, ItemSummary


class ItemCatalog:
    def __init__(self, data_path: Path):
        self._items = self._load_items(data_path)
        self._by_id = {item.id: item for item in self._items}
        self._by_name = {self._normalize(item.name): item for item in self._items}
        self._aliases = {
            self._normalize(alias): item
            for item in self._items
            for alias in [item.name, *item.aliases]
        }

    @classmethod
    def _load_items(cls, path: Path) -> list[Item]:
        if path.is_dir():
            raw_items: list[dict] = []
            for item_file in sorted(path.glob("*.json")):
                raw_items.extend(cls._load_raw_items(item_file))
        else:
            raw_items = cls._load_raw_items(path)

        items = [Item.model_validate(item) for item in raw_items]
        seen: set[str] = set()
        duplicates: set[str] = set()
        for item in items:
            if item.id in seen:
                duplicates.add(item.id)
            seen.add(item.id)
        if duplicates:
            raise ValueError(f"Duplicate item ids in catalog: {', '.join(sorted(duplicates))}")
        return items

    @staticmethod
    def _load_raw_items(path: Path) -> list[dict]:
        with path.open("r", encoding="utf-8") as file:
            raw_items = json.load(file)
        if not isinstance(raw_items, list):
            raise ValueError(f"Item catalog file must contain a list: {path}")
        return raw_items

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
        normalized = self._normalize(name)
        return self._by_name.get(normalized) or self._aliases.get(normalized)

    def find_in_text(self, text: str, allow_fuzzy: bool = True) -> Item | None:
        normalized = self._normalize(text)
        matches: list[tuple[int, Item]] = []
        for key, item in self._aliases.items():
            if key and key in normalized:
                matches.append((len(key), item))
        if not matches:
            return self._find_fuzzy_alias(text) if allow_fuzzy else None
        matches.sort(key=lambda match: match[0], reverse=True)
        return matches[0][1]

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
                    item.location or "",
                    item.acquisition or "",
                    " ".join(item.tags),
                    " ".join(item.aliases),
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
            location=item.location,
            acquisition=item.acquisition,
            source_url=item.source_url,
        )

    def _archetype_score(self, item: Item, archetype: str) -> int:
        return sum(1 for tag in item.tags if tag in archetype.lower())

    def _find_fuzzy_alias(self, text: str) -> Item | None:
        tokens = self._tokens(text)
        if not tokens:
            return None

        candidates: list[tuple[float, int, Item]] = []
        for alias, item in self._aliases.items():
            if len(alias) < 5:
                continue

            alias_tokens = self._tokens(alias)
            if not alias_tokens:
                continue

            for window in self._token_windows(tokens, len(alias_tokens)):
                score = SequenceMatcher(None, alias, self._normalize(" ".join(window))).ratio()
                threshold = 0.88 if len(alias) <= 8 else 0.82
                if score >= threshold:
                    candidates.append((score, len(alias), item))

        if not candidates:
            return None

        candidates.sort(key=lambda candidate: (candidate[0], candidate[1]), reverse=True)
        if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.03:
            return None
        return candidates[0][2]

    def _tokens(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _token_windows(self, tokens: list[str], size: int) -> list[list[str]]:
        sizes = {size}
        if size > 1:
            sizes.add(size - 1)
        sizes.add(size + 1)

        windows: list[list[str]] = []
        for window_size in sorted(sizes):
            if window_size <= 0 or window_size > len(tokens):
                continue
            for index in range(len(tokens) - window_size + 1):
                windows.append(tokens[index : index + window_size])
        return windows
