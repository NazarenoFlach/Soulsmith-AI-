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
