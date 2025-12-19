import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock
import pandas as pd
from fastapi.testclient import TestClient

import app.routers.pipeline as pipeline_module
import app.routers.sentiment as sentiment_router


def make_mock_service(capture_list):
    """Create a mock Neo4j service that captures queries and rows."""
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
    """Setup test client with mocked services."""
    capture = capture_list if capture_list is not None else []
    mock_service = make_mock_service(capture)
    
    # Patch pipeline to use mock Neo4j service
    monkeypatch.setattr(pipeline_module, "neo4j_service", mock_service)
    
    # Patch sentiment workflow to avoid real processing
    async def mock_sentiment_workflow(*args, **kwargs):
        return {
            "status": "success",
            "tweets_processed": 0,
            "tweets_updated": 0,
            "errors": 0
        }
    monkeypatch.setattr(
        "app.routers.pipeline.process_missing_sentiments",
        mock_sentiment_workflow
    )
    
    # Patch sentiment router to avoid real HuggingFace service
    mock_hf_instance = MagicMock()
    mock_hf_instance.analyze_sentiment.return_value = {"sentiment": 1, "confidence": 0.9}
    mock_get_hf_service = MagicMock(return_value=mock_hf_instance)
    monkeypatch.setattr(sentiment_router, "get_hf_service", mock_get_hf_service)
    
    # Reload main to ensure routers reference patched modules
    import app.main as main
    importlib.reload(main)
    return TestClient(main.app), capture


def test_pipeline_aapl_stock_data(monkeypatch, tmp_path):
    """Test pipeline ingestion for AAPL stock price data."""
    # Create test stock data for AAPL
    prices = pd.DataFrame([
        {
            "Date": "2021-09-30",
            "Stock Name": "AAPL",
            "Open": 145.0,
            "High": 146.5,
            "Low": 144.5,
            "Close": 145.5,
            "Volume": 50000000
        },
        {
            "Date": "2021-10-01",
            "Stock Name": "AAPL",
            "Open": 145.5,
            "High": 147.0,
            "Low": 145.0,
            "Close": 146.0,
            "Volume": 52000000
        },
        {
            "Date": "2021-10-02",
            "Stock Name": "AAPL",
            "Open": 146.0,
            "High": 147.5,
            "Low": 145.5,
            "Close": 147.0,
            "Volume": 51000000
        },
    ])
    prices_path = tmp_path / "prices.csv"
    prices.to_csv(prices_path, index=False)

    # Create empty social data (we'll test that separately)
    social = pd.DataFrame(columns=["Date", "Tweet", "Stock Name"])
    social_path = tmp_path / "social.csv"
    social.to_csv(social_path, index=False)

    # Setup mocks
    capture = []
    mock_service = make_mock_service(capture)
    monkeypatch.setattr(pipeline_module, "neo4j_service", mock_service)
    monkeypatch.setattr(pipeline_module, "STOCKS_CSV", str(prices_path))
    monkeypatch.setattr(pipeline_module, "SOCIAL_CSV", str(social_path))
    
    # Mock sentiment workflow
    async def mock_sentiment_workflow(*args, **kwargs):
        return {
            "status": "success",
            "tweets_processed": 0,
            "tweets_updated": 0,
            "errors": 0
        }
    monkeypatch.setattr(
        "app.routers.pipeline.process_missing_sentiments",
        mock_sentiment_workflow
    )

    import app.main as main
    importlib.reload(main)
    client = TestClient(main.app)

    # Call pipeline endpoint for AAPL
    resp = client.post(
        "/api/pipeline/dataset_to_graph",
        json={
            "stock": "AAPL",
            "start_date": "2021-09-30",
            "end_date": "2021-10-02",
            "chunk_size": 10,
        },
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["stock"] == "AAPL"
    assert data["prices_synced"] == 3
    assert data["tweets_imported"] == 0
    
    # Verify that stock data was captured
    assert len(capture) == 3
    # Check that all captured rows are for AAPL
    for row in capture:
        assert row["ticker"] == "AAPL"
        assert "date" in row
        assert "open" in row
        assert "close" in row
        assert "volume" in row


def test_pipeline_aapl_tweets(monkeypatch, tmp_path):
    """Test pipeline ingestion for AAPL tweet data."""
    # Create test stock data (minimal)
    prices = pd.DataFrame([
        {
            "Date": "2021-09-30",
            "Stock Name": "AAPL",
            "Open": 145.0,
            "High": 146.5,
            "Low": 144.5,
            "Close": 145.5,
            "Volume": 50000000
        },
    ])
    prices_path = tmp_path / "prices.csv"
    prices.to_csv(prices_path, index=False)

    # Create test tweet data for AAPL
    social = pd.DataFrame([
        {
            "Date": "2021-09-30",
            "Tweet": "AAPL is looking strong! #Apple #Tech",
            "Stock Name": "AAPL",
            "User": "tech_analyst",
            "Topics": "Tech|Finance",
            "Sentiment": 0.8,
            "Confidence": 0.85,
            "EventId": "event_1"
        },
        {
            "Date": "2021-09-30",
            "Tweet": "Love my new iPhone! @Apple #AAPL",
            "Stock Name": "AAPL",
            "User": "consumer_user",
            "Sentiment": 0.9,
            "Confidence": 0.92,
        },
        {
            "Date": "2021-10-01",
            "Tweet": "AAPL earnings beat expectations #bullish",
            "Stock Name": "AAPL",
            "Sentiment": 0.7,
            "Confidence": 0.75,
        },
    ])
    social_path = tmp_path / "social.csv"
    social.to_csv(social_path, index=False)

    # Setup mocks
    capture = []
    mock_service = make_mock_service(capture)
    monkeypatch.setattr(pipeline_module, "neo4j_service", mock_service)
    monkeypatch.setattr(pipeline_module, "STOCKS_CSV", str(prices_path))
    monkeypatch.setattr(pipeline_module, "SOCIAL_CSV", str(social_path))
    
    # Mock sentiment workflow
    async def mock_sentiment_workflow(*args, **kwargs):
        return {
            "status": "success",
            "tweets_processed": 0,
            "tweets_updated": 0,
            "errors": 0
        }
    monkeypatch.setattr(
        "app.routers.pipeline.process_missing_sentiments",
        mock_sentiment_workflow
    )

    import app.main as main
    importlib.reload(main)
    client = TestClient(main.app)

    # Call pipeline endpoint for AAPL
    resp = client.post(
        "/api/pipeline/dataset_to_graph",
        json={
            "stock": "AAPL",
            "start_date": "2021-09-30",
            "end_date": "2021-10-01",
            "chunk_size": 10,
        },
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["stock"] == "AAPL"
    assert data["prices_synced"] == 1
    assert data["tweets_imported"] == 3
    
    # Verify that both stock and tweet data were captured
    # We should have 1 stock record + 3 tweet records = 4 total
    assert len(capture) >= 3  # At least 3 tweets
    
    # Check that tweet data includes hashtags and mentions
    tweet_rows = [r for r in capture if "tweet_id" in r]
    assert len(tweet_rows) == 3
    
    # Verify first tweet has hashtags extracted
    first_tweet = tweet_rows[0]
    assert first_tweet["ticker"] == "AAPL"
    assert "hashtags" in first_tweet
    assert len(first_tweet["hashtags"]) > 0  # Should extract #Apple, #Tech


def test_pipeline_aapl_full_flow(monkeypatch, tmp_path):
    """Test complete pipeline flow for AAPL with both stock and tweet data."""
    # Create comprehensive test data for AAPL
    prices = pd.DataFrame([
        {
            "Date": "2021-09-30",
            "Stock Name": "AAPL",
            "Open": 145.0,
            "High": 146.5,
            "Low": 144.5,
            "Close": 145.5,
            "Volume": 50000000
        },
        {
            "Date": "2021-10-01",
            "Stock Name": "AAPL",
            "Open": 145.5,
            "High": 147.0,
            "Low": 145.0,
            "Close": 146.0,
            "Volume": 52000000
        },
    ])
    prices_path = tmp_path / "prices.csv"
    prices.to_csv(prices_path, index=False)

    social = pd.DataFrame([
        {
            "Date": "2021-09-30",
            "Tweet": "AAPL breaking new highs! #Apple #Tech #Investing",
            "Stock Name": "AAPL",
            "User": "market_analyst",
            "Topics": "Tech|Finance|Investing",
            "Sentiment": 0.85,
            "Confidence": 0.90,
            "EventId": "earnings_q3_2021"
        },
        {
            "Date": "2021-10-01",
            "Tweet": "Just bought more AAPL shares. Bullish on @Apple",
            "Stock Name": "AAPL",
            "User": "retail_trader",
            "Sentiment": 0.75,
            "Confidence": 0.80,
        },
    ])
    social_path = tmp_path / "social.csv"
    social.to_csv(social_path, index=False)

    # Setup mocks
    capture = []
    mock_service = make_mock_service(capture)
    monkeypatch.setattr(pipeline_module, "neo4j_service", mock_service)
    monkeypatch.setattr(pipeline_module, "STOCKS_CSV", str(prices_path))
    monkeypatch.setattr(pipeline_module, "SOCIAL_CSV", str(social_path))
    
    # Mock sentiment workflow
    async def mock_sentiment_workflow(*args, **kwargs):
        return {
            "status": "success",
            "tweets_processed": 0,
            "tweets_updated": 0,
            "errors": 0
        }
    monkeypatch.setattr(
        "app.routers.pipeline.process_missing_sentiments",
        mock_sentiment_workflow
    )

    import app.main as main
    importlib.reload(main)
    client = TestClient(main.app)

    # Call pipeline endpoint for AAPL
    resp = client.post(
        "/api/pipeline/dataset_to_graph",
        json={
            "stock": "AAPL",
            "start_date": "2021-09-30",
            "end_date": "2021-10-01",
            "chunk_size": 10,
        },
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["stock"] == "AAPL"
    assert data["prices_synced"] == 2
    assert data["tweets_imported"] == 2
    
    # Verify data structure
    stock_rows = [r for r in capture if "ticker" in r and "tweet_id" not in r]
    tweet_rows = [r for r in capture if "tweet_id" in r]
    
    assert len(stock_rows) == 2
    assert len(tweet_rows) == 2
    
    # Verify stock data calculations
    for stock_row in stock_rows:
        assert stock_row["ticker"] == "AAPL"
        assert "daily_change" in stock_row
        assert "volatility" in stock_row
        assert stock_row["daily_change"] >= 0  # Based on our test data
    
    # Verify tweet data includes extracted features
    for tweet_row in tweet_rows:
        assert tweet_row["ticker"] == "AAPL"
        assert "hashtags" in tweet_row
        assert "mentions" in tweet_row
        assert "sentiment" in tweet_row or tweet_row["sentiment"] is None


def test_pipeline_aapl_date_filtering(monkeypatch, tmp_path):
    """Test that pipeline correctly filters AAPL data by date range."""
    # Create test data spanning multiple dates
    prices = pd.DataFrame([
        {
            "Date": "2021-09-29",
            "Stock Name": "AAPL",
            "Open": 144.0,
            "High": 145.0,
            "Low": 143.5,
            "Close": 144.5,
            "Volume": 49000000
        },
        {
            "Date": "2021-09-30",
            "Stock Name": "AAPL",
            "Open": 145.0,
            "High": 146.5,
            "Low": 144.5,
            "Close": 145.5,
            "Volume": 50000000
        },
        {
            "Date": "2021-10-01",
            "Stock Name": "AAPL",
            "Open": 145.5,
            "High": 147.0,
            "Low": 145.0,
            "Close": 146.0,
            "Volume": 52000000
        },
        {
            "Date": "2021-10-02",
            "Stock Name": "AAPL",
            "Open": 146.0,
            "High": 147.5,
            "Low": 145.5,
            "Close": 147.0,
            "Volume": 51000000
        },
    ])
    prices_path = tmp_path / "prices.csv"
    prices.to_csv(prices_path, index=False)

    social = pd.DataFrame(columns=["Date", "Tweet", "Stock Name"])
    social_path = tmp_path / "social.csv"
    social.to_csv(social_path, index=False)

    # Setup mocks
    capture = []
    mock_service = make_mock_service(capture)
    monkeypatch.setattr(pipeline_module, "neo4j_service", mock_service)
    monkeypatch.setattr(pipeline_module, "STOCKS_CSV", str(prices_path))
    monkeypatch.setattr(pipeline_module, "SOCIAL_CSV", str(social_path))
    
    # Mock sentiment workflow
    async def mock_sentiment_workflow(*args, **kwargs):
        return {
            "status": "success",
            "tweets_processed": 0,
            "tweets_updated": 0,
            "errors": 0
        }
    monkeypatch.setattr(
        "app.routers.pipeline.process_missing_sentiments",
        mock_sentiment_workflow
    )

    import app.main as main
    importlib.reload(main)
    client = TestClient(main.app)

    # Call pipeline with date range that excludes first and last dates
    resp = client.post(
        "/api/pipeline/dataset_to_graph",
        json={
            "stock": "AAPL",
            "start_date": "2021-09-30",
            "end_date": "2021-10-01",
            "chunk_size": 10,
        },
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["stock"] == "AAPL"
    # Should only sync 2 records (2021-09-30 and 2021-10-01)
    assert data["prices_synced"] == 2
    
    # Verify captured dates
    captured_dates = {row["date"] for row in capture}
    assert "2021-09-30" in captured_dates
    assert "2021-10-01" in captured_dates
    assert "2021-09-29" not in captured_dates
    assert "2021-10-02" not in captured_dates

