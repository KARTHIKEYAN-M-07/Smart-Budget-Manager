"""Shopping orders and itemized returns models"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, get_utc_now

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.household import Household
    from app.models.transaction import Transaction
    from app.models.user import User


class OrderStatus(enum.StrEnum):
    PLACED = "PLACED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    PARTIALLY_RETURNED = "PARTIALLY_RETURNED"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"


class OrderItemStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"


class ReturnRefundStatus(enum.StrEnum):
    PENDING = "PENDING"
    REFUNDED = "REFUNDED"
    REJECTED = "REJECTED"


class ShoppingOrder(Base, UUIDPrimaryKeyMixin):
    """Shopping order entity for itemized e-commerce and store purchases."""

    __tablename__ = "shopping_orders"

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    merchant_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    order_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=OrderStatus.PLACED.value)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PLACED', 'SHIPPED', 'DELIVERED', 'PARTIALLY_RETURNED', 'RETURNED', 'CANCELLED')",
            name="ck_shopping_orders_status",
        ),
        CheckConstraint("total_amount >= 0", name="ck_shopping_orders_total_amount_positive"),
    )

    household: Mapped["Household"] = relationship("Household")
    user: Mapped["User"] = relationship("User")
    payment_transaction: Mapped[Optional["Transaction"]] = relationship("Transaction")
    items: Mapped[list["ShoppingOrderItem"]] = relationship(
        "ShoppingOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="ShoppingOrderItem.name",
    )
    returns: Mapped[list["OrderReturn"]] = relationship(
        "OrderReturn",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderReturn.return_date.desc()",
    )


class ShoppingOrderItem(Base, UUIDPrimaryKeyMixin):
    """Individual item within an order."""

    __tablename__ = "shopping_order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shopping_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=OrderItemStatus.ACTIVE.value)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_shopping_order_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_shopping_order_items_unit_price_positive"),
        CheckConstraint("total_price >= 0", name="ck_shopping_order_items_total_price_positive"),
        CheckConstraint(
            "status IN ('ACTIVE', 'RETURNED', 'CANCELLED')",
            name="ck_shopping_order_items_status",
        ),
    )

    order: Mapped["ShoppingOrder"] = relationship("ShoppingOrder", back_populates="items")
    category: Mapped[Optional["Category"]] = relationship("Category")


class OrderReturn(Base, UUIDPrimaryKeyMixin):
    """Return and refund tracking for an order or specific item."""

    __tablename__ = "order_returns"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shopping_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shopping_order_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    refund_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    refund_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ReturnRefundStatus.PENDING.value
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("refund_amount >= 0", name="ck_order_returns_refund_amount_positive"),
        CheckConstraint(
            "refund_status IN ('PENDING', 'REFUNDED', 'REJECTED')",
            name="ck_order_returns_refund_status",
        ),
    )

    order: Mapped["ShoppingOrder"] = relationship("ShoppingOrder", back_populates="returns")
    item: Mapped[Optional["ShoppingOrderItem"]] = relationship("ShoppingOrderItem")
    refund_transaction: Mapped[Optional["Transaction"]] = relationship("Transaction")
