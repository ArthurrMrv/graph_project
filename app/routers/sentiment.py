from fastapi import APIRouter, HTTPException
from app.models import SentimentRequest, SentimentResponse
from app.services.gemini_service import gemini_service

router = APIRouter()

@router.post("/analyze", response_model=SentimentResponse)
async def analyze_sentiment(request: SentimentRequest):
    result = gemini_service.analyze_sentiment(request.text, request.api_key)
    return SentimentResponse(
        sentiment=result.get("sentiment", 0),
        confidence=result.get("confidence", 0.0)
    )
