import threading

class InventoryService:
    """
    Handles atomic stock reservation to prevent overselling
    during concurrent order placement.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._stock = {
            "prod_001": 50,
            "prod_002": 30,
            "prod_003": 100,
        }

    def reserve_stock(self, product_id: str, quantity: int) -> bool:
        with self._lock:
            available = self._stock.get(product_id, 0)
            if available < quantity:
                return False
            self._stock[product_id] = available - quantity
            return True

    def release_stock(self, product_id: str, quantity: int) -> None:
        with self._lock:
            self._stock[product_id] = self._stock.get(product_id, 0) + quantity

    def get_stock(self, product_id: str) -> int:
        with self._lock:
            return self._stock.get(product_id, 0)
