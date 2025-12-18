import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock
import pandas as pd
from fastapi.testclient import TestClient

import app.routers.ingestion as ingestion
import app.routers.sentiment as sentiment_router
import app.routers.analytics as analytics_router


def make_mock_service(capture_list):
    def run_query(query, params=None):
        if params and "rows" in params:
            capture_list.extend(params["rows"])
        return []

    mock = SimpleNamespace(
        run_query=run_query,
        create_constraints=lambda: None,
    )
    return mock


def setup_client(monkeypatch, capture_list=None):
    capture = capture_list if capture_list is not None else []
    mock_service = make_mock_service(capture)
    # Patch ingestion & analytics to avoid real Neo4j
    monkeypatch.setattr(ingestion, "neo4j_service", mock_service)
    monkeypatch.setattr(analytics_router, "neo4j_service", mock_service)
    # Patch sentiment to avoid real Gemini
    mock_gemini = MagicMock()
    mock_gemini.analyze_sentiment.return_value = {"sentiment": 1, "confidence": 0.9}
    monkeypatch.setattr(sentiment_router, "gemini_service", mock_gemini)
    # Reload main to ensure routers reference patched modules (idempotent)
    import app.main as main
    importlib.reload(main)
    return TestClient(main.app), capture


def test_health_check(monkeypatch):
    client, _ = setup_client(monkeypatch)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Stock Sentiment Graph API is running"


def test_sentiment_analyze(monkeypatch):
    client, _ = setup_client(monkeypatch)
    payload = {"text": "Bullish on TSLA", "api_key": "dummy"}
    resp = client.post("/api/sentiment/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sentiment"] == 1
    assert data["confidence"] == 0.9


def test_ingestion_stocks_sync(monkeypatch, tmp_path):
    # Create a small prices CSV
    prices = pd.DataFrame(
        [
            {"Date": "2021-09-30", "Stock Name": "TSLA", "Close": 250.0, "Volume": 1000},
            {"Date": "2021-10-01", "Stock Name": "AAPL", "Close": 150.0, "Volume": 2000},
        ]
    )
    prices_path = tmp_path / "prices.csv"
    prices.to_csv(prices_path, index=False)

    # Patch the CSV path and mock neo4j
    capture = []
    mock_service = make_mock_service(capture)
    monkeypatch.setattr(ingestion, "neo4j_service", mock_service)
    monkeypatch.setattr(ingestion, "STOCKS_CSV", str(prices_path))

    import app.main as main
    importlib.reload(main)
    client = TestClient(main.app)

    resp = client.post(
        "/api/stocks/sync",
        json={
            "stock": "TSLA",
            "start_date": "2021-09-30",
            "end_date": "2021-09-30",
            "chunk_size": 10,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["records_synced"] == 1
    # Ensure one row was sent to the DB layer
    assert len(capture) == 1


def test_ingestion_social_import(monkeypatch, tmp_path):
    social = pd.DataFrame(
        [
            {
                "Date": "2021-09-30",
                "Tweet": "TSLA to the moon #EV",
                "Stock Name": "TSLA",
                "User": "u1",
                "Topics": "EV|Tech",
                "Sentiment": 1,
                "Confidence": 0.8,
                "EventId": "e1",
            },
            {
                "Date": "2021-10-01",
                "Tweet": "AAPL strong quarter #earnings",
                "Stock Name": "AAPL",
            },
        ]
    )
    social_path = tmp_path / "social.csv"
    social.to_csv(social_path, index=False)

    capture = []
    mock_service = make_mock_service(capture)
    monkeypatch.setattr(ingestion, "neo4j_service", mock_service)
    monkeypatch.setattr(ingestion, "SOCIAL_CSV", str(social_path))

    import app.main as main
    importlib.reload(main)
    client = TestClient(main.app)

    resp = client.post(
        "/api/social/import",
        json={
            "stock": "TSLA",
            "start_date": "2021-09-30",
            "end_date": "2021-09-30",
            "chunk_size": 10,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["records_imported"] == 1
    assert body["ticker"] == "TSLA"
    # Ensure one row was sent to the DB layer
    assert len(capture) == 1

