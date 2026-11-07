"""Pydantic schemas for shopping orders, order items, and returns"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.order import OrderItemStatus, OrderStatus, ReturnRefundStatus


class ShoppingOrderItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category_id: uuid.UUID | None = None
    quantity: int = Field(default=1, gt=0)
    unit_price: Decimal = Field(..., ge=Decimal("0.00"))
    total_price: Decimal | None = Field(default=None, ge=Decimal("0.00"))


class ShoppingOrderItemResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    status: OrderItemStatus

    model_config = {"from_attributes": True}


class OrderReturnCreate(BaseModel):
    item_id: uuid.UUID | None = None
    return_date: date
    refund_amount: Decimal = Field(..., gt=Decimal("0.00"), le=Decimal("999999999.99"))
    reason: str = Field(..., min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=500)
    create_refund_transaction: bool = False
    refund_account_id: uuid.UUID | None = None


class OrderReturnResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    item_id: uuid.UUID | None = None
    refund_transaction_id: uuid.UUID | None = None
    return_date: date
    refund_amount: Decimal
    reason: str
    refund_status: ReturnRefundStatus
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShoppingOrderCreate(BaseModel):
    merchant_name: str = Field(..., min_length=1, max_length=100)
    order_number: str | None = Field(default=None, max_length=100)
    order_date: date
    status: OrderStatus = OrderStatus.PLACED
    total_amount: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("999999999.99"))
    notes: str | None = Field(default=None, max_length=500)
    receipt_url: str | None = Field(default=None, max_length=500)
    payment_transaction_id: uuid.UUID | None = None
    items: list[ShoppingOrderItemCreate] = []


class ShoppingOrderUpdate(BaseModel):
    merchant_name: str | None = Field(default=None, min_length=1, max_length=100)
    order_number: str | None = Field(default=None, max_length=100)
    order_date: date | None = None
    status: OrderStatus | None = None
    total_amount: Decimal | None = Field(default=None, ge=Decimal("0.00"), le=Decimal("999999999.99"))
    notes: str | None = Field(default=None, max_length=500)
    receipt_url: str | None = Field(default=None, max_length=500)
    payment_transaction_id: uuid.UUID | None = None
    version: int = Field(..., description="Optimistic locking version")


class ShoppingOrderLinkTransactionRequest(BaseModel):
    payment_transaction_id: uuid.UUID
    version: int = Field(..., description="Current version of the order")


class ShoppingOrderResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    user_id: uuid.UUID
    user_name: str | None = None
    payment_transaction_id: uuid.UUID | None = None
    is_payment_linked: bool
    merchant_name: str
    order_number: str | None = None
    order_date: date
    status: OrderStatus
    total_amount: Decimal
    notes: str | None = None
    receipt_url: str | None = None
    version: int
    created_at: datetime
    items: list[ShoppingOrderItemResponse] = []
    returns: list[OrderReturnResponse] = []

    model_config = {"from_attributes": True}
