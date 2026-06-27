"""Tests for the master wallet API (routers/master_wallet.py)."""


def _total_budgets(client):
    wallets = client.get("/api/wallets").json()
    return sum(w["budget"] for w in wallets), len(wallets)


def test_initial_balance_is_zero(client):
    resp = client.get("/api/master-wallet")
    assert resp.status_code == 200
    assert resp.json()["balance"] == 0


def test_adjust_add_then_subtract(client):
    resp = client.post("/api/master-wallet/adjust", json={"amount": 50000})
    assert resp.status_code == 200
    assert resp.json()["balance"] == 50000

    resp = client.post("/api/master-wallet/adjust", json={"amount": -5000})
    assert resp.status_code == 200
    assert resp.json()["balance"] == 45000


def test_adjust_can_go_negative(client):
    resp = client.post("/api/master-wallet/adjust", json={"amount": -100})
    assert resp.status_code == 200
    assert resp.json()["balance"] == -100


def test_refill_insufficient_balance_returns_400(client):
    # Balance starts at 0, which is below the total wallet budgets.
    resp = client.post("/api/master-wallet/refill")
    assert resp.status_code == 400


def test_refill_with_enough_balance(client):
    total, wallet_count = _total_budgets(client)
    # Sanity check the seeded defaults.
    assert total == 26000

    # Top up to exactly the total budget so we can verify the math cleanly.
    starting = total
    client.post("/api/master-wallet/adjust", json={"amount": starting})

    resp = client.post("/api/master-wallet/refill")
    assert resp.status_code == 200
    data = resp.json()

    assert data["ok"] is True
    assert data["deducted"] == total
    assert data["new_balance"] == starting - total

    distributions = data["distributions"]
    assert len(distributions) == wallet_count
    assert sum(d["amount"] for d in distributions) == total


def test_balance_reflects_refill(client):
    total, _ = _total_budgets(client)
    starting = total + 1000
    client.post("/api/master-wallet/adjust", json={"amount": starting})

    refill = client.post("/api/master-wallet/refill")
    assert refill.status_code == 200
    new_balance = refill.json()["new_balance"]

    resp = client.get("/api/master-wallet")
    assert resp.status_code == 200
    assert resp.json()["balance"] == new_balance
    assert new_balance == starting - total
