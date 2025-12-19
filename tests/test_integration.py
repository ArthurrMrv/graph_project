import os
import pytest
import pandas as pd
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.neo4j_service import neo4j_service
import app.routers.pipeline as pipeline

# Connect to the test database explicitly if needed, 
# but relying on env vars set by Makefile is better.
client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_db():
    # Clean DB before each test
    try:
        neo4j_service.run_query("MATCH (n) DETACH DELETE n")
        # Ensure constraints exist
        neo4j_service.create_constraints()
    except Exception as e:
        pytest.skip(f"Neo4j not available for integration tests: {e}")
    yield

def test_health_integration():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Stock Sentiment Graph API is running"

def test_full_pipeline_flow(tmp_path, monkeypatch):
    """
    Test the consolidated pipeline: syncing stock and importing tweets in one call.
    """
    # 1. Prepare Dummy Data
    prices = pd.DataFrame([
        {"Date": "2023-01-01", "Stock Name": "TEST_CO", "Open": 99.0, "High": 101.0, "Low": 98.0, "Close": 100.0, "Volume": 500},
        {"Date": "2023-01-02", "Stock Name": "TEST_CO", "Open": 100.0, "High": 106.0, "Low": 99.0, "Close": 105.0, "Volume": 600},
    ])
    prices_path = tmp_path / "test_prices.csv"
    prices.to_csv(prices_path, index=False)

    social = pd.DataFrame([
        {
            "Date": "2023-01-01", 
            "Tweet": "TEST_CO is great #bullish", 
            "Stock Name": "TEST_CO"
        }
    ])
    social_path = tmp_path / "test_tweets.csv"
    social.to_csv(social_path, index=False)

    # 2. Patch the CSV paths
    monkeypatch.setattr(pipeline, "STOCKS_CSV", str(prices_path))
    monkeypatch.setattr(pipeline, "SOCIAL_CSV", str(social_path))
    
    # 3. Mock the background sentiment workflow to avoid external API calls
    mock_workflow = AsyncMock(return_value={"status": "success", "tweets_processed": 0})
    monkeypatch.setattr(pipeline, "process_missing_sentiments", mock_workflow)

    # 4. Call Unified Pipeline Endpoint
    resp = client.post("/api/pipeline/dataset_to_graph", json={
        "stock": "TEST_CO",
        "start_date": "2023-01-01",
        "end_date": "2023-01-02"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["prices_synced"] == 2
    assert data["tweets_imported"] == 1

    # 5. Verify Data in Neo4j directly
    # check Stock node
    results = neo4j_service.run_query("MATCH (s:Stock {ticker: 'TEST_CO'}) RETURN s")
    assert len(results) == 1
    
    # check Price relationship
    results = neo4j_service.run_query("""
        MATCH (s:Stock {ticker: 'TEST_CO'})-[:PRICE_ON]->(d:TradingDay)
        RETURN count(d) as days
    """)
    assert results[0]["days"] == 2

    # check Tweet and linkage
    results = neo4j_service.run_query("""
        MATCH (t:Tweet)-[:DISCUSSES]->(s:Stock {ticker: 'TEST_CO'})
        RETURN t.text as text
    """)
    assert len(results) == 1
    assert results[0]["text"] == "TEST_CO is great #bullish"

