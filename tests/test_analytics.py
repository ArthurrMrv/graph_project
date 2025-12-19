import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def mock_neo4j():
    with patch("app.routers.analytics.neo4j_service.run_query") as mock:
        yield mock

def test_network_influence(mock_neo4j):
    # Mock data return
    mock_neo4j.return_value = [
        {"user_id": "user1", "out_deg": 10},
        {"user_id": "user2", "out_deg": 5}
    ]
    
    response = client.get("/api/analytics/network/influence/test_user")
    assert response.status_code == 200
    data = response.json()
    assert data["user"] == "test_user"
    assert len(data["top_influencers"]) == 2
    assert data["top_influencers"][0]["user_id"] == "user1"

def test_cascade_sentiment(mock_neo4j):
    mock_neo4j.return_value = [
        {"n": 5, "avg_sentiment": 0.8, "avg_confidence": 0.9}
    ]
    
    response = client.get("/api/analytics/cascade/sentiment/tweet1")
    assert response.status_code == 200
    data = response.json()
    assert data["tweet_id"] == "tweet1"
    assert data["stats"]["n"] == 5

def test_clusters_stocks(mock_neo4j):
    mock_neo4j.return_value = [
        {"a": "TSLA", "b": "AAPL", "score": 100}
    ]
    
    response = client.get("/api/analytics/clusters/stocks")
    assert response.status_code == 200
    data = response.json()
    assert len(data["clusters"]) == 1
    assert data["clusters"][0]["a"] == "TSLA"

def test_timeline_events(mock_neo4j):
    mock_neo4j.return_value = [
        {"event_id": "ev1", "title": "Earnings", "published_at": "2023-01-01", "mentions": 10}
    ]
    
    response = client.get("/api/analytics/timeline/events/TSLA")
    assert response.status_code == 200
    data = response.json()
    assert data["stock"] == "TSLA"
    assert data["events"][0]["title"] == "Earnings"

def test_gds_global_influence(mock_neo4j):
    mock_neo4j.return_value = [
        {"user_id": "influencer1", "score": 0.95}
    ]
    
    response = client.get("/api/analytics/gds/influence/global")
    assert response.status_code == 200
    data = response.json()
    assert data["algorithm"] == "gds.pageRank"
    assert data["top_users"][0]["user_id"] == "influencer1"

def test_gds_stock_communities(mock_neo4j):
    # Mock for freshness drop and projection
    mock_neo4j.return_value = [
        {"ticker": "TSLA", "communityId": 1},
        {"ticker": "AAPL", "communityId": 1}
    ]
    
    response = client.get("/api/analytics/gds/communities/stocks")
    assert response.status_code == 200
    data = response.json()
    assert data["algorithm"] == "gds.louvain"
    assert len(data["stocks"]) == 2

def test_gds_stock_similarity(mock_neo4j):
    mock_neo4j.return_value = [
        {"similar_ticker": "NIO", "similarity": 0.8}
    ]
    
    response = client.get("/api/analytics/gds/similarity/stocks/TSLA")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "TSLA"
    assert data["similar"][0]["similar_ticker"] == "NIO"

def test_stock_sentiment_correlation(mock_neo4j):
    mock_neo4j.return_value = [
        {"date": "2023-01-01", "close_price": 100, "tweet_count": 50, "avg_sentiment": 0.6}
    ]
    
    response = client.get("/api/analytics/stock-sentiment/TSLA")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "TSLA"
    assert len(data["data"]) == 1
    assert data["data"][0]["price"] == 100

def test_stock_sentiment_correlation_error(mock_neo4j):
    mock_neo4j.side_effect = Exception("Neo4j Error")
    
    response = client.get("/api/analytics/stock-sentiment/TSLA")
    assert response.status_code == 200 # App handles exception and returns dict with error
    assert "error" in response.json()
