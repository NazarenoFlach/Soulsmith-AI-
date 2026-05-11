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


def test_catalog_handles_common_item_shorthand(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    item = catalog.find_in_text("where can i get the abbys sword?")

    assert item is not None
    assert item.id == "abyss_greatsword"


def test_catalog_ignores_weak_fuzzy_matches(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    item = catalog.find_in_text("where can i find the moon cabbage?")

    assert item is None


def test_catalog_loads_split_item_files(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")

    assert catalog.find_by_name("Abyss Greatsword") is not None
    assert catalog.find_by_name("Bastard Sword") is not None
    assert catalog.find_by_name("Master Key") is not None
    assert catalog.find_by_name("Fireball") is not None
