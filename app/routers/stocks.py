from fastapi import APIRouter
from app.models import StockSyncRequest
from app.services.neo4j_service import neo4j_service
import pandas as pd
import os

router = APIRouter()

DATA_PATH = "data/Stock Tweets Sentiment Analysis/stock_yfinance_data.csv"

@router.post("/sync")
async def sync_stocks(request: StockSyncRequest):
    # Ensure constraints exist
    neo4j_service.create_constraints()
    
    if not os.path.exists(DATA_PATH):
        return {"status": "error", "message": "Data file not found"}

    df = pd.read_csv(DATA_PATH)
    
    # Filter for User defined range and Stock
    # Date format in CSV is likely YYYY-MM-DD based on head command
    df['Date'] = pd.to_datetime(df['Date'])
    start_date = pd.to_datetime("2021-09-30")
    end_date = pd.to_datetime("2022-09-30")
    
    mask = (df['Date'] >= start_date) & (df['Date'] <= end_date) & (df['Stock Name'] == request.stock)
    filtered_df = df.loc[mask]
    
    records_processed = 0
    query = """
    MERGE (s:Stock {ticker: $ticker})
    MERGE (d:TradingDay {date: $date})
    MERGE (s)-[:PRICE_ON {close: $close, volume: $volume}]->(d)
    """
    
    # Batch processing could be better but for MVP row-by-row or small batches is fine
    # For speed let's just loop.
    for _, row in filtered_df.iterrows():
        params = {
            "ticker": row['Stock Name'],
            "date": row['Date'].strftime("%Y-%m-%d"),
            "close": float(row['Close']),
            "volume": int(row['Volume'])
        }
        neo4j_service.run_query(query, params)
        records_processed += 1
        
    return {"status": "success", "records_synced": records_processed}
