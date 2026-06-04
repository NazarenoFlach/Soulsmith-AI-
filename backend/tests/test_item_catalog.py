from app.services.item_catalog import ItemCatalog


def test_catalog_finds_lighter_strength_weapon(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    assert len(catalog.all()) >= 450

    options = catalog.lighter_weapons_for("Man-Serpent Greatsword", "Strength bruiser")

    assert options
    assert options[0].weight < 10
    assert "strength" in options[0].tags


def test_catalog_matches_aliases_and_keeps_source_notes(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    item = catalog.find_in_text("where is the fap ring?", allow_fuzzy=False)

    assert item is not None
    assert item.id == "ring_of_favor_and_protection"
    assert item.acquisition is not None
    assert item.source_url is not None


def test_catalog_tolerates_misspelled_item_names(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    item = catalog.find_in_text("where can i find the crimsom set?")

    assert item is not None
    assert item.id == "crimson_set"


def test_catalog_tolerates_typo_heavy_item_queries(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    examples = {
        "wher can i finde the haval rign?": "havels_ring",
        "where can i get the grss crest shiled?": "grass_crest_shield",
        "how do i obtian the moonlite sword?": "moonlight_greatsword",
        "where cn i get claymor?": "claymore",
        "wer do i farm blak knight halbred?": "black_knight_halberd",
    }

    for query, expected_id in examples.items():
        item = catalog.find_in_text(query)

        assert item is not None
        assert item.id == expected_id


def test_catalog_handles_common_item_shorthand(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    item = catalog.find_in_text("where can i get the abbys sword?")

    assert item is not None
    assert item.id == "abyss_greatsword"


def test_catalog_generates_safe_aliases(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    examples = {
        "where can i get bk halberd?": "black_knight_halberd",
        "where is havel ring?": "havels_ring",
        "where can i find havel armor?": "havel_set",
        "where can i get grass shield?": "grass_crest_shield",
        "where is moonlight sword?": "moonlight_greatsword",
    }

    for query, expected_id in examples.items():
        item = catalog.find_in_text(query, allow_fuzzy=False)

        assert item is not None
        assert item.id == expected_id


def test_catalog_matches_semantic_item_descriptions(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    examples = {
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

    for query, expected_id in examples.items():
        item = catalog.find_in_text(query)

        assert item is not None
        assert item.id == expected_id


def test_catalog_leaves_short_ambiguous_aliases_unmatched(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    item = catalog.find_in_text("where can i find havel?", allow_fuzzy=False)

    assert item is None


def test_catalog_ignores_weak_fuzzy_matches(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    item = catalog.find_in_text("where can i find the moon cabbage?")

    assert item is None


def test_catalog_ignores_weak_semantic_matches(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    item = catalog.find_in_text("what item lets me become a sandwich?")

    assert item is None


def test_catalog_loads_split_item_files(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    assert catalog.find_by_name("Abyss Greatsword") is not None
    assert catalog.find_by_name("Bastard Sword") is not None
    assert catalog.find_by_name("Master Key") is not None
    assert catalog.find_by_name("Fireball") is not None


def test_catalog_quality_report_has_no_alias_conflicts(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    report = catalog.quality_report()

    assert report.total_items >= 450
    assert report.indexed_aliases > report.total_items
    assert report.generated_aliases > 0
    assert report.ignored_ambiguous_aliases == 0
    assert report.alias_conflicts == []
