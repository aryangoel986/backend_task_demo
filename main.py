import os
import secrets
from datetime import datetime
from enum import Enum

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import inventory
from database import Base, Order, OrderItem, engine, get_db

security = HTTPBasic()


def require_auth(creds: HTTPBasicCredentials = Depends(security)) -> None:
    user, password = os.getenv("API_USER"), os.getenv("API_PASSWORD")
    if not (user and password):
        raise HTTPException(status_code=503, detail="Auth is not configured")
    valid = secrets.compare_digest(creds.username, user) & secrets.compare_digest(creds.password, password)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Basic"})


class Status(str, Enum):
    pending = "pending"
    paid = "paid"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


ALLOWED_TRANSITIONS = {
    Status.pending: {Status.paid, Status.cancelled},
    Status.paid: {Status.shipped, Status.cancelled},
    Status.shipped: {Status.delivered},
}


class ItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=100)


class OrderIn(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    items: list[ItemIn] = Field(min_length=1, max_length=50)


class StatusUpdate(BaseModel):
    status: Status


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    quantity: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: str
    status: Status
    created_at: datetime
    items: list[ItemOut]


Base.metadata.create_all(engine)
app = FastAPI(title="Forge Commerce Order Service", dependencies=[Depends(require_auth)])
app.include_router(inventory.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/orders", response_model=OrderOut, status_code=201)
def create_order(
    body: OrderIn,
    idempotency_key: str | None = Header(default=None, max_length=64),
    db: Session = Depends(get_db),
):
    # Flash-sale clients retry aggressively; the same key must never create two orders.
    if idempotency_key:
        existing = db.query(Order).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    # Fixed product order means concurrent multi-item orders lock rows in the same sequence (no deadlocks).
    items = sorted(body.items, key=lambda i: i.product_id)
    try:
        for item in items:
            inventory.reserve_stock(db, item.product_id, item.quantity)
        order = Order(
            customer_id=body.customer_id,
            idempotency_key=idempotency_key,
            items=[OrderItem(product_id=i.product_id, quantity=i.quantity) for i in items],
        )
        db.add(order)
        db.commit()
    except inventory.ProductNotFound as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Product {e.product_id} not found")
    except inventory.OutOfStock as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Insufficient stock for product {e.product_id}")
    except IntegrityError:
        # Lost a race on the same idempotency key: return the order the other request created.
        db.rollback()
        return db.query(Order).filter_by(idempotency_key=idempotency_key).one()
    db.refresh(order)
    return order


@app.get("/orders", response_model=list[OrderOut])
def list_orders(
    customer_id: str,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return (
        db.query(Order)
        .filter(Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


@app.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.patch("/orders/{order_id}/status", response_model=OrderOut)
def update_status(order_id: int, body: StatusUpdate, db: Session = Depends(get_db)):
    order = db.get(Order, order_id, with_for_update=True)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    current = Status(order.status)
    if body.status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise HTTPException(status_code=409, detail=f"Cannot move order from {current.value} to {body.status.value}")
    if body.status == Status.cancelled:
        for item in order.items:
            inventory.release_stock(db, item.product_id, item.quantity)
    order.status = body.status.value
    db.commit()
    db.refresh(order)
    return order
