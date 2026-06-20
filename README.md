# Order Management API

A standalone order management service for Forge Commerce, built to handle order creation, status updates, and inventory checks reliably at scale.

## Features
- Order creation with inventory validation
- Order status updates with state machine enforcement
- Concurrency-safe inventory deduction
- Token-based authentication on all endpoints

## Tech Stack
- Python, FastAPI
- PostgreSQL with SQLAlchemy
- Pydantic for request validation
- Uvicorn

## Setup
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Endpoints
- `POST /orders` — create a new order
- `GET /orders/{order_id}` — retrieve order details
- `PATCH /orders/{order_id}/status` — update order status

## Schema
Orders reference a `product_id` and `quantity`. Inventory is checked and decremented atomically at creation time to prevent overselling during concurrent requests.
