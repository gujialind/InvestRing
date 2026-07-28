from pydantic import BaseModel
from datetime import date
from typing import Optional


class PriceDataResponse(BaseModel):
    product_code: str
    market: str
    price_date: date
    unit_price: float

    class Config:
        from_attributes = True


class PriceDataSyncRequest(BaseModel):
    start_date: date
    end_date: date
