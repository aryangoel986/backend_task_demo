import os

os.environ["DATABASE_URL"] = "sqlite:///./test_orders.db"
os.environ["API_USER"], os.environ["API_PASSWORD"] = "test", "secret"

import pytest
from fastapi.testclient import TestClient

from database import Base, Product, SessionLocal, engine
from main import app

client = TestClient(app)
AUTH = ("test", "secret")


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Product(id=1, sku="TSHIRT-M", name="T-shirt", stock=1))
        db.commit()


def order(qty=1, key=None):
    headers = {"Idempotency-Key": key} if key else {}
    return client.post("/orders", json={"customer_id": "c1", "items": [{"product_id": 1, "quantity": qty}]}, auth=AUTH, headers=headers)


def test_requires_auth():
    assert client.get("/orders/1").status_code == 401


def test_create_order_reserves_stock():
    res = order()
    assert res.status_code == 201
    assert res.json()["status"] == "pending"
    assert client.get("/inventory/TSHIRT-M", auth=AUTH).json() == {"sku": "TSHIRT-M", "available": 0}


def test_no_oversell():
    assert order().status_code == 201
    assert order().status_code == 409


def test_unknown_product_is_404():
    res = client.post("/orders", json={"customer_id": "c1", "items": [{"product_id": 99, "quantity": 1}]}, auth=AUTH)
    assert res.status_code == 404


def test_idempotent_retry_creates_one_order():
    first, retry = order(key="abc"), order(key="abc")
    assert first.json()["id"] == retry.json()["id"]


def test_cancel_releases_stock_and_blocks_invalid_transition():
    order_id = order().json()["id"]
    assert client.patch(f"/orders/{order_id}/status", json={"status": "cancelled"}, auth=AUTH).status_code == 200
    assert client.get("/inventory/TSHIRT-M", auth=AUTH).json()["available"] == 1
    assert client.patch(f"/orders/{order_id}/status", json={"status": "shipped"}, auth=AUTH).status_code == 409
