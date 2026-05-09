import json
from pathlib import Path

from pydantic import BaseModel

from app.models.build import Build


class BuildTemplate(BaseModel):
    key: str
    aliases: list[str]
    build: Build


class BuildTemplateCatalog:
    def __init__(self, path: Path):
        with path.open("r", encoding="utf-8") as file:
            templates = [BuildTemplate.model_validate(item) for item in json.load(file)]

        self._templates = {template.key: template for template in templates}
        self._aliases = {
            alias.lower(): template.key
            for template in templates
            for alias in [template.key, *template.aliases]
        }

    def get(self, key: str) -> Build:
        template = self._templates.get(key, self._templates["quality"])
        return template.build.model_copy(deep=True)

    def resolve_key(self, requested: str | None, constraints: list[str]) -> str:
        text = " ".join([requested or "", *constraints]).lower()
        for alias, key in self._aliases.items():
            if alias in text:
                return key
        return "quality"

    def mentioned_keys(self, text: str) -> set[str]:
        lowered = text.lower()
        return {key for alias, key in self._aliases.items() if alias in lowered}
