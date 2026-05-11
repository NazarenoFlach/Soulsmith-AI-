from fastapi.testclient import TestClient

from app.main import app


def test_ambiguous_first_message_asks_for_clarification():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "message": "i dont know if i want a dexterity or wizard build, what do you recommend?"
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert "Dexterity" in body["message"]
    assert "Sorcery" in body["message"]


def test_pending_clarification_generates_after_user_picks_style():
    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={
                "message": "i dont know if i want a dexterity or wizard build, what do you recommend?"
            },
        ).json()

        second = client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "hybrid sounds better, i want melee with some magic",
            },
        )

    assert second.status_code == 200
    body = second.json()
    assert body["conversation_id"] == first["conversation_id"]
    assert body["build"] is not None
    assert body["build"]["archetype"] == "Pyromancy bruiser"


def test_exploring_new_archetype_does_not_replace_current_build_until_confirmed():
    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={"message": "i want a strength build"},
        ).json()

        opinion = client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "what do you think about playing priest?",
            },
        ).json()

        switched = client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "yeah, switch to that",
            },
        ).json()

    assert first["build"]["archetype"] == "Strength bruiser"
    assert opinion["build"]["archetype"] == "Strength bruiser"
    assert "Faith weapon buffer" in opinion["message"]
    assert "not changed" in opinion["message"]
    assert switched["build"]["archetype"] == "Faith weapon buffer"


def test_single_archetype_difficulty_question_is_exploration():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "message": "what do you think about play priest? is it easy or hard?"
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert "Faith weapon buffer" in body["message"]
    assert "not the easiest" in body["message"]


def test_single_archetype_viability_question_is_exploration():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "what about the pyromancy build? is it good or not?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert "Pyromancy bruiser" in body["message"]
    assert "very good" in body["message"]


def test_unavailable_item_location_does_not_generate_default_build():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "where can i find the crimson set?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert "farming souls" in body["message"]


def test_greeting_does_not_generate_default_build():
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert "Dark Souls 1 builds" in body["message"]


def test_generic_build_request_asks_for_preferences():
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "i want a build"})

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert "Do you prefer" in body["message"]
