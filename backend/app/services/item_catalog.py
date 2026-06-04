import json
import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from app.core.errors import NotFoundError
from app.models.build import Item, ItemCategory, ItemSummary
from app.models.catalog import AliasConflict, CatalogCategoryCoverage, CatalogQualityReport
from app.services.item_aliases import AliasCandidate, alias_candidates_for
from app.services.item_semantics import (
    SemanticProfile,
    build_semantic_profiles,
    find_semantic_item,
)


QUERY_NOISE_WORDS = {
    "a",
    "an",
    "and",
    "around",
    "can",
    "cn",
    "do",
    "does",
    "drop",
    "drops",
    "farm",
    "find",
    "finde",
    "for",
    "from",
    "get",
    "how",
    "i",
    "in",
    "is",
    "it",
    "location",
    "my",
    "obtain",
    "of",
    "please",
    "the",
    "to",
    "where",
    "what",
    "which",
    "with",
    "wer",
    "wher",
    "whr",
    "obtian",
}


@dataclass(frozen=True)
class FuzzyAlias:
    alias: str
    tokens: list[str]
    initials: frozenset[str]
    item: Item
    threshold: float


class ItemCatalog:
    def __init__(self, data_path: Path):
        self._items = self._load_items(data_path)
        self._by_id = {item.id: item for item in self._items}
        self._by_name = {self._normalize(item.name): item for item in self._items}
        self._alias_groups = self._build_alias_groups()
        self._aliases, self._ambiguous_aliases = self._build_alias_index()
        self._search_aliases = self._build_search_aliases()
        self._fuzzy_aliases = self._build_fuzzy_aliases()
        self._semantic_profiles = self._build_semantic_profiles()

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

    def quality_report(self) -> CatalogQualityReport:
        categories: dict[str, CatalogCategoryCoverage] = {}
        for item in self._items:
            coverage = categories.setdefault(item.category, CatalogCategoryCoverage())
            coverage.total += 1
            coverage.with_source_url += int(item.source_url is not None)
            coverage.with_location += int(item.location is not None)
            coverage.with_acquisition += int(item.acquisition is not None)
            coverage.with_manual_aliases += int(bool(item.aliases))

        conflicts = [
            AliasConflict(
                alias=self._best_alias_label(candidates),
                normalized_alias=alias,
                item_ids=sorted({candidate.item.id for candidate in candidates}),
                kinds=sorted({candidate.kind for candidate in candidates}),
            )
            for alias, candidates in sorted(self._ambiguous_aliases.items())
        ]
        generated_aliases = sum(
            1
            for candidates in self._alias_groups.values()
            for candidate in candidates
            if candidate.kind == "generated"
        )

        return CatalogQualityReport(
            total_items=len(self._items),
            indexed_aliases=len(self._aliases),
            generated_aliases=generated_aliases,
            ignored_ambiguous_aliases=len(self._ambiguous_aliases),
            categories=categories,
            alias_conflicts=conflicts,
        )

    def get(self, item_id: str) -> Item:
        try:
            return self._by_id[item_id]
        except KeyError as exc:
            raise NotFoundError(f"Unknown item: {item_id}") from exc

    def find_by_name(self, name: str) -> Item | None:
        normalized = self._normalize(name)
        return self._by_name.get(normalized) or self._aliases.get(normalized)

    def find_in_text(self, text: str, allow_fuzzy: bool = True) -> Item | None:
        return self._find_in_text_cached(text, allow_fuzzy)

    @lru_cache(maxsize=1024)
    def _find_in_text_cached(self, text: str, allow_fuzzy: bool) -> Item | None:
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
                    " ".join(self._search_aliases.get(item.id, [])),
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

    def alternative_weapons_for(
        self,
        current_weapon: str,
        archetype: str,
        limit: int = 3,
    ) -> list[Item]:
        current = self.find_by_name(current_weapon)
        candidates = [
            item
            for item in self.search(archetype, category="weapon", limit=25)
            if current is None or item.id != current.id
        ]
        candidates.sort(
            key=lambda item: (
                -self._archetype_score(item, archetype),
                item.weight is None,
                item.weight or 99,
            )
        )
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

    def _build_alias_groups(self) -> dict[str, list[AliasCandidate]]:
        groups: dict[str, list[AliasCandidate]] = defaultdict(list)
        for item in self._items:
            for candidate in alias_candidates_for(item):
                normalized = self._normalize(candidate.alias)
                if normalized:
                    groups[normalized].append(candidate)
        return dict(groups)

    def _build_alias_index(
        self,
    ) -> tuple[dict[str, Item], dict[str, list[AliasCandidate]]]:
        aliases: dict[str, Item] = {}
        ambiguous: dict[str, list[AliasCandidate]] = {}

        for alias, candidates in self._alias_groups.items():
            item_ids = {candidate.item.id for candidate in candidates}
            if len(item_ids) == 1:
                aliases[alias] = candidates[0].item
                continue

            canonical = [
                candidate
                for candidate in candidates
                if candidate.kind == "canonical"
                and self._normalize(candidate.alias) == alias
            ]
            canonical_ids = {candidate.item.id for candidate in canonical}
            if len(canonical_ids) == 1:
                aliases[alias] = canonical[0].item
                continue

            ambiguous[alias] = candidates

        return aliases, ambiguous

    def _build_search_aliases(self) -> dict[str, list[str]]:
        aliases_by_item: dict[str, list[str]] = defaultdict(list)
        for alias, candidates in self._alias_groups.items():
            if alias in self._ambiguous_aliases:
                continue
            for candidate in candidates:
                aliases_by_item[candidate.item.id].append(candidate.alias)
        return dict(aliases_by_item)

    def _build_fuzzy_aliases(self) -> list[FuzzyAlias]:
        records: list[FuzzyAlias] = []
        seen: set[tuple[str, str]] = set()
        for alias, candidates in self._alias_groups.items():
            if alias in self._ambiguous_aliases or len(alias) < 5:
                continue

            item = self._aliases.get(alias)
            if item is None:
                continue

            for candidate in candidates:
                key = (alias, item.id)
                if key in seen:
                    continue
                seen.add(key)
                tokens = self._tokens(candidate.alias)
                if tokens:
                    records.append(
                        FuzzyAlias(
                            alias=alias,
                            tokens=tokens,
                            initials=frozenset(token[0] for token in tokens if token),
                            item=item,
                            threshold=self._fuzzy_threshold(alias, tokens),
                        )
                    )
        return records

    def _build_semantic_profiles(self) -> list[SemanticProfile]:
        return build_semantic_profiles(self._items, self._search_aliases)

    def _best_alias_label(self, candidates: list[AliasCandidate]) -> str:
        sorted_candidates = sorted(
            candidates,
            key=lambda candidate: (candidate.kind != "generated", len(candidate.alias)),
        )
        return sorted_candidates[0].alias

    def _find_fuzzy_alias(self, text: str) -> Item | None:
        tokens = self._signal_tokens(text)
        if not tokens:
            return None

        candidates: list[tuple[float, int, Item]] = []
        token_initials = {token[0] for token in tokens if token}
        for alias in self._fuzzy_aliases:
            if not self._has_enough_initial_overlap(alias, token_initials):
                continue
            for window in self._token_windows(tokens, len(alias.tokens)):
                compact_window = self._normalize(" ".join(window))
                char_score = SequenceMatcher(None, alias.alias, compact_window).ratio()
                token_score = self._token_similarity(alias.tokens, window)
                score = max(char_score, token_score)
                if score >= alias.threshold:
                    candidates.append((score, len(alias.alias), alias.item))

        if not candidates:
            return find_semantic_item(text, self._semantic_profiles)

        candidates.sort(key=lambda candidate: (candidate[0], candidate[1]), reverse=True)
        best_score, _, best_item = candidates[0]
        next_different = next(
            (
                candidate
                for candidate in candidates[1:]
                if candidate[2].id != best_item.id
            ),
            None,
        )
        if next_different and best_score - next_different[0] < 0.03:
            return None
        return best_item

    def _has_enough_initial_overlap(self, alias: FuzzyAlias, token_initials: set[str]) -> bool:
        overlap = len(alias.initials & token_initials)
        if len(alias.tokens) == 1:
            return overlap >= 1
        required = 2 if len(alias.initials) >= 2 and len(token_initials) >= 2 else 1
        return overlap >= required

    def _signal_tokens(self, text: str) -> list[str]:
        tokens = self._tokens(text)
        signal_tokens = [token for token in tokens if not self._is_noise_token(token)]
        return signal_tokens or tokens

    def _is_noise_token(self, token: str) -> bool:
        if token in QUERY_NOISE_WORDS:
            return True
        if len(token) < 4:
            return False
        return any(
            SequenceMatcher(None, token, noise_word).ratio() >= 0.84
            for noise_word in QUERY_NOISE_WORDS
        )

    def _token_similarity(self, alias_tokens: list[str], query_tokens: list[str]) -> float:
        if not alias_tokens or not query_tokens:
            return 0.0

        scores = []
        for alias_token in alias_tokens:
            scores.append(
                max(
                    SequenceMatcher(None, alias_token, query_token).ratio()
                    for query_token in query_tokens
                )
            )
        return sum(scores) / len(scores)

    def _fuzzy_threshold(self, alias: str, alias_tokens: list[str]) -> float:
        if len(alias) <= 5:
            return 0.9
        if len(alias_tokens) == 1:
            return 0.88 if len(alias) <= 8 else 0.84
        return 0.77

    def _tokens(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _token_windows(self, tokens: list[str], size: int) -> list[list[str]]:
        sizes = {size}
        sizes.add(size + 1)

        windows: list[list[str]] = []
        for window_size in sorted(sizes):
            if window_size <= 0 or window_size > len(tokens):
                continue
            for index in range(len(tokens) - window_size + 1):
                windows.append(tokens[index : index + window_size])
        return windows
