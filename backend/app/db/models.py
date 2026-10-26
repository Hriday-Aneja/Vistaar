from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


class Shop(Base):
    __tablename__ = "shops"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    owner_name: Mapped[str] = mapped_column(String(120))
    area: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    upi_vpa: Mapped[str] = mapped_column(String(80))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)  # demo shops never mix with real ones
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(200))
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    shop: Mapped[Shop] = relationship()


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    name_hi: Mapped[str] = mapped_column(String(120), default="")
    category: Mapped[str] = mapped_column(String(60), index=True)
    unit: Mapped[str] = mapped_column(String(20), default="pack")
    default_shelf_days: Mapped[int] = mapped_column(Integer)
    mrp: Mapped[float] = mapped_column(Float)


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    qty_received: Mapped[int] = mapped_column(Integer)
    qty_left: Mapped[int] = mapped_column(Integer)
    cost_price: Mapped[float] = mapped_column(Float)
    sell_price: Mapped[float] = mapped_column(Float)
    received_on: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_source: Mapped[str] = mapped_column(String(12), default="entered")  # entered | default | inferred
    source: Mapped[str] = mapped_column(String(12), default="manual")  # manual | invoice | ocr | swap | bulk
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    product: Mapped[Product] = relationship()


class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("batches.id"), nullable=True)
    qty: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float)
    sold_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_simulated: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (Index("ix_sales_shop_product_time", "shop_id", "product_id", "sold_at"),)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    phone: Mapped[str] = mapped_column(String(10))
    phone_hash: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    last_visit: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    aliases: Mapped[list["CustomerAlias"]] = relationship(cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("shop_id", "phone", name="uq_customer_shop_phone"),)


class CustomerAlias(Base):
    __tablename__ = "customer_aliases"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    alias: Mapped[str] = mapped_column(String(120))


class KhataEntry(Base):
    __tablename__ = "khata_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)  # positive = udhaar given, negative = payment received
    note: Mapped[str] = mapped_column(String(200), default="")
    created_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class KhataReminder(Base):
    __tablename__ = "khata_reminders"
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    message: Mapped[str] = mapped_column(Text)
    upi_link: Mapped[str] = mapped_column(String(300))
    channel: Mapped[str] = mapped_column(String(12), default="mock")  # mock | whatsapp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Swap(Base):
    __tablename__ = "swaps"
    id: Mapped[int] = mapped_column(primary_key=True)
    from_shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    to_shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    qty: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    score_breakdown: Mapped[dict] = mapped_column(JSON)
    why: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="proposed")  # proposed | approved | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class EventCalendar(Base):
    __tablename__ = "event_calendar"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))  # heatwave | cricket | wedding_season | festival
    label: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    categories: Mapped[list] = mapped_column(JSON)
    suggested_action: Mapped[str] = mapped_column(String(200))


class PulseAlert(Base):
    __tablename__ = "pulse_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    z_score: Mapped[float] = mapped_column(Float)
    cause: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(200))
    why: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Distributor(Base):
    __tablename__ = "distributors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(10), default="")
    # Lowest price this distributor will go to in a reverse auction, as a share of its quote.
    floor_ratio: Mapped[float] = mapped_column(Float, default=0.9)


class DistributorQuote(Base):
    __tablename__ = "distributor_quotes"
    id: Mapped[int] = mapped_column(primary_key=True)
    distributor_id: Mapped[int] = mapped_column(ForeignKey("distributors.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    unit_price: Mapped[float] = mapped_column(Float)
    min_qty: Mapped[int] = mapped_column(Integer)
    delivery_days: Mapped[int] = mapped_column(Integer)
    valid_till: Mapped[date] = mapped_column(Date)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    distributor_id: Mapped[int] = mapped_column(ForeignKey("distributors.id"))
    lines: Mapped[list] = mapped_column(JSON)  # [{product_id, shop_id, qty, unit_price}]
    total: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(12), default="proposed")
    thread_id: Mapped[str] = mapped_column(String(40), default="")
    audit_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, unique=True)
    kind: Mapped[str] = mapped_column(String(30))
    ref_id: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)

class OrderPlan(Base):
    __tablename__ = "order_plans"

    thread_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default="awaiting_approval",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)