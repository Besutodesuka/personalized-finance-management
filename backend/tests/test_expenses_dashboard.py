"""Tests for the expenses, dashboard, and export endpoints."""

MONTH = "2026-06"
DATE = "2026-06-15"
OTHER_MONTH = "2026-07"
OTHER_DATE = "2026-07-15"


def _make_expense(category_id, wallet_id, amount=100.0, date=DATE,
                  description="lunch", type="planned"):
    return {
        "date": date,
        "amount": amount,
        "description": description,
        "category_id": category_id,
        "wallet_id": wallet_id,
        "type": type,
    }


def test_create_expense_appears_in_month_list(client, wallet_id, category_id):
    payload = _make_expense(category_id, wallet_id, amount=150.0)
    created = client.post("/api/expenses", json=payload).json()
    assert "id" in created
    assert created["amount"] == 150.0

    listed = client.get(f"/api/expenses?month={MONTH}").json()
    ids = [e["id"] for e in listed]
    assert created["id"] in ids


def test_month_filter_excludes_other_months(client, wallet_id, category_id):
    in_month = client.post(
        "/api/expenses", json=_make_expense(category_id, wallet_id, date=DATE)
    ).json()
    other = client.post(
        "/api/expenses",
        json=_make_expense(category_id, wallet_id, date=OTHER_DATE),
    ).json()

    listed = client.get(f"/api/expenses?month={MONTH}").json()
    ids = [e["id"] for e in listed]
    assert in_month["id"] in ids
    assert other["id"] not in ids


def test_wallet_id_filter_works(client, wallet_id, category_id):
    wallets = client.get("/api/wallets").json()
    assert len(wallets) >= 2
    other_wallet_id = wallets[1]["id"]

    mine = client.post(
        "/api/expenses", json=_make_expense(category_id, wallet_id)
    ).json()
    theirs = client.post(
        "/api/expenses", json=_make_expense(category_id, other_wallet_id)
    ).json()

    listed = client.get(f"/api/expenses?wallet_id={wallet_id}").json()
    ids = [e["id"] for e in listed]
    assert mine["id"] in ids
    assert theirs["id"] not in ids
    assert all(e["wallet_id"] == wallet_id for e in listed)


def test_update_expense_amount_persists(client, wallet_id, category_id):
    created = client.post(
        "/api/expenses", json=_make_expense(category_id, wallet_id, amount=100.0)
    ).json()

    payload = _make_expense(category_id, wallet_id, amount=275.0)
    updated = client.put(f"/api/expenses/{created['id']}", json=payload).json()
    assert updated["amount"] == 275.0

    listed = client.get(f"/api/expenses?month={MONTH}").json()
    match = [e for e in listed if e["id"] == created["id"]]
    assert len(match) == 1
    assert match[0]["amount"] == 275.0


def test_update_nonexistent_expense_returns_404(client, wallet_id, category_id):
    payload = _make_expense(category_id, wallet_id)
    resp = client.put("/api/expenses/does-not-exist", json=payload)
    assert resp.status_code == 404


def test_delete_expense_removes_it(client, wallet_id, category_id):
    created = client.post(
        "/api/expenses", json=_make_expense(category_id, wallet_id)
    ).json()

    resp = client.delete(f"/api/expenses/{created['id']}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    listed = client.get(f"/api/expenses?month={MONTH}").json()
    ids = [e["id"] for e in listed]
    assert created["id"] not in ids


def test_dashboard_aggregates_spent_and_budget(client, wallet_id, category_id):
    client.post(
        "/api/expenses", json=_make_expense(category_id, wallet_id, amount=300.0)
    )

    dash = client.get(f"/api/dashboard?month={MONTH}").json()
    assert dash["total_spent"] >= 300

    breakdown = {b["wallet"]["id"]: b for b in dash["wallet_breakdown"]}
    assert wallet_id in breakdown
    entry = breakdown[wallet_id]
    assert entry["spent"] >= 300
    assert entry["remaining"] == entry["budget"] - entry["spent"]

    wallets = client.get("/api/wallets").json()
    assert dash["total_budget"] == sum(w["budget"] for w in wallets)


def test_dashboard_unexpected_count_increments(client, wallet_id, category_id):
    before = client.get(f"/api/dashboard?month={MONTH}").json()["unexpected_count"]

    client.post(
        "/api/expenses",
        json=_make_expense(category_id, wallet_id, type="unexpected"),
    )

    after = client.get(f"/api/dashboard?month={MONTH}").json()["unexpected_count"]
    assert after == before + 1


def test_export_data_json_returns_collections(client):
    resp = client.get("/api/export/data.json")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("wallets", "categories", "expenses", "subscriptions"):
        assert key in data
        assert isinstance(data[key], list)


def test_export_csv_404_when_no_expenses(client):
    # Fresh per-test client with no expenses added.
    resp = client.get("/api/export/expenses.csv")
    assert resp.status_code == 404


def test_export_csv_200_after_adding_expense(client, wallet_id, category_id):
    client.post("/api/expenses", json=_make_expense(category_id, wallet_id))
    resp = client.get("/api/export/expenses.csv")
    assert resp.status_code == 200
