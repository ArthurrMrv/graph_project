import pytest
import statistics
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def mock_neo4j():
    with patch("app.routers.quantitative.neo4j_service.run_query") as mock:
        yield mock

def test_sentiment_price_correlation_valid(mock_neo4j):
    # Mock data for 3 days to allow correlation calculation
    mock_neo4j.return_value = [
        {"date": "2023-01-01", "close_price": 100.0, "trading_volume": 1000, "avg_sentiment": 0.5, "tweet_count": 10},
        {"date": "2023-01-02", "close_price": 110.0, "trading_volume": 1100, "avg_sentiment": 0.8, "tweet_count": 15},
        {"date": "2023-01-03", "close_price": 120.0, "trading_volume": 1200, "avg_sentiment": 0.9, "tweet_count": 20}
    ]
    
    response = client.get("/api/correlation/sentiment-price/TSLA")
    assert response.status_code == 200
    data = response.json()
    assert data["stock"] == "TSLA"
    assert data["correlation_coefficient"] is not None
    assert len(data["daily_data"]) == 3

def test_sentiment_price_correlation_insufficient_data(mock_neo4j):
    mock_neo4j.return_value = [
        {"date": "2023-01-01", "close_price": 100.0, "trading_volume": 1000, "avg_sentiment": 0.5, "tweet_count": 10}
    ]
    response = client.get("/api/correlation/sentiment-price/TSLA")
    assert response.status_code == 200
    data = response.json()
    assert data["correlation_coefficient"] is None
    assert data["interpretation"] == "Insufficient data"

def test_trending_stocks(mock_neo4j):
    mock_neo4j.return_value = [
        {"ticker": "TSLA", "tweet_volume": 100, "avg_sentiment": 0.7, "sentiment_count": 80, "trend_score": 150.0},
        {"ticker": "AAPL", "tweet_volume": 50, "avg_sentiment": 0.6, "sentiment_count": 40, "trend_score": 75.0}
    ]
    
    response = client.get("/api/trending/stocks?window=daily")
    assert response.status_code == 200
    data = response.json()
    assert data["window"] == "daily"
    assert len(data["trending_stocks"]) == 2

def test_top_influencers(mock_neo4j):
    mock_neo4j.return_value = [
        {
            "user_id": "user1", 
            "tweet_count": 20, 
            "avg_sentiment": 0.8, 
            "sentiment_count": 15, 
            "influence_count": 100, 
            "influence_score": 50.0
        }
    ]
    
    response = client.get("/api/influencers/TSLA")
    assert response.status_code == 200
    data = response.json()
    assert data["stock"] == "TSLA"
    assert data["top_influencers"][0]["user_id"] == "user1"

def test_sentiment_based_prediction_bullish(mock_neo4j):
    mock_neo4j.return_value = [
        {"avg_sentiment": 0.8, "tweet_count": 50, "sentiment_volatility": 0.1}
    ]
    
    response = client.get("/api/prediction/sentiment-based/TSLA")
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"] == "bullish"
    assert data["confidence"] > 0.5

def test_sentiment_based_prediction_bearish(mock_neo4j):
    mock_neo4j.return_value = [
        {"avg_sentiment": 0.2, "tweet_count": 50, "sentiment_volatility": 0.1}
    ]
    
    response = client.get("/api/prediction/sentiment-based/TSLA")
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"] == "bearish"

def test_sentiment_based_prediction_neutral(mock_neo4j):
    mock_neo4j.return_value = [
        {"avg_sentiment": 0.5, "tweet_count": 50, "sentiment_volatility": 0.1}
    ]
    
    response = client.get("/api/prediction/sentiment-based/TSLA")
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"] == "neutral"

def test_sentiment_based_prediction_no_data(mock_neo4j):
    mock_neo4j.return_value = []
    
    response = client.get("/api/prediction/sentiment-based/TSLA")
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"] == "insufficient_data"

def test_social_driven_volatility(mock_neo4j):
    mock_neo4j.return_value = [
        {
            "ticker": "TSLA", 
            "tweet_count": 100, 
            "avg_sentiment": 0.5, 
            "sentiment_std": 0.4, 
            "volatility_score": 40.0
        }
    ]
    
    response = client.get("/api/volatility/social-driven")
    assert response.status_code == 200
    data = response.json()
    assert len(data["volatile_stocks"]) == 1
    assert "high volatility" in data["volatile_stocks"][0]["interpretation"].lower()
