import sys
from unittest.mock import MagicMock
import pandas as pd
import sys
import os

# Mock modules before importing app
sys.modules["neo4j"] = MagicMock()
sys.modules["google.generativeai"] = MagicMock()

from fastapi.testclient import TestClient
from app.main import app

def test_api():
    client = TestClient(app)
    
    print("Testing /api/sentiment/analyze")
    # Mock Gemini response
    with sys.modules["app.routers.sentiment"].gemini_service as mock_gemini:
        mock_gemini.analyze_sentiment.return_value = {"sentiment": 1, "confidence": 0.95}
        
        response = client.post(
            "/api/sentiment/analyze", 
            json={"text": "Tesla is great!", "api_key": "dummy"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 200
        assert response.json()["sentiment"] == 1

    print("\nTesting /api/stocks/sync (dry run)")
    # Mock Neo4j run_query
    with sys.modules["app.routers.stocks"].neo4j_service as mock_neo4j:
        response = client.post("/api/stocks/sync", json={"stock": "TSLA"})
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        # We expect success if file exists, else error. 
        # Since we are in the real env, file should exist.
        if response.status_code == 200:
             print("Success! Records synced (mocked DB write)")
        else:
             print("Failed (expected if file missing or other issue)")

    print("\nTesting /api/social/import (dry run)")
    with sys.modules["app.routers.social"].neo4j_service as mock_neo4j:
        response = client.post("/api/social/import", json={"stock": "TSLA"})
        print(f"Status: {response.status_code}")
        # Note: This might take a while if it actually parses the huge CSV.
        # But we mocked the DB write, so it's just pandas reading.
        # It might be too slow for this script if the file is 18MB, but 18MB is small for Pandas.
        print(f"Response: {response.json()}")
        if response.status_code == 200:
             print("Success! Records imported (mocked DB write)")
        else:
             print("Failed")

if __name__ == "__main__":
    test_api()
