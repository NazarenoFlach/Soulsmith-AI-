from app.services.item_catalog import ItemCatalog


def test_catalog_finds_lighter_strength_weapon(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items.json")

    options = catalog.lighter_weapons_for("Man-Serpent Greatsword", "Strength bruiser")

    assert options
    assert options[0].weight < 10
    assert "strength" in options[0].tags
