from typing import Optional, Dict, Any, List
import time
from app.services.huggingface_service import get_hf_service
from app.services.neo4j_service import neo4j_service
from app.config import settings

async def process_missing_sentiments(
    stock: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    batch_size: int = 100,
    overwrite: bool = False,
    limit: Optional[int] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze sentiment for tweets in Neo4j that are missing sentiment scores.
    
    Args:
        stock: Optional stock ticker to filter by.
        start_date: Optional start date (ISO format or YYYY-MM-DD) to filter tweets.
        end_date: Optional end date (ISO format or YYYY-MM-DD) to filter tweets.
        batch_size: Number of tweets to process in one batch.
        overwrite: If True, re-analyze tweets that already have sentiment.
        limit: Max number of tweets to process.
        api_key: Optional HF Token.
        
    Returns:
        Dict with processing stats.
    """
    
    # Get Hugging Face service
    try:
        hf_service = get_hf_service(api_key=api_key)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to initialize HuggingFace service: {str(e)}",
            "tweets_processed": 0
        }
        
    # Build Cypher query to fetch tweets
    where_conditions = ["(t.sentiment IS NULL OR $overwrite = true)"]
    params = {"overwrite": overwrite}
    
    # Build the MATCH clause
    if stock:
        # If stock filter is provided, match through the relationship
        cypher_fetch = "MATCH (t:Tweet)-[:DISCUSSES]->(s:Stock {ticker: $stock})"
        params["stock"] = stock
    else:
        cypher_fetch = "MATCH (t:Tweet)"
    
    # Add date filters if provided
    if start_date:
        where_conditions.append("t.date >= $start_date")
        params["start_date"] = start_date
    
    if end_date:
        # Ensure end_date is inclusive of the full day if no time is specified
        if "T" not in end_date and len(end_date) == 10:
             # It's likely YYYY-MM-DD, append end of day
             params["end_date"] = f"{end_date}T23:59:59"
        else:
             params["end_date"] = end_date
             
        where_conditions.append("t.date <= $end_date")
    
    cypher_fetch += "\nWHERE " + " AND ".join(where_conditions)
    
    cypher_fetch += "\nRETURN t.id AS id, t.text AS text"
    
    if limit:
        cypher_fetch += "\nLIMIT $limit"
        params["limit"] = limit
    
    # Fetch tweets from Neo4j
    try:
        tweets = neo4j_service.run_query(cypher_fetch, params)
    except Exception as e:
        print(f"Error fetching tweets from Neo4j: {e}")
        return {
            "status": "error",
            "message": f"Error fetching tweets: {str(e)}",
            "tweets_processed": 0
        }
    
    if not tweets:
        return {
            "status": "success",
            "message": "No tweets found requiring analysis",
            "tweets_processed": 0,
            "tweets_updated": 0,
            "errors": 0
        }
    
    print(f"DEBUG: Service found {len(tweets)} tweets to process.")
    
    # Process tweets in batches
    tweets_processed = 0
    tweets_updated = 0
    errors = 0
    
    valid_batch_size = max(1, min(batch_size, 100))
    
    for i in range(0, len(tweets), valid_batch_size):
        batch = tweets[i:i + valid_batch_size]
        print(f"DEBUG: Processing batch {i//valid_batch_size + 1}, size {len(batch)}")
        
        texts_to_analyze = []
        tweet_ids = []
        
        for tweet_record in batch:
            tweet_id = tweet_record["id"]
            tweet_text = tweet_record.get("text", "")
            
            if not tweet_text:
                errors += 1
                continue
            
            texts_to_analyze.append(tweet_text)
            tweet_ids.append(tweet_id)
        
        if not texts_to_analyze:
            continue
        
        # Use batch sentiment analysis
        try:
            results = hf_service.batch_analyze_sentiment(texts_to_analyze)
            
            batch_updates = []
            for j, result in enumerate(results):
                if j < len(tweet_ids):
                    sentiment = result.get("sentiment", 0)
                    confidence = result.get("confidence", 0.0)
                    
                    batch_updates.append({
                        "id": tweet_ids[j],
                        "sentiment": sentiment,
                        "confidence": confidence
                    })
                    tweets_processed += 1
            
            # Batch update Neo4j with sentiment scores
            if batch_updates:
                try:
                    cypher_update = """
                    UNWIND $updates AS update
                    MATCH (t:Tweet {id: update.id})
                    SET t.sentiment = update.sentiment,
                        t.confidence = update.confidence
                    RETURN count(t) AS updated
                    """
                    
                    result = neo4j_service.run_query(cypher_update, {"updates": batch_updates})
                    if result and len(result) > 0:
                        tweets_updated += result[0].get("updated", 0)
                    
                except Exception as e:
                    print(f"Error updating Neo4j batch: {e}")
                    errors += len(batch_updates)
            
            if len(results) == len(texts_to_analyze):
                time.sleep(0.01)
            else:
                time.sleep(0.1)
                
        except Exception as e:
            print(f"Error in batch sentiment analysis: {e}")
            for tweet_record in batch:
                tweet_id = tweet_record["id"]
                tweet_text = tweet_record.get("text", "")
                
                if not tweet_text:
                    errors += 1
                    continue
                
                try:
                    result = hf_service.analyze_sentiment(tweet_text)
                    sentiment = result.get("sentiment", 0)
                    confidence = result.get("confidence", 0.0)
                    
                    cypher_update = """
                    MATCH (t:Tweet {id: $id})
                    SET t.sentiment = $sentiment,
                        t.confidence = $confidence
                    RETURN count(t) AS updated
                    """
                    
                    update_result = neo4j_service.run_query(cypher_update, {
                        "id": tweet_id,
                        "sentiment": sentiment,
                        "confidence": confidence
                    })
                    
                    if update_result and len(update_result) > 0 and update_result[0].get("updated", 0) > 0:
                        tweets_updated += 1
                    
                    tweets_processed += 1
                    time.sleep(0.1)
                    
                except Exception as err:
                    print(f"Error analyzing sentiment for tweet {tweet_id}: {err}")
                    errors += 1
                    continue

    return {
        "status": "success",
        "tweets_processed": tweets_processed,
        "tweets_updated": tweets_updated,
        "errors": errors,
        "stock": stock,
        "date_range": {"start": start_date, "end": end_date} if start_date or end_date else None,
        "debug_query": cypher_fetch,
        "debug_params": params
    }
