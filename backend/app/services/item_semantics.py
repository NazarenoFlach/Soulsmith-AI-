import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.models.build import Item


SEMANTIC_NOISE_WORDS = {
    "a",
    "an",
    "and",
    "any",
    "can",
    "do",
    "does",
    "for",
    "from",
    "get",
    "give",
    "how",
    "i",
    "is",
    "it",
    "item",
    "me",
    "my",
    "need",
    "one",
    "please",
    "something",
    "that",
    "the",
    "thing",
    "to",
    "use",
    "what",
    "where",
    "which",
    "with",
}

SEMANTIC_SYNONYMS: dict[str, tuple[str, ...]] = {
    "big": ("great", "large"),
    "boost": ("buff", "increase", "raises"),
    "buff": ("boost", "enhance", "enhances", "coats", "weapon"),
    "cure": ("cures", "removes", "cancels", "reduces"),
    "door": ("opens", "unlock", "unlocks"),
    "early": ("starting", "gift", "early"),
    "ghost": ("ghosts", "transient", "curse"),
    "ghosts": ("ghost", "transient", "curse"),
    "green": ("grass", "crest"),
    "heal": ("heals", "healing", "restore", "restores", "hp"),
    "hit": ("damage", "damaging", "attack"),
    "light": ("bright", "illumination"),
    "lightning": ("lightning", "sunlight"),
    "load": ("equip", "equipment", "burden"),
    "lock": ("locks", "unlock", "unlocks", "opens"),
    "locks": ("lock", "unlock", "unlocks", "opens"),
    "magic": ("magic", "sorcery", "enchanted"),
    "material": ("upgrade", "reinforce", "titanite"),
    "open": ("opens", "unlock", "unlocks"),
    "poise": ("stability", "tank", "heavy"),
    "poison": ("poisoned", "toxic", "moss"),
    "regen": ("regeneration", "recovery", "stamina"),
    "regeneration": ("regen", "recovery", "stamina"),
    "resist": ("resistance", "defense"),
    "stamina": ("stamina", "recovery", "regeneration", "regen"),
    "toxic": ("poison", "moss", "blooming"),
    "unlock": ("unlocks", "opens", "key"),
    "upgrade": ("reinforce", "ascension", "material", "ember", "titanite"),
}

CATEGORY_TERMS = {
    "ammunition": {"ammo", "arrow", "bolt"},
    "armor": {"armor", "set", "helm", "chest", "gauntlets", "leggings"},
    "consumable": {"consumable", "item", "use"},
    "ember": {"ember", "ascension", "andre"},
    "key_item": {"key", "unlock", "opens", "door"},
    "multiplayer": {"covenant", "online", "multiplayer"},
    "ring": {"ring"},
    "shield": {"shield", "block"},
    "soul": {"soul", "boss"},
    "spell": {"spell", "sorcery", "miracle", "pyromancy", "cast"},
    "tool": {"tool", "catalyst", "talisman", "flame"},
    "upgrade_material": {"upgrade", "material", "reinforce", "titanite"},
    "weapon": {"weapon", "sword", "axe", "halberd", "bow", "dagger", "katana"},
}


@dataclass(frozen=True)
class SemanticProfile:
    item: Item
    name_terms: frozenset[str]
    alias_terms: frozenset[str]
    tag_terms: frozenset[str]
    category_terms: frozenset[str]
    body_terms: frozenset[str]

    @property
    def all_terms(self) -> frozenset[str]:
        return frozenset(
            self.name_terms
            | self.alias_terms
            | self.tag_terms
            | self.category_terms
            | self.body_terms
        )


def build_semantic_profiles(
    items: list[Item],
    aliases_by_item: dict[str, list[str]],
) -> list[SemanticProfile]:
    profiles = []
    for item in items:
        body = " ".join(
            [
                item.description,
                item.location or "",
                item.acquisition or "",
            ]
        )
        profiles.append(
            SemanticProfile(
                item=item,
                name_terms=_terms(item.name),
                alias_terms=_terms(" ".join(aliases_by_item.get(item.id, []))),
                tag_terms=_terms(" ".join(item.tags)),
                category_terms=frozenset(CATEGORY_TERMS.get(item.category, {item.category})),
                body_terms=_terms(body),
            )
        )
    return profiles


def find_semantic_item(text: str, profiles: list[SemanticProfile]) -> Item | None:
    query_tokens = _signal_terms(text)
    if len(query_tokens) < 2:
        return None

    scored: list[tuple[float, int, Item]] = []
    for profile in profiles:
        score, hits = _score_profile(query_tokens, profile)
        if hits >= 2 and score >= 9:
            scored.append((score, hits, profile.item))

    if not scored:
        return None

    scored.sort(key=lambda candidate: (candidate[0], candidate[1]), reverse=True)
    best_score, best_hits, best_item = scored[0]
    next_different = next(
        (candidate for candidate in scored[1:] if candidate[2].id != best_item.id),
        None,
    )
    if next_different and _is_too_close(best_score, best_hits, next_different):
        return None
    return best_item


def _score_profile(query_tokens: list[str], profile: SemanticProfile) -> tuple[float, int]:
    score = 0.0
    hits = 0
    for token in query_tokens:
        variants = _expand_query_term(token)
        token_score = _score_variants(variants, profile)
        if token_score:
            hits += 1
            score += token_score
    return score, hits


def _score_variants(variants: set[str], profile: SemanticProfile) -> float:
    if variants & profile.name_terms:
        return 7.0
    if variants & profile.alias_terms:
        return 6.5
    if variants & profile.tag_terms:
        return 5.0
    if variants & profile.category_terms:
        return 4.0
    if variants & profile.body_terms:
        return 2.5
    fuzzy_body_score = _fuzzy_body_score(variants, profile.body_terms)
    if fuzzy_body_score:
        return fuzzy_body_score
    return 0.0


def _fuzzy_body_score(variants: set[str], body_terms: frozenset[str]) -> float:
    if not variants or not body_terms:
        return 0.0
    for variant in variants:
        if len(variant) < 5:
            continue
        for term in body_terms:
            if abs(len(variant) - len(term)) > 2:
                continue
            if SequenceMatcher(None, variant, term).ratio() >= 0.86:
                return 1.5
    return 0.0


def _is_too_close(
    best_score: float,
    best_hits: int,
    next_candidate: tuple[float, int, Item],
) -> bool:
    next_score, next_hits, _ = next_candidate
    return best_score - next_score < 3 and best_hits <= next_hits


def _signal_terms(text: str) -> list[str]:
    terms = []
    for token in _words(text):
        if token in SEMANTIC_NOISE_WORDS:
            continue
        terms.extend(_term_variants(token))
    return list(dict.fromkeys(terms))


def _expand_query_term(term: str) -> set[str]:
    expanded = set(_term_variants(term))
    for variant in list(expanded):
        for synonym in SEMANTIC_SYNONYMS.get(variant, ()):
            expanded.update(_term_variants(synonym))
    return expanded


def _terms(text: str) -> frozenset[str]:
    terms = []
    for token in _words(text):
        terms.extend(_term_variants(token))
    return frozenset(terms)


def _term_variants(token: str) -> set[str]:
    variants = {token}
    if len(token) > 4 and token.endswith("ing"):
        variants.add(token[:-3])
    if len(token) > 4 and token.endswith("ed"):
        variants.add(token[:-2])
    if len(token) > 3 and token.endswith("s"):
        variants.add(token[:-1])
    return variants


def _words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())
