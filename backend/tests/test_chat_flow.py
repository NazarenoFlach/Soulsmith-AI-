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


def test_known_item_location_uses_dataset_notes():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "where can i find the crimson set?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert "Sealer's corpse" in body["message"]
    assert body["items"][0]["id"] == "crimson_set"


def test_misspelled_item_location_uses_fuzzy_match():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "where can i find the crimsom set?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert "Crimson Set" in body["message"]
    assert body["items"][0]["id"] == "crimson_set"


def test_unknown_item_location_keeps_friendly_fallback():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "where can i find the moon cabbage?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert body["items"] == []
    assert "farming souls" in body["message"]
    assert "pin down" in body["message"]


def test_catalog_item_without_location_does_not_look_unknown():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "where can i get the abyss greatsword?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert body["items"][0]["id"] == "abyss_greatsword"
    assert "local catalog" in body["message"]
    assert "will not invent" in body["message"]


def test_catalog_item_shorthand_does_not_look_unknown():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "where can i get the abbys sword?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert body["items"][0]["id"] == "abyss_greatsword"
    assert "local catalog" in body["message"]
    assert "will not invent" in body["message"]


def test_generated_alias_item_question_uses_catalog():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "where is havel ring?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert body["items"][0]["id"] == "havels_ring"
    assert "Havel" in body["message"]


def test_typo_heavy_item_question_still_uses_catalog():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "wher can i finde the haval rign?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert body["items"][0]["id"] == "havels_ring"
    assert "Havel" in body["message"]


def test_semantic_item_question_uses_catalog():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "what item lets me hit ghosts?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert body["items"][0]["id"] == "transient_curse"
    assert "Transient Curse" in body["message"]


def test_semantic_spell_question_uses_catalog():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "what spell buffs my weapon with lightning?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert body["items"][0]["id"] == "sunlight_blade"
    assert "Sunlight Blade" in body["message"]


def test_semantic_key_question_uses_catalog():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "which key opens early locks?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert body["items"][0]["id"] == "master_key"
    assert "Master Key" in body["message"]


def test_tank_damage_recommendation_generates_strength_build():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "message": "what do you recommend? i like to play with tank characters but with a lot of damage"
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is not None
    assert body["build"]["archetype"] == "Strength bruiser"
    assert body["items"][0]["id"] != "skull_lantern"


def test_tank_build_switches_to_strength_even_with_existing_build():
    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={"message": "i want a dark wizard build"},
        ).json()

        response = client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "i want a tank build",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is not None
    assert body["build"]["archetype"] == "Strength bruiser"


def test_damage_only_build_request_asks_for_damage_style():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "i want a fully damage build"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is None
    assert "melee damage" in body["message"]
    assert "ranged spell damage" in body["message"]


def test_damage_clarification_followup_generates_matching_build():
    cases = [
        ("melee damage", "Strength bruiser"),
        ("fast bleed", "Dexterity duelist"),
        ("ranged spell damage", "Sorcery skirmisher"),
    ]

    for followup, expected_archetype in cases:
        with TestClient(app) as client:
            first = client.post(
                "/api/chat",
                json={"message": "i want a fully damage build"},
            ).json()

            response = client.post(
                "/api/chat",
                json={
                    "conversation_id": first["conversation_id"],
                    "message": followup,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["build"] is not None
        assert body["build"]["archetype"] == expected_archetype


def test_refinement_response_does_not_expose_raw_patch():
    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={"message": "i want a strength build"},
        ).json()

        response = client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "Recommend a lighter weapon",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert "Applied this patch" not in body["message"]
    assert "Swapped the weapon" in body["message"]
    assert body["build"]["equipment"]["weapon"] == "Battle Axe"


def test_heavy_shield_refinement_uses_heavy_option_and_keeps_notes_unique():
    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={"message": "i want a tank build, with a lot of HP"},
        ).json()

        shield_response = client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "i would like to use a shield too, what do you recommend?",
            },
        ).json()
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "and what about a heavy shield?",
            },
        )

    assert shield_response["build"]["equipment"]["offhand"] == "Balder Shield"
    assert response.status_code == 200
    body = response.json()
    assert body["build"]["equipment"]["offhand"] == "Eagle Shield"
    assert "Eagle Shield" in body["message"]
    assert len(body["build"]["notes"]) == len(set(body["build"]["notes"]))


def test_ninja_build_is_treated_as_dexterity_exploration():
    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={"message": "i want a strength build"},
        ).json()

        response = client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "what about a ninja build?",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"]["archetype"] == "Strength bruiser"
    assert "Dexterity duelist" in body["message"]
    assert "not changed" in body["message"]


def test_disliked_weapon_refines_current_build_instead_of_regenerating():
    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={"message": "a dextery build"},
        ).json()

        response = client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "i dont like the uchigatana, i want another weapon",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"]["archetype"] == "Dexterity duelist"
    assert body["build"]["equipment"]["weapon"] != "Uchigatana"
    assert "Swapped the weapon" in body["message"]


def test_item_location_followup_reuses_previous_item_question_context():
    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={"message": "a dextery build"},
        ).json()

        client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "where can i get the shadow set?",
            },
        )
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "and the huchigatana?",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["id"] == "uchigatana"
    assert "Uchigatana" in body["message"]


def test_generic_item_followup_can_reference_current_build_equipment():
    with TestClient(app) as client:
        first = client.post(
            "/api/chat",
            json={"message": "a dextery build"},
        ).json()

        client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "where can i get the shadow set?",
            },
        )
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": first["conversation_id"],
                "message": "and the weapon?",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["id"] == "uchigatana"
    assert "Uchigatana" in body["message"]


def test_misspelled_archetype_still_generates_expected_build():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "i want a strenght build"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["build"] is not None
    assert body["build"]["archetype"] == "Strength bruiser"


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
