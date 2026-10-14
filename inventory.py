
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from database import Product, get_db


class InventoryError(Exception):
    def __init__(self, product_id: int):
        self.product_id = product_id


class ProductNotFound(InventoryError):
    pass


class OutOfStock(InventoryError):
    pass


def reserve_stock(db: Session, product_id: int, qty: int) -> None:
    """Atomic conditional decrement.

    The check and the write are one SQL statement, so two concurrent requests
    (even on different app instances) can never both take the last unit.
    """
    result = db.execute(
        update(Product)
        .where(Product.id == product_id, Product.stock >= qty)
        .values(stock=Product.stock - qty)
    )
    if result.rowcount == 0:
        if db.get(Product, product_id) is None:
            raise ProductNotFound(product_id)
        raise OutOfStock(product_id)


def release_stock(db: Session, product_id: int, qty: int) -> None:
    db.execute(update(Product).where(Product.id == product_id).values(stock=Product.stock + qty))


router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/{sku}")
def get_inventory(sku: str, db: Session = Depends(get_db)):
    """Same response shape as the legacy inventory service: {sku, available}."""
    product = db.query(Product).filter(Product.sku == sku).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Unknown SKU")
    return {"sku": product.sku, "available": product.stock}
