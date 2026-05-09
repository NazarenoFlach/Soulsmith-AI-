from threading import RLock

from app.models.build import Build, BuildPatch


class BuildStateManager:
    def __init__(self):
        self._states: dict[str, Build] = {}
        self._lock = RLock()

    def get_snapshot(self, conversation_id: str) -> Build | None:
        with self._lock:
            return self._states.get(conversation_id)

    def replace(self, conversation_id: str, build: Build) -> Build:
        with self._lock:
            self._states[conversation_id] = build
            return build

    def apply_patch(self, conversation_id: str, patch: BuildPatch) -> Build:
        with self._lock:
            current = self._states.get(conversation_id)
            if current is None:
                raise ValueError("Cannot patch a build before one exists.")

            current_data = current.model_dump()
            patch_data = patch.model_dump(exclude_none=True)
            merged = self._deep_merge(current_data, patch_data)
            build = Build.model_validate(merged)
            self._states[conversation_id] = build
            return build

    def reset(self, conversation_id: str) -> None:
        with self._lock:
            self._states.pop(conversation_id, None)

    @classmethod
    def _deep_merge(cls, current: dict, patch: dict) -> dict:
        merged = dict(current)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = cls._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
