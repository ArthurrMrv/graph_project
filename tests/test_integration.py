import os
import pytest
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app
from app.services.neo4j_service import neo4j_service
import app.routers.ingestion as ingestion

# Connect to the test database explicitly if needed, 
# but relying on env vars set by Makefile is better.
client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_db():
    # Clean DB before each test
    neo4j_service.run_query("MATCH (n) DETACH DELETE n")
    # Ensure constraints exist
    neo4j_service.create_constraints()
    yield
    # Optional: Clean after

def test_health_integration():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Stock Sentiment Graph API is running"

def test_full_ingestion_flow(tmp_path, monkeypatch):
    """
    Test syncing a stock and importing tweets, then verifying the graph structure.
    """
    # 1. Prepare Mock Data
    prices = pd.DataFrame([
        {"Date": "2023-01-01", "Stock Name": "TEST_CO", "Close": 100.0, "Volume": 500},
        {"Date": "2023-01-02", "Stock Name": "TEST_CO", "Close": 105.0, "Volume": 600},
    ])
    prices_path = tmp_path / "test_prices.csv"
    prices.to_csv(prices_path, index=False)

    social = pd.DataFrame([
        {
            "Date": "2023-01-01", 
            "Tweet": "TEST_CO is great #bullish", 
            "Stock Name": "TEST_CO",
            "User": "trader_joe",
            "Topics": "Finance",
            "Sentiment": 0.9,
            "Confidence": 0.99,
            "EventId": "evt_1"
        }
    ])
    social_path = tmp_path / "test_tweets.csv"
    social.to_csv(social_path, index=False)

    # 2. Patch the CSV paths in the ingestion module so it reads our temp files
    # We DO NOT mock neo4j_service, we want the real one.
    monkeypatch.setattr(ingestion, "STOCKS_CSV", str(prices_path))
    monkeypatch.setattr(ingestion, "SOCIAL_CSV", str(social_path))

    # 3. Call Sync Stocks Endpoint
    resp = client.post("/api/stocks/sync", json={
        "stock": "TEST_CO",
        "start_date": "2023-01-01",
        "end_date": "2023-01-02"
    })
    assert resp.status_code == 200
    assert resp.json()["records_synced"] == 2

    # 4. Call Import Social Endpoint
    resp = client.post("/api/social/import", json={
        "stock": "TEST_CO",
        "start_date": "2023-01-01",
        "end_date": "2023-01-02"
    })
    assert resp.status_code == 200
    assert resp.json()["records_imported"] == 1

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
        RETURN t.text as text, t.sentiment as sentiment
    """)
    assert len(results) == 1
    assert results[0]["text"] == "TEST_CO is great #bullish"
    assert results[0]["sentiment"] == 0.9
