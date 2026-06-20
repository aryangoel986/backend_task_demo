from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from enum import Enum
from inventory import InventoryService
from database import OrderDatabase

app = FastAPI(title="Order Management API")

inventory = InventoryService()
db = OrderDatabase()

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"

VALID_TRANSITIONS = {
    OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
    OrderStatus.CONFIRMED: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
    OrderStatus.SHIPPED: [],
    OrderStatus.CANCELLED: []
}

class CreateOrderRequest(BaseModel):
    product_id: str
    quantity: int
    customer_id: str

class UpdateStatusRequest(BaseModel):
    status: OrderStatus

def verify_token(authorization: str = Header(...)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/orders", status_code=201)
def create_order(request: CreateOrderRequest, token: str = Depends(verify_token)):
    if request.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    reserved = inventory.reserve_stock(request.product_id, request.quantity)
    if not reserved:
        raise HTTPException(status_code=409, detail="Insufficient stock for this product")

    try:
        order = db.create_order(
            product_id=request.product_id,
            quantity=request.quantity,
            customer_id=request.customer_id,
            status=OrderStatus.PENDING
        )
        return order
    except Exception as e:
        inventory.release_stock(request.product_id, request.quantity)
        raise HTTPException(status_code=500, detail=f"Order creation failed: {str(e)}")

@app.get("/orders/{order_id}")
def get_order(order_id: str, token: str = Depends(verify_token)):
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.patch("/orders/{order_id}/status")
def update_status(order_id: str, request: UpdateStatusRequest, token: str = Depends(verify_token)):
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    current_status = OrderStatus(order["status"])
    if request.status not in VALID_TRANSITIONS[current_status]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {current_status} to {request.status}"
        )

    updated_order = db.update_order_status(order_id, request.status)

    if request.status == OrderStatus.CANCELLED and current_status != OrderStatus.SHIPPED:
        inventory.release_stock(order["product_id"], order["quantity"])

    return updated_order
