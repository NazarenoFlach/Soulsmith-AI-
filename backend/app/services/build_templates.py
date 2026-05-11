import json
import re
from difflib import SequenceMatcher
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
        return self.first_mentioned_key(text) or "quality"

    def mentioned_keys(self, text: str) -> set[str]:
        lowered = text.lower()
        exact = {key for alias, key in self._aliases.items() if alias in lowered}
        return exact | self._fuzzy_keys(text)

    def first_mentioned_key(self, text: str) -> str | None:
        lowered = text.lower()
        matches = [
            (position, -len(alias), key)
            for alias, key in self._aliases.items()
            if (position := lowered.find(alias)) >= 0
        ]
        if matches:
            return sorted(matches)[0][2]
        fuzzy_matches = self._fuzzy_matches(text)
        return fuzzy_matches[0][2] if fuzzy_matches else None

    def _fuzzy_keys(self, text: str) -> set[str]:
        return {key for _, _, key in self._fuzzy_matches(text)}

    def _fuzzy_matches(self, text: str) -> list[tuple[float, int, str]]:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if not tokens:
            return []

        matches: list[tuple[float, int, str]] = []
        for alias, key in self._aliases.items():
            normalized_alias = self._normalize(alias)
            if len(normalized_alias) < 5:
                continue

            alias_size = len(re.findall(r"[a-z0-9]+", alias))
            for window in self._token_windows(tokens, alias_size):
                score = SequenceMatcher(
                    None,
                    normalized_alias,
                    self._normalize(" ".join(window)),
                ).ratio()
                threshold = 0.9 if len(normalized_alias) <= 8 else 0.84
                if score >= threshold:
                    matches.append((score, len(normalized_alias), key))

        matches.sort(key=lambda match: (match[0], match[1]), reverse=True)
        return matches

    def _normalize(self, value: str) -> str:
        return "".join(char.lower() for char in value if char.isalnum())

    def _token_windows(self, tokens: list[str], size: int) -> list[list[str]]:
        sizes = {size}
        if size > 1:
            sizes.add(size - 1)
        sizes.add(size + 1)

        windows: list[list[str]] = []
        for window_size in sorted(sizes):
            if window_size <= 0 or window_size > len(tokens):
                continue
            for index in range(len(tokens) - window_size + 1):
                windows.append(tokens[index : index + window_size])
        return windows
