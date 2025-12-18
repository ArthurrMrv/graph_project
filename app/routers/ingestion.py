from fastapi import APIRouter
from typing import Optional, List
import pandas as pd
import hashlib
import re
import os

from app.models import StockSyncRequest, SocialImportRequest
from app.services.neo4j_service import neo4j_service

router = APIRouter()

STOCKS_CSV = "data/Stock Tweets Sentiment Analysis/stock_yfinance_data.csv"
SOCIAL_CSV = "data/Stock Tweets Sentiment Analysis/stock_tweets.csv"


def _extract_hashtags(text: str) -> List[str]:
    return re.findall(r"#(\w+)", text or "")


@router.post("/stocks/sync", tags=["Stocks"])
async def sync_stocks(request: StockSyncRequest):
    """
    Batch insert price data for a ticker within a date window using UNWIND.
    """
    neo4j_service.create_constraints()
    
    if not os.path.exists(STOCKS_CSV):
        return {"status": "error", "message": "Data file not found"}

    default_start = pd.to_datetime("2021-09-30")
    default_end = pd.to_datetime("2022-09-30")
    # Validate date strings - check if they're not None, not empty, and not the literal "string"
    start_date = pd.to_datetime(request.start_date) if (request.start_date and request.start_date.strip() and request.start_date != "string") else default_start
    end_date = pd.to_datetime(request.end_date) if (request.end_date and request.end_date.strip() and request.end_date != "string") else default_end
    chunk_size = max(100, min(request.chunk_size, 5000))

    cypher = """
    UNWIND $rows AS row
    MERGE (s:Stock {ticker: row.ticker})
    MERGE (d:TradingDay {date: row.date})
    MERGE (s)-[:PRICE_ON {close: row.close, volume: row.volume}]->(d)
    """

    records_processed = 0
    for chunk in pd.read_csv(STOCKS_CSV, chunksize=chunk_size):
        chunk["Date"] = pd.to_datetime(chunk["Date"], errors="coerce")
        mask = (chunk["Date"] >= start_date) & (chunk["Date"] <= end_date) & (chunk["Stock Name"] == request.stock)
        filtered = chunk.loc[mask]

        rows = []
        for _, row in filtered.iterrows():
            if pd.isna(row["Date"]):
                continue
            rows.append(
                {
                    "ticker": str(row["Stock Name"]),
                    "date": row["Date"].strftime("%Y-%m-%d"),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                }
            )

        if rows:
            neo4j_service.run_query(cypher, {"rows": rows})
            records_processed += len(rows)
        
    return {"status": "success", "records_synced": records_processed, "ticker": request.stock}


@router.post("/social/import", tags=["Social"])
async def import_social(request: SocialImportRequest):
    """
    Batch insert tweets/posts for a ticker within a date window using UNWIND.
    Supports optional columns: User, Topics (pipe-separated), Sentiment, Confidence, EventId.
    """
    neo4j_service.create_constraints()
    
    if not os.path.exists(SOCIAL_CSV):
        return {"status": "error", "message": "Data file not found"}

    default_start = pd.to_datetime("2021-09-30")
    default_end = pd.to_datetime("2022-09-30")
    # Validate date strings - check if they're not None, not empty, and not the literal "string"
    start_date = pd.to_datetime(request.start_date) if (request.start_date and request.start_date.strip() and request.start_date != "string") else default_start
    end_date = pd.to_datetime(request.end_date) if (request.end_date and request.end_date.strip() and request.end_date != "string") else default_end
    chunk_size = max(100, min(request.chunk_size, 5000))

    cypher = """
    UNWIND $rows AS row
    MERGE (s:Stock {ticker: row.ticker})
    MERGE (t:Tweet {id: row.tweet_id})
    SET t.text = row.text, t.date = row.date
    FOREACH (_ IN CASE WHEN row.sentiment IS NULL THEN [] ELSE [1] END |
        SET t.sentiment = row.sentiment, t.confidence = row.confidence)
    MERGE (t)-[:DISCUSSES]->(s)
    FOREACH (tag IN row.hashtags |
        MERGE (h:HashTag {tag: tag})
        MERGE (t)-[:TAGGED_WITH]->(h))
    FOREACH (usr IN CASE WHEN row.user_id IS NULL THEN [] ELSE [row.user_id] END |
        MERGE (u:User {user_id: usr})
        MERGE (t)-[:POSTED_BY]->(u))
    FOREACH (topic IN row.topics |
        MERGE (tp:Topic {name: topic})
        MERGE (t)-[:MENTIONS]->(tp))
    FOREACH (ev IN CASE WHEN row.event_id IS NULL THEN [] ELSE [row.event_id] END |
        MERGE (n:NewsEvent {event_id: ev})
        MERGE (t)-[:REFERENCES]->(n))
    """

    records_processed = 0
    for chunk in pd.read_csv(SOCIAL_CSV, chunksize=chunk_size, on_bad_lines="skip"):
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

            topics: List[str] = []
            if "Topics" in row and isinstance(row["Topics"], str):
                topics = [t.strip() for t in row["Topics"].split("|") if t.strip()]

            sentiment = None
            confidence = None
            if "Sentiment" in row and pd.notna(row["Sentiment"]):
                sentiment = int(row["Sentiment"])
                confidence = float(row.get("Confidence", 0.0)) if "Confidence" in row else None

            user_id = None
            if "User" in row and pd.notna(row["User"]):
                user_id = str(row["User"])

            event_id = None
            if "EventId" in row and pd.notna(row["EventId"]):
                event_id = str(row["EventId"])

            rows.append(
                {
                    "ticker": str(row["Stock Name"]),
                    "tweet_id": tweet_id,
                    "text": text,
                    "date": row["Date"].isoformat(),
                    "hashtags": _extract_hashtags(text),
                    "user_id": user_id,
                    "topics": topics,
                    "sentiment": sentiment,
                    "confidence": confidence,
                    "event_id": event_id,
                }
            )

        if rows:
            neo4j_service.run_query(cypher, {"rows": rows})
            records_processed += len(rows)

    return {
        "status": "success",
        "records_imported": records_processed,
        "ticker": request.stock,
        "start_date": start_date.date().isoformat(),
        "end_date": end_date.date().isoformat(),
    }


