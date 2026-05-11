from app.models.build import BuildPatch, EquipmentPatch
from app.services.build_crafter import BuildCraftService
from app.services.build_state import BuildStateManager
from app.services.item_catalog import ItemCatalog
from app.models.agent import AgentIntent, AgentPlan
from app.services.build_templates import BuildTemplateCatalog


def test_apply_patch_preserves_unmodified_build_fields(settings_data_dir):
    catalog = ItemCatalog(settings_data_dir / "items")
    templates = BuildTemplateCatalog(settings_data_dir / "build_templates.json")
    crafter = BuildCraftService(catalog, templates)
    build = crafter.generate(AgentPlan(intent=AgentIntent.generate, archetype="strength"))

    manager = BuildStateManager()
    manager.replace("demo", build)
    updated = manager.apply_patch(
        "demo",
        BuildPatch(equipment=EquipmentPatch(weapon="Reinforced Club")),
    )

    assert updated.equipment.weapon == "Reinforced Club"
    assert updated.stats == build.stats
    assert updated.equipment.rings == build.equipment.rings
