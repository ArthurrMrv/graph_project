import time
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
            detail="HF_TOKEN must be provided either in request body (api_key) or in .env file (HF_TOKEN)",
        )

    try:
        # Pass None if using env token (enables caching), otherwise pass the provided api_key
        hf_service = get_hf_service(api_key=api_key)
        result = hf_service.analyze_sentiment(request.text)
        return SentimentResponse(sentiment=result.get("sentiment", 0), confidence=result.get("confidence", 0.0))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing sentiment: {str(e)}") from e



