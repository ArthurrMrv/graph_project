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
    start_date: Optional[str] = None  # ISO date (YYYY-MM-DD)
    end_date: Optional[str] = None    # ISO date (YYYY-MM-DD)
    chunk_size: int = 1000

class SocialImportRequest(BaseModel):
    stock: str = "TSLA"
    start_date: Optional[str] = None  # ISO date (YYYY-MM-DD)
    end_date: Optional[str] = None    # ISO date (YYYY-MM-DD)
    chunk_size: int = 1000
