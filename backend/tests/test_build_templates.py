from app.services.build_templates import BuildTemplateCatalog


def test_templates_resolve_common_archetype_aliases(settings_data_dir):
    templates = BuildTemplateCatalog(settings_data_dir / "build_templates.json")

    assert templates.resolve_key("wizard", []) == "sorcery"
    assert templates.resolve_key(None, ["fast melee dex"]) == "dexterity"
    assert templates.resolve_key(None, ["strenght build"]) == "strength"
    assert templates.mentioned_keys("dextery or wizard") == {"dexterity", "sorcery"}
    assert templates.get("strength").equipment.weapon == "Man-Serpent Greatsword"
