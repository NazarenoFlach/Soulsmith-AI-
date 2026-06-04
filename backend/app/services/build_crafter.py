from app.models.agent import AgentPlan
from app.models.build import Build, BuildPatch, EquipmentPatch, StatsPatch
from app.services.build_templates import BuildTemplateCatalog
from app.services.item_catalog import ItemCatalog


class BuildCraftService:
    def __init__(self, catalog: ItemCatalog, templates: BuildTemplateCatalog):
        self.catalog = catalog
        self.templates = templates

    def generate(self, plan: AgentPlan) -> Build:
        archetype = self.templates.resolve_key(plan.archetype, plan.constraints)
        build = self.templates.get(archetype)
        build.relevant_items = self._relevant_items(build)
        return build

    def refine(self, current: Build, plan: AgentPlan, user_message: str) -> BuildPatch:
        text = " ".join([user_message, " ".join(plan.constraints), " ".join(plan.refinement_targets)]).lower()

        if "weapon swap" in text or self._wants_alternative_weapon(text):
            options = self.catalog.alternative_weapons_for(current.equipment.weapon, current.archetype)
            if options:
                weapon = options[0]
                notes = self._replace_note(
                    current.notes,
                    f"Swapped to {weapon.name} because the previous weapon was not the right fit.",
                )
                return BuildPatch(
                    equipment=EquipmentPatch(weapon=weapon.name),
                    notes=notes,
                    relevant_items=self._summaries_for_equipment(
                        weapon.name,
                        current.equipment.offhand,
                        current.equipment.armor,
                        current.equipment.rings,
                        current.equipment.spells,
                    ),
                )

        if "lighter" in text and ("weapon" in text or "weap" in text or current.equipment.weapon):
            options = self.catalog.lighter_weapons_for(current.equipment.weapon, current.archetype)
            if options:
                weapon = options[0]
                notes = self._replace_note(
                    current.notes,
                    f"Swapped to {weapon.name} to reduce weapon weight while preserving the build's stat plan.",
                )
                return BuildPatch(
                    equipment=EquipmentPatch(weapon=weapon.name),
                    notes=notes,
                    relevant_items=self._summaries_for_equipment(
                        weapon.name,
                        current.equipment.offhand,
                        current.equipment.armor,
                        current.equipment.rings,
                        current.equipment.spells,
                    ),
                )

        if any(term in text for term in ["fast roll", "faster roll", "more mobile", "lighter armor"]):
            notes = self._replace_note(current.notes, "Shifted armor and rings toward fast-roll mobility.")
            return BuildPatch(
                equipment=EquipmentPatch(
                    armor="Shadow Set",
                    rings=["Dark Wood Grain Ring", "Ring of Favor and Protection"],
                ),
                notes=notes,
                relevant_items=self._summaries_for_equipment(
                    current.equipment.weapon,
                    current.equipment.offhand,
                    "Shadow Set",
                    ["Dark Wood Grain Ring", "Ring of Favor and Protection"],
                    current.equipment.spells,
                ),
            )

        if any(term in text for term in ["tankier", "more poise", "poise", "heavy armor"]):
            notes = self._replace_note(current.notes, "Added heavier poise tools; watch equip load breakpoints.")
            return BuildPatch(
                equipment=EquipmentPatch(
                    armor="Havel's Set",
                    rings=["Havel's Ring", "Ring of Favor and Protection"],
                ),
                notes=notes,
                relevant_items=self._summaries_for_equipment(
                    current.equipment.weapon,
                    current.equipment.offhand,
                    "Havel's Set",
                    ["Havel's Ring", "Ring of Favor and Protection"],
                    current.equipment.spells,
                ),
            )

        if any(term in text for term in ["shield", "block", "stability"]):
            if any(term in text for term in ["heavy shield", "greatshield", "great shield"]):
                shield = "Eagle Shield"
            elif "stability" in text or "strength" in current.archetype.lower():
                shield = "Balder Shield"
            else:
                shield = "Heater Shield"
            notes = self._replace_note(current.notes, f"Changed offhand to {shield} for the requested defensive profile.")
            return BuildPatch(
                equipment=EquipmentPatch(offhand=shield),
                notes=notes,
                relevant_items=self._summaries_for_equipment(
                    current.equipment.weapon,
                    shield,
                    current.equipment.armor,
                    current.equipment.rings,
                    current.equipment.spells,
                ),
            )

        if any(term in text for term in ["pyro", "pyromancy", "fire"]):
            spells = list(dict.fromkeys([*current.equipment.spells, "Power Within", "Great Combustion"]))
            notes = self._replace_note(current.notes, "Added pyromancy without disturbing the weapon stat spread.")
            return BuildPatch(
                stats=StatsPatch(attunement=max(current.stats.attunement, 12)),
                equipment=EquipmentPatch(spells=spells),
                notes=notes,
                relevant_items=self._summaries_for_equipment(
                    current.equipment.weapon,
                    "Pyromancy Flame",
                    current.equipment.armor,
                    current.equipment.rings,
                    spells,
                ),
            )

        notes = self._replace_note(current.notes, "Kept the core build intact; no equipment change was required.")
        return BuildPatch(notes=notes)

    def _relevant_items(self, build: Build):
        return self._summaries_for_equipment(
            build.equipment.weapon,
            build.equipment.offhand,
            build.equipment.armor,
            build.equipment.rings,
            build.equipment.spells,
        )

    def _summaries_for_equipment(
        self,
        weapon: str,
        offhand: str,
        armor: str,
        rings: list[str],
        spells: list[str],
    ):
        names = [weapon, offhand, armor, *rings, *spells]
        return self.catalog.summaries_for_names(names)

    def _replace_note(self, notes: list[str], note: str) -> list[str]:
        retained = [
            existing
            for existing in notes
            if existing != note and not self._same_note_family(existing, note)
        ]
        return [*retained[:3], note]

    def _wants_alternative_weapon(self, text: str) -> bool:
        weapon_terms = ["weapon", "sword", "katana", "blade", "uchigatana"]
        swap_terms = [
            "another",
            "different",
            "swap",
            "change",
            "replace",
            "instead",
            "dont like",
            "don't like",
            "not like",
        ]
        return any(term in text for term in weapon_terms) and any(term in text for term in swap_terms)

    def _same_note_family(self, existing: str, note: str) -> bool:
        prefixes = [
            "Added heavier poise",
            "Added pyromancy",
            "Changed offhand",
            "Kept the core build",
            "Shifted armor",
            "Swapped",
        ]
        return any(existing.startswith(prefix) and note.startswith(prefix) for prefix in prefixes)
