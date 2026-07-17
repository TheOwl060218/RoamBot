from __future__ import annotations

from sqlalchemy import func, select

from roambot.persistence.tables import FavoriteTable, PlaceTable
from roambot.providers.mock import DESTINATIONS

FAVORITES_URL = "/api/v1/favorites"
PASSWORD = "correct horse battery staple"


def register(client, username: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()["csrf_token"]


def favorite_payload(
    *,
    destination_index: int = 0,
    name: str | None = None,
) -> dict[str, object]:
    destination = DESTINATIONS[destination_index].model_dump(mode="json")
    if name is not None:
        destination["name"] = name
    return {"provider": "mock", "destination": destination}


def test_guest_cannot_read_add_or_delete_favorites(auth_api_fixture) -> None:
    client, _, _ = auth_api_fixture()

    responses = [
        client.get(FAVORITES_URL),
        client.post(FAVORITES_URL, json=favorite_payload()),
        client.delete(f"{FAVORITES_URL}/missing"),
    ]

    assert [response.status_code for response in responses] == [401, 401, 401]
    assert all(
        response.json()["error"]["code"] == "authentication_required"
        for response in responses
    )


def test_first_favorite_is_201_and_repeat_is_200_with_same_id(
    auth_api_fixture,
) -> None:
    client, _, session_factory = auth_api_fixture()
    csrf = register(client, "alice_01")

    first = client.post(
        FAVORITES_URL,
        json=favorite_payload(),
        headers={"X-CSRF-Token": csrf},
    )
    repeated = client.post(
        FAVORITES_URL,
        json=favorite_payload(name="Updated place name"),
        headers={"X-CSRF-Token": csrf},
    )

    assert first.status_code == 201
    assert repeated.status_code == 200
    assert first.json()["favorite"]["id"] == repeated.json()["favorite"]["id"]
    assert repeated.json()["favorite"]["place"]["name"] == "Updated place name"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(PlaceTable)) == 1
        assert db.scalar(select(func.count()).select_from(FavoriteTable)) == 1


def test_favorite_list_is_private_and_contains_only_place_metadata(
    auth_api_fixture,
) -> None:
    alice, _, _ = auth_api_fixture()
    alice_csrf = register(alice, "alice_01")
    created = alice.post(
        FAVORITES_URL,
        json=favorite_payload(),
        headers={"X-CSRF-Token": alice_csrf},
    ).json()["favorite"]

    bob, _, _ = auth_api_fixture()
    register(bob, "bob_01")

    alice_list = alice.get(FAVORITES_URL)
    bob_list = bob.get(FAVORITES_URL)

    assert alice_list.status_code == bob_list.status_code == 200
    assert alice_list.json() == {"favorites": [created]}
    assert bob_list.json() == {"favorites": []}
    serialized = alice_list.text.lower()
    assert all(key not in serialized for key in ("weather", "score", "explanation"))


def test_repeat_favorite_selects_the_matching_place_when_user_has_multiple(
    auth_api_fixture,
) -> None:
    client, _, _ = auth_api_fixture()
    csrf = register(client, "alice_01")
    first = client.post(
        FAVORITES_URL,
        json=favorite_payload(destination_index=0),
        headers={"X-CSRF-Token": csrf},
    )
    client.post(
        FAVORITES_URL,
        json=favorite_payload(destination_index=1),
        headers={"X-CSRF-Token": csrf},
    )

    repeated = client.post(
        FAVORITES_URL,
        json=favorite_payload(destination_index=0, name="Updated place name"),
        headers={"X-CSRF-Token": csrf},
    )

    assert repeated.status_code == 200
    assert repeated.json()["favorite"]["id"] == first.json()["favorite"]["id"]


def test_cross_user_delete_is_resource_not_found(auth_api_fixture) -> None:
    client, _, _ = auth_api_fixture()
    alice_csrf = register(client, "alice_01")
    favorite_id = client.post(
        FAVORITES_URL,
        json=favorite_payload(),
        headers={"X-CSRF-Token": alice_csrf},
    ).json()["favorite"]["id"]
    client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": alice_csrf},
    )
    bob_csrf = register(client, "bob_01")

    forbidden = client.delete(
        f"{FAVORITES_URL}/{favorite_id}",
        headers={"X-CSRF-Token": bob_csrf},
    )

    assert forbidden.status_code == 404
    assert forbidden.json()["error"]["code"] == "resource_not_found"


def test_favorite_mutations_require_valid_csrf_before_writing(
    auth_api_fixture,
) -> None:
    client, _, session_factory = auth_api_fixture()
    register(client, "alice_01")

    missing = client.post(FAVORITES_URL, json=favorite_payload())
    wrong = client.delete(
        f"{FAVORITES_URL}/missing",
        headers={"X-CSRF-Token": "wrong"},
    )

    assert missing.status_code == wrong.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_invalid"
    assert wrong.json()["error"]["code"] == "csrf_invalid"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(FavoriteTable)) == 0
