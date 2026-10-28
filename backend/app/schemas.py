import re
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.security import normalize_phone


def _check_phone(value: str) -> str:
    phone = normalize_phone(value)
    if not re.fullmatch(r"[6-9]\d{9}", phone):
        raise ValueError("10 digit ka mobile number daalo")
    return phone


class RegisterIn(BaseModel):
    phone: str
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=100)
    shop_name: str = Field(min_length=2, max_length=120)
    area: str = Field(min_length=2, max_length=120)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    upi_vpa: Optional[str] = Field(default=None, max_length=80)

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, value):
        return _check_phone(value)

    @field_validator("upi_vpa")
    @classmethod
    def vpa_ok(cls, value):
        if value and not re.fullmatch(r"[\w.\-]{2,}@[A-Za-z]{2,}", value):
            raise ValueError("UPI ID aise likho: naam@bank")
        return value


class LoginIn(BaseModel):
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, value):
        return _check_phone(value)


class ShopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    area: str
    lat: float
    lng: float
    upi_vpa: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    phone: str
    shop: ShopOut


class TokenOut(BaseModel):
    token: str
    user: UserOut


class BatchIn(BaseModel):
    product_id: Optional[int] = None
    product_name: Optional[str] = Field(default=None, max_length=120)
    category: Optional[str] = None
    mrp: Optional[float] = Field(default=None, gt=0)
    qty: int = Field(gt=0, le=100000)
    cost_price: float = Field(ge=0)
    sell_price: float = Field(gt=0)
    received_on: Optional[date] = None
    expiry_date: Optional[date] = None

    @model_validator(mode="after")
    def product_given(self):
        if self.product_id is None and not (self.product_name and self.category):
            raise ValueError("Product chuno, ya naam aur category do")
        if self.expiry_date and self.received_on and self.expiry_date < self.received_on:
            raise ValueError("Expiry maal aane ki date se pehle nahi ho sakti")
        return self


class SaleIn(BaseModel):
    product_id: int
    qty: int = Field(gt=0, le=100000)
    unit_price: Optional[float] = Field(default=None, gt=0)
    sold_on: Optional[date] = None  # backdated sale; omitted = now (checked in api/stock.py)