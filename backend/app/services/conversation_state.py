from threading import RLock

from app.models.conversation import BuildPreferences, ConversationState


class ConversationStateManager:
    def __init__(self):
        self._states: dict[str, ConversationState] = {}
        self._lock = RLock()

    def get_snapshot(self, conversation_id: str) -> ConversationState:
        with self._lock:
            state = self._states.get(conversation_id)
            if state is None:
                state = ConversationState()
                self._states[conversation_id] = state
            return state.model_copy(deep=True)

    def update(
        self,
        conversation_id: str,
        preferences: BuildPreferences | None = None,
        pending_question: str | None = None,
        pending_archetypes: list[str] | None = None,
        last_user_message: str | None = None,
        last_intent: str | None = None,
    ) -> ConversationState:
        with self._lock:
            current = self._states.get(conversation_id) or ConversationState()
            if preferences is not None:
                current.preferences = self._merge_preferences(current.preferences, preferences)
            if pending_question is not None:
                current.pending_question = pending_question
            if pending_archetypes is not None:
                current.pending_archetypes = pending_archetypes
                current.preferences.considered_archetypes = pending_archetypes
            if last_user_message is not None:
                current.last_user_message = last_user_message
            if last_intent is not None:
                current.last_intent = last_intent
            self._states[conversation_id] = current
            return current.model_copy(deep=True)

    def clear_pending(self, conversation_id: str) -> ConversationState:
        with self._lock:
            current = self._states.get(conversation_id) or ConversationState()
            current.pending_question = None
            current.pending_archetypes = []
            self._states[conversation_id] = current
            return current.model_copy(deep=True)

    def reset(self, conversation_id: str) -> None:
        with self._lock:
            self._states.pop(conversation_id, None)

    def _merge_preferences(
        self,
        current: BuildPreferences,
        patch: BuildPreferences,
    ) -> BuildPreferences:
        data = current.model_dump()
        patch_data = patch.model_dump(exclude_none=True)
        for key, value in patch_data.items():
            if value != []:
                data[key] = value
        return BuildPreferences.model_validate(data)
