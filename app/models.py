from pydantic import BaseModel
from typing import Optional

class SentimentRequest(BaseModel):
    text: str
    api_key: Optional[str] = None  # Optional, will use HF_TOKEN from .env if not provided

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

class SyncSentimentsRequest(BaseModel):
    stock: Optional[str] = None  # Filter by stock ticker
    start_date: Optional[str] = None  # ISO date (YYYY-MM-DD)
    end_date: Optional[str] = None  # ISO date (YYYY-MM-DD)
    limit: Optional[int] = None  # Maximum number of tweets to process
    overwrite: bool = False  # If True, re-analyze tweets that already have sentiment
    batch_size: int = 50  # Number of tweets to process per batch
    api_key: Optional[str] = None  # Optional, will use HF_TOKEN from .env if not provided

class SyncSentimentsResponse(BaseModel):
    tweets_processed: int
    tweets_updated: int
    errors: int
    stock: Optional[str] = None
    date_range: Optional[dict] = None
