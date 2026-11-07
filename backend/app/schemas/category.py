"""Category Pydantic Schemas"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    type: str = Field(description="One of: income, expense, transfer, investment")
    icon: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=20)
    parent_id: uuid.UUID | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid_types = {"income", "expense", "transfer", "investment"}
        val = v.lower().strip()
        if val not in valid_types:
            raise ValueError(f"Invalid category type. Must be one of: {sorted(valid_types)}")
        return val


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    icon: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=20)
    parent_id: uuid.UUID | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    type: str
    icon: str | None
    color: str | None
    is_system: bool
    parent_id: uuid.UUID | None
    created_at: datetime
