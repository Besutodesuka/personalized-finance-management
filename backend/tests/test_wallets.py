"""Tests for the wallets API (/api/wallets)."""


def test_seeded_wallets_present(client):
    res = client.get("/api/wallets")
    assert res.status_code == 200
    wallets = res.json()
    assert len(wallets) == 4
    for w in wallets:
        assert "id" in w and w["id"]
        assert "name" in w
        assert "budget" in w


def test_create_wallet_returns_id_and_echoes_fields(client):
    payload = {"name": "Travel", "budget": 1500, "color": "#ff0000", "icon": "✈️"}
    res = client.post("/api/wallets", json=payload)
    assert res.status_code == 200
    created = res.json()
    assert created["id"]
    assert created["name"] == "Travel"
    assert created["budget"] == 1500
    assert created["color"] == "#ff0000"
    assert created["icon"] == "✈️"

    listed = client.get("/api/wallets").json()
    assert any(w["id"] == created["id"] for w in listed)


def test_create_wallet_uses_default_color_and_icon(client):
    res = client.post("/api/wallets", json={"name": "Savings", "budget": 200})
    assert res.status_code == 200
    created = res.json()
    assert created["color"] == "#6366f1"
    assert created["icon"] == "💰"


def test_update_wallet_persists(client, wallet_id):
    payload = {
        "name": "Renamed",
        "budget": 999,
        "color": "#00ff00",
        "icon": "🏦",
    }
    res = client.put(f"/api/wallets/{wallet_id}", json=payload)
    assert res.status_code == 200
    updated = res.json()
    assert updated["name"] == "Renamed"
    assert updated["budget"] == 999

    listed = client.get("/api/wallets").json()
    match = next(w for w in listed if w["id"] == wallet_id)
    assert match["name"] == "Renamed"
    assert match["budget"] == 999


def test_update_nonexistent_wallet_returns_404(client):
    payload = {"name": "Ghost", "budget": 1, "color": "#000000", "icon": "👻"}
    res = client.put("/api/wallets/does-not-exist", json=payload)
    assert res.status_code == 404


def test_delete_wallet_removes_from_list(client, wallet_id):
    res = client.delete(f"/api/wallets/{wallet_id}")
    assert res.status_code == 200
    assert res.json() == {"ok": True}

    listed = client.get("/api/wallets").json()
    assert all(w["id"] != wallet_id for w in listed)
