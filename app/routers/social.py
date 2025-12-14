from fastapi import APIRouter
from app.models import SocialImportRequest
from app.services.neo4j_service import neo4j_service
import pandas as pd
import hashlib
import re
import os

router = APIRouter()

DATA_PATH = "data/Stock Tweets Sentiment Analysis/stock_tweets.csv"

def extract_hashtags(text):
    return re.findall(r"#(\w+)", text)

@router.post("/import")
async def import_social(request: SocialImportRequest):
    neo4j_service.create_constraints()
    
    if not os.path.exists(DATA_PATH):
        return {"status": "error", "message": "Data file not found"}

    # Read CSV
    # Using on_bad_lines='skip' just in case
    df = pd.read_csv(DATA_PATH, on_bad_lines='skip')
    
    # Rename columns to standard names if needed, based on head: 
    # Date, Tweet, Stock Name, Company Name
    
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce') # Handle potential mixed formats
    # Note: the Date in tweets includes time, but for fitering we care about day
    
    # Filter
    start_date = pd.to_datetime("2021-09-30").tz_localize(None)
    end_date = pd.to_datetime("2022-09-30").tz_localize(None)
    
    # Ensure df date is naive or comparable
    df['Date_Day'] = df['Date'].dt.tz_localize(None) # Remove timezone if present

    mask = (df['Date_Day'] >= start_date) & (df['Date_Day'] <= end_date) & (df['Stock Name'] == request.stock)
    filtered_df = df.loc[mask]
    
    query = """
    MERGE (s:Stock {ticker: $ticker})
    MERGE (t:Tweet {id: $tweet_id})
    SET t.text = $text, t.date = $date
    MERGE (t)-[:DISCUSSES]->(s)
    WITH t
    UNWIND $hashtags AS tag
    MERGE (h:HashTag {tag: tag})
    MERGE (t)-[:TAGGED_WITH]->(h)
    """
    
    records_processed = 0
    for _, row in filtered_df.iterrows():
        text = str(row['Tweet'])
        # Create a deterministic ID since none provided
        tweet_id = hashlib.sha256((text + str(row['Date'])).encode()).hexdigest()
        
        hashtags = extract_hashtags(text)
        
        params = {
            "ticker": row['Stock Name'],
            "tweet_id": tweet_id,
            "text": text,
            "date": row['Date'].isoformat(),
            "hashtags": hashtags
        }
        
        neo4j_service.run_query(query, params)
        records_processed += 1

    return {"status": "success", "records_imported": records_processed}
