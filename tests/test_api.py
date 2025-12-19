import importlib
import pytest
from unittest.mock import MagicMock, AsyncMock
import pandas as pd
from fastapi.testclient import TestClient

import app.routers.pipeline as pipeline_router
import app.routers.sentiment as sentiment_router
import app.routers.analytics as analytics_router


def run_query_mock(query, params=None):
    """Simple mock for Neo4j queries"""
    return []


def setup_client(monkeypatch):
    # Mock Neo4j service for all routers
    mock_neo4j = MagicMock()
    mock_neo4j.run_query.side_effect = run_query_mock
    mock_neo4j.create_constraints.return_value = None

    monkeypatch.setattr(pipeline_router, "neo4j_service", mock_neo4j)
    monkeypatch.setattr(analytics_router, "neo4j_service", mock_neo4j)

    # Mock Sentiment Workflow to avoid real AI calls and Async issues
    mock_workflow = AsyncMock(return_value={"status": "success", "tweets_processed": 0})
    monkeypatch.setattr(pipeline_router, "process_missing_sentiments", mock_workflow)

    # Mock HuggingFace service
    mock_hf_instance = MagicMock()
    mock_hf_instance.analyze_sentiment.return_value = {"sentiment": 1, "confidence": 0.9}
    mock_get_hf_service = MagicMock(return_value=mock_hf_instance)
    monkeypatch.setattr(sentiment_router, "get_hf_service", mock_get_hf_service)

    # Reload main to apply patches
    import app.main as main
    importlib.reload(main)
    return TestClient(main.app)


def test_health_check(monkeypatch):
    client = setup_client(monkeypatch)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Stock Sentiment Graph API is running"


def test_sentiment_analyze(monkeypatch):
    client = setup_client(monkeypatch)
    payload = {"text": "Bullish on TSLA", "api_key": "dummy"}
    resp = client.post("/api/sentiment/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sentiment"] == 1
    assert data["confidence"] == 0.9


def test_pipeline_dataset_to_graph(monkeypatch, tmp_path):
    # Setup dummy data
    prices = pd.DataFrame([{"Date": "2021-09-30", "Stock Name": "TSLA", "Open": 240.0, "High": 255.0, "Low": 235.0, "Close": 250.0, "Volume": 1000}])
    social = pd.DataFrame([{"Date": "2021-09-30", "Tweet": "TSLA moon #EV", "Stock Name": "TSLA"}])
    
    prices_path = tmp_path / "prices.csv"
    social_path = tmp_path / "social.csv"
    prices.to_csv(prices_path, index=False)
    social.to_csv(social_path, index=False)

    # Patch paths in pipeline router
    monkeypatch.setattr(pipeline_router, "STOCKS_CSV", str(prices_path))
    monkeypatch.setattr(pipeline_router, "SOCIAL_CSV", str(social_path))

    client = setup_client(monkeypatch)
    
    payload = {
        "stock": "TSLA",
        "start_date": "2021-09-30",
        "end_date": "2021-09-30"
    }
    
    resp = client.post("/api/pipeline/dataset_to_graph", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["stock"] == "TSLA"
    assert data["prices_synced"] > 0
    assert data["tweets_imported"] > 0

@pytest.mark.asyncio
async def test_sentiment_workflow(monkeypatch):
    from app.services.sentiment_workflow import process_missing_sentiments
    
    # Mock Neo4j to return 2 tweets
    mock_neo4j = MagicMock()
    mock_neo4j.run_query.side_effect = [
        [{"id": "t1", "text": "Good"}, {"id": "t2", "text": "Bad"}], # Fetch
        [{"updated": 2}] # Update
    ]
    monkeypatch.setattr("app.services.sentiment_workflow.neo4j_service", mock_neo4j)
    
    # Mock HF Service
    mock_hf = MagicMock()
    mock_hf.batch_analyze_sentiment.return_value = [
        {"sentiment": 1, "confidence": 0.9},
        {"sentiment": -1, "confidence": 0.8}
    ]
    monkeypatch.setattr("app.services.sentiment_workflow.get_hf_service", lambda api_key=None: mock_hf)
    
    result = await process_missing_sentiments(stock="TSLA", batch_size=10)
    
    assert result["status"] == "success"
    assert result["tweets_updated"] == 2
    assert mock_neo4j.run_query.call_count == 2

