from pydantic import BaseModel
from typing import Optional

class SentimentRequest(BaseModel):
    text: str
    api_key: str

class SentimentResponse(BaseModel):
    sentiment: int
    confidence: float

class StockSyncRequest(BaseModel):
    stock: str = "TSLA"

class SocialImportRequest(BaseModel):
    stock: str = "TSLA"
