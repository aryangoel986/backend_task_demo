
# Forge Commerce — Order Management Service

Standalone FastAPI service for order creation, retrieval and status updates, built to survive flash-sale traffic without overselling.

## Endpoints (all require HTTP Basic auth)
| Method | Path | Purpose |
|---|---|---|
| POST | `/orders` | Create an order, reserving stock atomically (`Idempotency-Key` header supported) |
| GET | `/orders/{id}` | Fetch one order |
| GET | `/orders?customer_id=` | List a customer's orders (paginated) |
| PATCH | `/orders/{id}/status` | Move an order through `pending → paid → shipped → delivered` or cancel it |
| GET | `/inventory/{sku}` | Legacy-compatible stock lookup (`{sku, available}`) |
| GET | `/health` | Health check |

Status codes: `201` created, `401` bad credentials, `404` unknown order/product, `409` out of stock or invalid status transition, `422` invalid input.

## Design decisions
- **No overselling:** stock is reserved with a single conditional `UPDATE ... WHERE stock >= qty`. The check and the write happen in one statement, so concurrent requests can't both claim the last unit. A `CHECK (stock >= 0)` constraint backs this up at the database level.
- **Horizontal scaling:** the app is stateless and holds no in-process locks; all correctness lives in the database, so any number of instances can run behind a load balancer. Swap SQLite for Postgres via `DATABASE_URL`.
- **Flash-sale retries:** an optional `Idempotency-Key` (unique column) guarantees a retried request never creates a duplicate order.
- **Deadlock avoidance:** multi-item orders reserve products in `product_id` order.
- **Schema:** normalized into `products`, `orders` and `order_items`, with indexes on `orders(customer_id, created_at)`, `orders.status` and both `order_items` foreign keys.
- **Backwards compatibility:** `/inventory/{sku}` keeps the existing inventory service's response shape.

## Run
```bash
pip install -r requirements.txt
export API_USER=admin API_PASSWORD=<strong-password>
uvicorn main:app --reload
```

## Test
```bash
pytest -q
```
Covers auth, stock reservation, oversell protection, unknown products, idempotent retries, and cancellation/transition rules.
