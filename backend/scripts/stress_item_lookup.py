import sys
from pathlib import Path
from time import perf_counter


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from app.services.item_catalog import ItemCatalog  # noqa: E402


CASES = {
    "wher can i finde the haval rign?": "havels_ring",
    "where can i get the grss crest shiled?": "grass_crest_shield",
    "how do i obtian the moonlite sword?": "moonlight_greatsword",
    "where cn i get claymor?": "claymore",
    "wer do i farm blak knight halbred?": "black_knight_halberd",
    "where can i get the abbys sword?": "abyss_greatsword",
    "where is the fap rign?": "ring_of_favor_and_protection",
    "where can i find the crimsom set?": "crimson_set",
    "where is the green stamina thing?": "grass_crest_shield",
    "what ring improves stamina recovery?": "cloranthy_ring",
    "what item lets me hit ghosts?": "transient_curse",
    "what spell buffs my weapon with lightning?": "sunlight_blade",
    "which key opens early locks?": "master_key",
    "what material upgrades boss soul weapons?": "demon_titanite",
    "what moss cures toxic?": "blooming_purple_moss_clump",
    "what item cures poison?": "purple_moss_clump",
    "what pyromancy throws a giant fireball?": "great_fireball",
}


def main() -> int:
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    catalog = ItemCatalog(BACKEND_DIR / "app" / "data" / "items")
    misses = []
    timings = []

    started = perf_counter()
    for index in range(iterations):
        for query, expected_id in CASES.items():
            lookup_started = perf_counter()
            item = catalog.find_in_text(query)
            timings.append(perf_counter() - lookup_started)
            if item is None or item.id != expected_id:
                misses.append((index, query, expected_id, item.id if item else None))

    elapsed = perf_counter() - started
    timings.sort()
    p95 = timings[int(len(timings) * 0.95)]
    total = iterations * len(CASES)
    print(f"lookups={total}")
    print(f"elapsed_seconds={elapsed:.3f}")
    print(f"lookups_per_second={total / elapsed:.1f}")
    print(f"p95_lookup_ms={p95 * 1000:.3f}")
    print(f"misses={len(misses)}")

    for miss in misses[:10]:
        print(f"miss iteration={miss[0]} query={miss[1]!r} expected={miss[2]} actual={miss[3]}")

    return 1 if misses else 0


if __name__ == "__main__":
    raise SystemExit(main())
