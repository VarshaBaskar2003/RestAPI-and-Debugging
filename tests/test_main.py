import pytest
from fastapi.testclient import TestClient
import main
from main import app, expenses

client = TestClient(app)
safe_client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_expenses():
    """Runs around every test: the data is restored so tests don't affect each other."""
    original = {key: value.copy() for key, value in expenses.items()}
    original_next_id = main.next_id
    yield
    expenses.clear()
    expenses.update(original)
    main.next_id = original_next_id


def new_expense(**changes):
    """A valid expense body. Pass a field to override it, e.g. new_expense(amount=-5)."""
    body = {
        "description": "Books",
        "amount": 250,
        "category": "Education",
        "expense_date": "2026-10-03",
    }
    body.update(changes)
    return body


def assert_bad_request(response):
    """Checks the 400 status and our error format."""
    assert response.status_code == 400
    assert response.json()["error"] == "Validation failed"
    assert len(response.json()["details"]) > 0


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Expense Tracker API is running"



def test_summary_returns_total_amount():
    
    response = client.get("/expenses/summary")
    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert response.json()["total_amount"] == 630


def test_summary_after_create():
    client.post("/expenses", json=new_expense(amount=250))
    response = client.get("/expenses/summary")
    assert response.json()["count"] == 3
    assert response.json()["total_amount"] == 880  # 630 + 250


def test_summary_after_delete():
    client.delete("/expenses/1")
    response = client.get("/expenses/summary")
    assert response.json()["count"] == 1
    assert response.json()["total_amount"] == 180


def test_get_existing_expense():
    response = client.get("/expenses/1")
    assert response.status_code == 200
    assert response.json()["description"] == "Travel"


def test_get_missing_expense_returns_404():
    response = client.get("/expenses/999")
    assert response.status_code == 404
    assert response.json() == {"error": "Expense not found"}


def test_get_with_text_id_returns_400():
    response = client.get("/expenses/abc")
    assert_bad_request(response)


def test_list_all_expenses():
    response = client.get("/expenses")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_filter_by_category():
    response = client.get("/expenses", params={"category": "Food"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["category"] == "Food"


def test_filter_ignores_upper_lower_case():
    response = client.get("/expenses", params={"category": "food"})
    assert len(response.json()) == 1
    assert response.json()[0]["category"] == "Food"


def test_filter_with_no_match_returns_empty_list():
    response = client.get("/expenses", params={"category": "Rent"})
    assert response.status_code == 200
    assert response.json() == []



def test_create_expense():
    response = client.post("/expenses", json=new_expense())
    assert response.status_code == 201
    assert response.json()["id"] == 3
    assert response.json()["amount"] == 250


def test_created_expense_can_be_fetched():
    client.post("/expenses", json=new_expense())
    response = client.get("/expenses/3")
    assert response.status_code == 200
    assert response.json()["description"] == "Books"


def test_create_trims_spaces_and_rounds_amount():
    response = client.post(
        "/expenses",
        json=new_expense(description="  Tea  ", amount=10.456),
    )
    assert response.status_code == 201
    assert response.json()["description"] == "Tea"
    assert response.json()["amount"] == 10.46



def test_create_rejects_negative_amount():
    response = client.post("/expenses", json=new_expense(amount=-250))
    assert_bad_request(response)


def test_create_rejects_zero_amount():
    response = client.post("/expenses", json=new_expense(amount=0))
    assert_bad_request(response)


def test_create_rejects_too_large_amount():
    response = client.post("/expenses", json=new_expense(amount=10**12))
    assert_bad_request(response)


def test_create_rejects_text_as_amount():
    response = client.post("/expenses", json=new_expense(amount="abc"))
    assert_bad_request(response)


def test_create_rejects_invalid_date():
    response = client.post("/expenses", json=new_expense(expense_date="hello"))
    assert_bad_request(response)


def test_create_rejects_impossible_date():
    response = client.post("/expenses", json=new_expense(expense_date="2026-13-45"))
    assert_bad_request(response)


def test_create_rejects_week_date_format():
    # Python 3.11+ would accept this format, we only allow YYYY-MM-DD.
    response = client.post("/expenses", json=new_expense(expense_date="2026-W40-1"))

    assert_bad_request(response)


def test_create_rejects_empty_description():
    response = client.post("/expenses", json=new_expense(description=""))
    assert_bad_request(response)


def test_create_rejects_spaces_only_description():
    response = client.post("/expenses", json=new_expense(description="     "))
    assert_bad_request(response)


def test_create_rejects_too_long_description():
    response = client.post("/expenses", json=new_expense(description="x" * 201))
    assert_bad_request(response)


def test_create_rejects_missing_field():
    body = new_expense()
    del body["expense_date"]
    response = client.post("/expenses", json=body)
    assert_bad_request(response)


def test_create_rejects_unknown_field():
    response = client.post("/expenses", json=new_expense(amout=5))
    assert_bad_request(response)


def test_failed_create_does_not_store_anything():
    client.post("/expenses", json=new_expense(amount=-1))
    response = client.get("/expenses")
    assert len(response.json()) == 2


def test_update_only_amount():
    response = client.put("/expenses/1", json={"amount": 500})
    assert response.status_code == 200
    assert response.json()["amount"] == 500
    # the other fields are unchanged
    assert response.json()["description"] == "Travel"
    assert response.json()["category"] == "Travel"


def test_update_date():
    response = client.put("/expenses/1", json={"expense_date": "2026-10-05"})
    assert response.status_code == 200
    assert response.json()["expense_date"] == "2026-10-05"


def test_update_rejects_negative_amount():
    response = client.put("/expenses/1", json={"amount": -100})
    assert_bad_request(response)
    # the failed update must not change the stored expense
    assert client.get("/expenses/1").json()["amount"] == 450.0


def test_update_rejects_invalid_date():
    response = client.put("/expenses/1", json={"expense_date": "hello"})
    assert_bad_request(response)


def test_update_rejects_null_description():
    response = client.put("/expenses/1", json={"description": None})
    assert_bad_request(response)
    assert client.get("/expenses/1").json()["description"] == "Travel"


def test_update_rejects_null_amount():
    response = client.put("/expenses/1", json={"amount": None})
    assert_bad_request(response)
    assert client.get("/expenses/1").json()["amount"] == 450.0


def test_update_rejects_null_date():    
    response = client.put("/expenses/1", json={"expense_date": None})
    assert_bad_request(response)
    assert client.get("/expenses/1").json()["expense_date"] == "2026-10-01"


def test_update_rejects_empty_body():
    response = client.put("/expenses/1", json={})
    assert_bad_request(response)


def test_update_rejects_unknown_field():
    response = client.put("/expenses/1", json={"amt": 5})
    assert_bad_request(response)


def test_update_missing_expense_returns_404():
    response = client.put("/expenses/999", json={"amount": 100})
    assert response.status_code == 404
    assert response.json() == {"error": "Expense not found"}


def test_delete_expense():
    response = client.delete("/expenses/1")
    assert response.status_code == 204
    assert response.content == b""  # 204 has no body


def test_deleted_expense_is_gone():
    client.delete("/expenses/1")
    response = client.get("/expenses/1")
    assert response.status_code == 404


def test_delete_missing_expense_returns_404():
    response = client.delete("/expenses/999")
    assert response.status_code == 404
    assert response.json() == {"error": "Expense not found"}



def test_unexpected_error_returns_500_without_details(monkeypatch):    
    class BrokenStore(dict):
        def values(self):
            raise RuntimeError("secret internal detail")

    monkeypatch.setattr(main, "expenses", BrokenStore())
    response = safe_client.get("/expenses")
    assert response.status_code == 500
    assert response.json() == {"error": "Internal server error"}
    assert "secret" not in response.text  