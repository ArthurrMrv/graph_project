from fastapi import APIRouter
from typing import Optional, List
import pandas as pd
import hashlib
import re
import os
from pydantic import BaseModel

from app.services.neo4j_service import neo4j_service

router = APIRouter()

STOCKS_CSV = "data/Stock Tweets Sentiment Analysis/stock_yfinance_data.csv"
SOCIAL_CSV = "data/Stock Tweets Sentiment Analysis/stock_tweets.csv"


class PipelineRequest(BaseModel):
    stock: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    chunk_size: int = 2000


def _extract_hashtags(text: str) -> List[str]:
    return re.findall(r"#(\w+)", text or "")


@router.post("/dataset_to_graph", tags=["Pipeline"])
async def dataset_to_graph(request: PipelineRequest):
    """
    Unified pipeline to ingest both Stock Price data and Social Tweets for a given ticker.
    Refactored to simplified schema:
    - Nodes: Stock, TradingDay, Tweet, HashTag
    - Relationships: PRICE_ON, DISCUSSES, ON_DATE, TAGGED_WITH
    """
    
    # 1. Pipeline Setup
    neo4j_service.create_constraints()
    
    if not os.path.exists(STOCKS_CSV) or not os.path.exists(SOCIAL_CSV):
        return {"status": "error", "message": "One or more data files not found"}

    default_start = pd.to_datetime("2015-01-01")
    default_end = pd.to_datetime("2024-01-01")
    start_date = pd.to_datetime(request.start_date) if request.start_date else default_start
    end_date = pd.to_datetime(request.end_date) if request.end_date else default_end
   
    # 2. Ingest Stock Data
    stock_records = 0
    stock_cypher = """
    UNWIND $rows AS row
    MERGE (s:Stock {ticker: row.ticker})
    MERGE (d:TradingDay {date: row.date})
    MERGE (s)-[r:PRICE_ON]->(d)
    SET r.open = row.open,
        r.high = row.high,
        r.low = row.low,
        r.close = row.close,
        r.volume = row.volume,
        r.daily_change = row.daily_change,
        r.volatility = row.volatility
    """
    
    # Read Stock CSV
    for chunk in pd.read_csv(STOCKS_CSV, chunksize=request.chunk_size):
        chunk["Date"] = pd.to_datetime(chunk["Date"], errors="coerce")
        mask = (chunk["Date"] >= start_date) & (chunk["Date"] <= end_date) & (chunk["Stock Name"] == request.stock)
        filtered = chunk.loc[mask]
        
        rows = []
        for _, row in filtered.iterrows():
            if pd.isna(row["Date"]):
                continue
            
            open_price = float(row["Open"])
            close_price = float(row["Close"])
            high_price = float(row["High"])
            low_price = float(row["Low"])
            
            # Calculate metrics
            daily_change = (close_price - open_price) / open_price if open_price != 0 else 0.0
            volatility = (high_price - low_price) / open_price if open_price != 0 else 0.0

            rows.append({
                "ticker": str(row["Stock Name"]),
                "date": row["Date"].strftime("%Y-%m-%d"),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": int(row["Volume"]),
                "daily_change": daily_change,
                "volatility": volatility
            })
            
        if rows:
            neo4j_service.run_query(stock_cypher, {"rows": rows})
            stock_records += len(rows)

    # 3. Ingest Tweet Data 
    tweet_records = 0
    tweet_cypher = """
    UNWIND $rows AS row
    MERGE (s:Stock {ticker: row.ticker})
    MERGE (t:Tweet {id: row.tweet_id})
    SET t.text = row.text, 
        t.date = row.date,
        t.sentiment = row.sentiment,
        t.confidence = row.confidence

    // Link to Stock
    MERGE (t)-[:DISCUSSES]->(s)

    // Link to TradingDay (Group by Date)
    MERGE (d:TradingDay {date: row.date_only})
    MERGE (t)-[:ON_DATE]->(d)

    // Link to HashTags
    FOREACH (tag IN row.hashtags |
        MERGE (h:HashTag {tag: tag})
        MERGE (t)-[:TAGGED_WITH]->(h))
    """
    
    # Read Social CSV
    for chunk in pd.read_csv(SOCIAL_CSV, chunksize=request.chunk_size, on_bad_lines="skip"):
        chunk["Date"] = pd.to_datetime(chunk["Date"], errors="coerce")
        chunk["Date"] = chunk["Date"].dt.tz_localize(None)
        
        mask = (chunk["Date"] >= start_date) & (chunk["Date"] <= end_date) & (chunk["Stock Name"] == request.stock)
        filtered = chunk.loc[mask]
        
        rows = []
        for _, row in filtered.iterrows():
            if pd.isna(row["Date"]):
                continue
            
            text = str(row["Tweet"])
            tweet_id = hashlib.sha256((text + str(row["Date"])).encode()).hexdigest()
            
            # Sentiment to be added 
            sentiment = None
            confidence = None
            if "Sentiment" in row and pd.notna(row["Sentiment"]):
                sentiment = int(row["Sentiment"])
                confidence = float(row.get("Confidence", 0.0)) if "Confidence" in row else None

            rows.append({
                "ticker": str(row["Stock Name"]),
                "tweet_id": tweet_id,
                "text": text,
                "date": row["Date"].isoformat(),      # Full ISO timestamp for Tweet property
                "date_only": row["Date"].strftime("%Y-%m-%d"), # YYYY-MM-DD for TradingDay matching
                "hashtags": _extract_hashtags(text),
                "sentiment": sentiment,
                "confidence": confidence
            })
            
        if rows:
            neo4j_service.run_query(tweet_cypher, {"rows": rows})
            tweet_records += len(rows)

    return {
        "status": "success",
        "stock": request.stock,
        "prices_synced": stock_records,
        "tweets_imported": tweet_records,
        "schema_notes": "Simplified: User, Topic, NewsEvent labels were skipped."
    }
