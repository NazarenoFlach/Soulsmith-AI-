import re
from dataclasses import dataclass
from typing import Literal

from app.models.build import Item


AliasKind = Literal["canonical", "manual", "generated"]

STOP_WORDS = {"a", "an", "and", "of", "the"}

CURATED_ALIASES: dict[str, tuple[str, ...]] = {
    "abyss_greatsword": ("abyss sword", "abbys sword"),
    "black_knight_greataxe": ("bk greataxe", "bk great axe"),
    "black_knight_greatsword": ("bk greatsword", "bk great sword"),
    "black_knight_halberd": ("bk halberd",),
    "black_knight_shield": ("bk shield",),
    "black_knight_sword": ("bk sword",),
    "darkmoon_seance_ring": ("seance ring",),
    "blooming_purple_moss_clump": ("toxic moss", "toxic cure moss", "cures toxic"),
    "cloranthy_ring": ("stamina recovery ring", "stamina regen ring"),
    "demon_titanite": ("boss soul upgrade material", "boss weapon titanite"),
    "divine_blessing": ("full heal item", "status cure heal"),
    "grass_crest_shield": (
        "grass shield",
        "green stamina shield",
        "stamina recovery shield",
        "stamina regen shield",
    ),
    "great_fireball": ("giant fireball", "big fireball pyromancy"),
    "havel_set": ("havel armor", "heavy poise armor"),
    "havels_ring": ("havel ring", "equip load ring", "heavy armor ring"),
    "large_ember": ("plus ten ember", "normal upgrade ember"),
    "master_key": ("early lock key", "starting gift key", "thief gift key"),
    "moonlight_greatsword": ("moonlight sword", "mlgs", "magic greatsword"),
    "purple_moss_clump": ("poison moss", "poison cure moss", "cures poison"),
    "ring_of_favor_and_protection": ("rofap", "favor protection ring", "hp stamina equip load ring"),
    "silver_knight_shield": ("sk shield",),
    "silver_knight_spear": ("sk spear",),
    "silver_knight_straight_sword": ("sk sword",),
    "sunlight_blade": ("lightning weapon buff", "faith lightning buff"),
    "transient_curse": ("ghost hit item", "damage ghosts item", "ghost curse item"),
    "twinkling_titanite": ("rare armor upgrade material", "special weapon upgrade material"),
    "very_large_ember": ("plus fifteen ember", "final normal ember"),
}


@dataclass(frozen=True)
class AliasCandidate:
    alias: str
    item: Item
    kind: AliasKind


def alias_candidates_for(item: Item) -> list[AliasCandidate]:
    candidates = [AliasCandidate(item.name, item, "canonical")]
    candidates.extend(AliasCandidate(alias, item, "manual") for alias in item.aliases)
    candidates.extend(
        AliasCandidate(alias, item, "generated")
        for alias in sorted(_generated_aliases(item))
    )
    return candidates


def _generated_aliases(item: Item) -> set[str]:
    aliases = set(CURATED_ALIASES.get(item.id, ()))
    aliases.update(_possessive_variants(item.name))
    aliases.update(_category_variants(item))
    aliases.update(_faction_shorthand(item.name))
    return {alias for alias in aliases if _is_useful(alias)}


def _possessive_variants(name: str) -> set[str]:
    variants = set()
    if "'s" in name:
        variants.add(name.replace("'s", ""))
    if "s'" in name:
        variants.add(name.replace("s'", "s"))
    return variants


def _category_variants(item: Item) -> set[str]:
    name = item.name
    variants = set()

    if item.category == "armor" and name.endswith(" Set"):
        stem = name.removesuffix(" Set")
        variants.add(f"{stem} armor")

    if item.category == "ring":
        if name.endswith(" Ring"):
            stem = name.removesuffix(" Ring")
            if not _is_single_possessive(stem):
                variants.add(stem)
        if name.startswith("Ring of "):
            core = name.removeprefix("Ring of ")
            core_without_stops = " ".join(word for word in _words(core) if word not in STOP_WORDS)
            variants.add(f"{core} ring")
            if core_without_stops:
                variants.add(f"{core_without_stops} ring")

    return variants


def _faction_shorthand(name: str) -> set[str]:
    words = _words(name)
    if len(words) < 3:
        return set()

    prefixes = {
        ("black", "knight"): "bk",
        ("silver", "knight"): "sk",
    }
    prefix = prefixes.get(tuple(words[:2]))
    if not prefix:
        return set()

    rest = " ".join(words[2:])
    return {f"{prefix} {rest}"} if rest else set()


def _words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _is_single_possessive(value: str) -> bool:
    return value.endswith("'s") and len(_words(value)) == 2


def _is_useful(alias: str) -> bool:
    compact = "".join(char for char in alias.lower() if char.isalnum())
    return len(compact) >= 3
