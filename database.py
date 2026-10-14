import os
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# SQLite for local dev; point DATABASE_URL at Postgres in production.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./orders.db")
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    sku = Column(String(64), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    # Last line of defence: the DB itself refuses negative stock.
    __table_args__ = (CheckConstraint("stock >= 0", name="ck_stock_non_negative"),)


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    idempotency_key = Column(String(64), unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan", lazy="selectin")
    __table_args__ = (Index("ix_orders_customer_created", "customer_id", "created_at"),)


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    order = relationship("Order", back_populates="items")
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_quantity_positive"),)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
