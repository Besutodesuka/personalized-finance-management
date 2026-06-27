"""Tests for the subscriptions router (/api/subscriptions)."""


def test_create_monthly_subscription_defaults(client, wallet_id):
    resp = client.post(
        "/api/subscriptions",
        json={
            "name": "Spotify",
            "amount": 9.99,
            "wallet_id": wallet_id,
            "billing_day": 15,
        },
    )
    assert resp.status_code == 200
    sub = resp.json()
    assert "id" in sub
    assert sub["name"] == "Spotify"
    assert sub["amount"] == 9.99
    assert sub["billing_day"] == 15
    assert sub["billing_cycle"] == "monthly"
    assert sub["renewal_date"] is None
    assert sub["active"] is True


def test_create_yearly_subscription_with_renewal_date(client, wallet_id):
    resp = client.post(
        "/api/subscriptions",
        json={
            "name": "Amazon Prime",
            "amount": 139.0,
            "wallet_id": wallet_id,
            "billing_cycle": "yearly",
            "renewal_date": "2026-12-01",
        },
    )
    assert resp.status_code == 200
    sub = resp.json()
    assert sub["billing_cycle"] == "yearly"
    assert sub["renewal_date"] == "2026-12-01"


def test_created_subscription_appears_in_list(client, wallet_id):
    created = client.post(
        "/api/subscriptions",
        json={"name": "Netflix", "amount": 19.99, "wallet_id": wallet_id},
    ).json()

    resp = client.get("/api/subscriptions")
    assert resp.status_code == 200
    subs = resp.json()
    assert isinstance(subs, list)
    ids = [s["id"] for s in subs]
    assert created["id"] in ids


def test_update_subscription_amount_and_pause(client, wallet_id):
    created = client.post(
        "/api/subscriptions",
        json={"name": "Disney+", "amount": 11.99, "wallet_id": wallet_id},
    ).json()

    update_body = {
        "name": "Disney+",
        "amount": 13.99,
        "wallet_id": wallet_id,
        "billing_day": created["billing_day"],
        "billing_cycle": created["billing_cycle"],
        "renewal_date": created["renewal_date"],
        "active": False,
    }
    resp = client.put(f"/api/subscriptions/{created['id']}", json=update_body)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["amount"] == 13.99
    assert updated["active"] is False

    # Persists on re-GET.
    subs = client.get("/api/subscriptions").json()
    fetched = next(s for s in subs if s["id"] == created["id"])
    assert fetched["amount"] == 13.99
    assert fetched["active"] is False
    assert isinstance(fetched["active"], bool)


def test_update_yearly_renewal_date(client, wallet_id):
    created = client.post(
        "/api/subscriptions",
        json={
            "name": "iCloud+",
            "amount": 99.0,
            "wallet_id": wallet_id,
            "billing_cycle": "yearly",
            "renewal_date": "2026-01-01",
        },
    ).json()

    update_body = {
        "name": "iCloud+",
        "amount": 99.0,
        "wallet_id": wallet_id,
        "billing_day": created["billing_day"],
        "billing_cycle": "yearly",
        "renewal_date": "2027-03-15",
        "active": True,
    }
    resp = client.put(f"/api/subscriptions/{created['id']}", json=update_body)
    assert resp.status_code == 200
    assert resp.json()["renewal_date"] == "2027-03-15"

    subs = client.get("/api/subscriptions").json()
    fetched = next(s for s in subs if s["id"] == created["id"])
    assert fetched["renewal_date"] == "2027-03-15"


def test_update_nonexistent_subscription_returns_404(client, wallet_id):
    resp = client.put(
        "/api/subscriptions/does-not-exist",
        json={"name": "Ghost", "amount": 1.0, "wallet_id": wallet_id},
    )
    assert resp.status_code == 404


def test_delete_removes_subscription(client, wallet_id):
    created = client.post(
        "/api/subscriptions",
        json={"name": "HBO Max", "amount": 15.99, "wallet_id": wallet_id},
    ).json()

    resp = client.delete(f"/api/subscriptions/{created['id']}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    subs = client.get("/api/subscriptions").json()
    ids = [s["id"] for s in subs]
    assert created["id"] not in ids


def test_active_field_is_json_bool(client, wallet_id):
    active_sub = client.post(
        "/api/subscriptions",
        json={"name": "Active", "amount": 1.0, "wallet_id": wallet_id, "active": True},
    ).json()
    assert active_sub["active"] is True
    assert isinstance(active_sub["active"], bool)

    paused_sub = client.post(
        "/api/subscriptions",
        json={"name": "Paused", "amount": 1.0, "wallet_id": wallet_id, "active": False},
    ).json()
    assert paused_sub["active"] is False
    assert isinstance(paused_sub["active"], bool)

    # And the booleans survive the round-trip through the DB on GET.
    subs = client.get("/api/subscriptions").json()
    for s in subs:
        assert isinstance(s["active"], bool)
