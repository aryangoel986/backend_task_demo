import uuid
from datetime import datetime, timezone
from threading import Lock

class OrderDatabase:
    """
    In-memory order store standing in for PostgreSQL during local development.
    In production this would be SQLAlchemy models against a real Postgres instance,
    with order_id indexed and customer_id indexed for fast lookup.
    """

    def __init__(self):
        self._orders = {}
        self._lock = Lock()

    def create_order(self, product_id: str, quantity: int, customer_id: str, status) -> dict:
        with self._lock:
            order_id = str(uuid.uuid4())
            order = {
                "order_id": order_id,
                "product_id": product_id,
                "quantity": quantity,
                "customer_id": customer_id,
                "status": status.value,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._orders[order_id] = order
            return order

    def get_order(self, order_id: str) -> dict | None:
        with self._lock:
            return self._orders.get(order_id)

    def update_order_status(self, order_id: str, status) -> dict:
        with self._lock:
            order = self._orders[order_id]
            order["status"] = status.value
            order["updated_at"] = datetime.now(timezone.utc).isoformat()
            return order
