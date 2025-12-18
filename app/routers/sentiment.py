from fastapi import APIRouter, HTTPException
from app.models import SentimentRequest, SentimentResponse, SyncSentimentsRequest, SyncSentimentsResponse
from app.services.huggingface_service import get_hf_service
from app.services.neo4j_service import neo4j_service
from app.config import settings
from typing import List, Dict, Any
import time

router = APIRouter()

@router.post("/analyze", response_model=SentimentResponse)
async def analyze_sentiment(request: SentimentRequest):
    # Use api_key from request if provided, otherwise use HF_TOKEN from .env
    # Pass None to get_hf_service if using env token (to enable caching)
    api_key = request.api_key if request.api_key is not None else None
    
    # Check if we have a token (either from request or env)
    if not api_key and not settings.HF_TOKEN:
        raise HTTPException(
            status_code=400,
            detail="HF_TOKEN must be provided either in request body (api_key) or in .env file (HF_TOKEN)"
        )
    
    try:
        # Pass None if using env token (enables caching), otherwise pass the provided api_key
        hf_service = get_hf_service(api_key=api_key)
        result = hf_service.analyze_sentiment(request.text)
        return SentimentResponse(
            sentiment=result.get("sentiment", 0),
            confidence=result.get("confidence", 0.0)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing sentiment: {str(e)}")


@router.post("/syncSentiments", response_model=SyncSentimentsResponse)
async def sync_sentiments(request: SyncSentimentsRequest):
    """
    Automatically analyze sentiment for tweets in Neo4j and update them with sentiment scores.
    Processes tweets in batches and supports optional filtering by stock, date range, and limit.
    """
    # Use api_key from request if provided, otherwise use HF_TOKEN from .env
    api_key = request.api_key if request.api_key is not None else None
    
    # Check if we have a token (either from request or env)
    if not api_key and not settings.HF_TOKEN:
        raise HTTPException(
            status_code=400,
            detail="HF_TOKEN must be provided either in request body (api_key) or in .env file (HF_TOKEN)"
        )
    
    try:
        # Get Hugging Face service
        hf_service = get_hf_service(api_key=api_key)
        
        # Build Cypher query to fetch tweets
        # Note: Using IS NULL to check for missing/null sentiment property
        # Neo4j may show warnings if property doesn't exist in schema, but query will work
        where_conditions = ["(t.sentiment IS NULL OR $overwrite = true)"]
        params = {"overwrite": request.overwrite}
        
        # Build the MATCH clause
        if request.stock:
            # If stock filter is provided, match through the relationship
            cypher_fetch = "MATCH (t:Tweet)-[:DISCUSSES]->(s:Stock {ticker: $stock})"
            params["stock"] = request.stock
        else:
            # No stock filter - match all tweets
            cypher_fetch = "MATCH (t:Tweet)"
        
        # Add date filters if provided
        if request.start_date:
            where_conditions.append("t.date >= $start_date")
            params["start_date"] = request.start_date
        
        if request.end_date:
            where_conditions.append("t.date <= $end_date")
            params["end_date"] = request.end_date
        
        # Build WHERE clause
        cypher_fetch += "\nWHERE " + " AND ".join(where_conditions)
        
        # Add RETURN clause
        cypher_fetch += "\nRETURN t.id AS id, t.text AS text"
        
        # Add LIMIT if provided
        if request.limit:
            cypher_fetch += "\nLIMIT $limit"
            params["limit"] = request.limit
        
        # Fetch tweets from Neo4j
        try:
            tweets = neo4j_service.run_query(cypher_fetch, params)
        except Exception as e:
            # If query fails (e.g., database is empty or schema issues), return empty result
            print(f"Error fetching tweets from Neo4j: {e}")
            return SyncSentimentsResponse(
                tweets_processed=0,
                tweets_updated=0,
                errors=0,
                stock=request.stock,
                date_range={"start": request.start_date, "end": request.end_date} if request.start_date or request.end_date else None
            )
        
        if not tweets:
            return SyncSentimentsResponse(
                tweets_processed=0,
                tweets_updated=0,
                errors=0,
                stock=request.stock,
                date_range={"start": request.start_date, "end": request.end_date} if request.start_date or request.end_date else None
            )
        
        # Process tweets in batches using batch sentiment analysis
        tweets_processed = 0
        tweets_updated = 0
        errors = 0
        
        batch_size = max(1, min(request.batch_size, 100))  # Ensure batch_size is between 1 and 100
        
        for i in range(0, len(tweets), batch_size):
            batch = tweets[i:i + batch_size]
            
            # Prepare texts and track tweet IDs
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
                
                # Prepare batch updates for Neo4j
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
                
                # Small delay between batches to avoid rate limiting (only if batch processing worked)
                if len(results) == len(texts_to_analyze):
                    time.sleep(0.1)
                else:
                    # If batch processing failed and fell back to individual, add longer delay
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"Error in batch sentiment analysis: {e}")
                # Fall back to individual processing for this batch
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
                        
                        # Update Neo4j individually
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
        
        # Build response
        date_range = None
        if request.start_date or request.end_date:
            date_range = {
                "start": request.start_date,
                "end": request.end_date
            }
        
        return SyncSentimentsResponse(
            tweets_processed=tweets_processed,
            tweets_updated=tweets_updated,
            errors=errors,
            stock=request.stock,
            date_range=date_range
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing sentiments: {str(e)}")
