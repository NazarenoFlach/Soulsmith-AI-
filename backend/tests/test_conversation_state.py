from app.models.conversation import BuildPreferences
from app.services.conversation_state import ConversationStateManager


def test_conversation_state_keeps_pending_preferences():
    manager = ConversationStateManager()

    state = manager.update(
        "demo",
        preferences=BuildPreferences(play_style="ranged"),
        pending_question="Close-range, ranged, or hybrid?",
        pending_archetypes=["dexterity", "sorcery"],
        last_user_message="not sure yet",
    )

    assert state.preferences.play_style == "ranged"
    assert state.pending_archetypes == ["dexterity", "sorcery"]
    assert state.preferences.considered_archetypes == ["dexterity", "sorcery"]


def test_clear_pending_preserves_preferences():
    manager = ConversationStateManager()
    manager.update(
        "demo",
        preferences=BuildPreferences(play_style="hybrid"),
        pending_question="Close-range, ranged, or hybrid?",
        pending_archetypes=["dexterity", "sorcery"],
    )

    state = manager.clear_pending("demo")

    assert state.preferences.play_style == "hybrid"
    assert state.pending_question is None
    assert state.pending_archetypes == []
