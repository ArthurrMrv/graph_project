import pytest
from unittest.mock import patch, MagicMock
from app.services.huggingface_service import HuggingFaceService

@pytest.fixture
def mock_inference_client():
    with patch("app.services.huggingface_service.InferenceClient") as mock:
        yield mock

def test_analyze_sentiment_success(mock_inference_client):
    mock_instance = mock_inference_client.return_value
    mock_instance.text_classification.return_value = [
        {"label": "positive", "score": 0.9}
    ]
    
    service = HuggingFaceService(api_key="test_key")
    result = service.analyze_sentiment("I love this stock!")
    
    assert result["sentiment"] == 1
    assert result["confidence"] == 0.9

def test_analyze_sentiment_fallback(mock_inference_client):
    mock_instance = mock_inference_client.return_value
    mock_instance.text_classification.side_effect = Exception("API Down")
    
    service = HuggingFaceService(api_key="test_key")
    result = service.analyze_sentiment("I love this stock!")
    
    assert result["sentiment"] == 0
    assert result["confidence"] == 0.0

def test_batch_analyze_sentiment_success(mock_inference_client):
    mock_instance = mock_inference_client.return_value
    # Mocking batch response format
    mock_instance.text_classification.return_value = [
        [{"label": "positive", "score": 0.9}],
        [{"label": "negative", "score": 0.1}]
    ]
    
    service = HuggingFaceService(api_key="test_key")
    results = service.batch_analyze_sentiment(["good", "bad"])
    
    assert len(results) == 2
    assert results[0]["sentiment"] == 1
    assert results[1]["sentiment"] == 0

def test_batch_analyze_sentiment_fallback_to_individual(mock_inference_client):
    mock_instance = mock_inference_client.return_value
    # First call (batch) fails with TypeError (a common way to trigger fallback in our code)
    # Actually our code catches TypeError/ValueError/AttributeError for fallback
    mock_instance.text_classification.side_effect = [
        TypeError("Batch not supported"), # Batch call
        [{"label": "positive", "score": 0.9}], # Individual call 1
        [{"label": "negative", "score": 0.1}]  # Individual call 2
    ]
    
    service = HuggingFaceService(api_key="test_key")
    results = service.batch_analyze_sentiment(["good", "bad"])
    
    assert len(results) == 2
    assert results[0]["sentiment"] == 1
    assert results[1]["sentiment"] == 0

def test_batch_analyze_sentiment_empty(mock_inference_client):
    service = HuggingFaceService(api_key="test_key")
    results = service.batch_analyze_sentiment([])
    assert results == []

def test_process_single_result_low_confidence(mock_inference_client):
    service = HuggingFaceService(api_key="test_key")
    # positive but < 0.5 confidence -> sentiment 0
    result = service._process_single_result([{"label": "positive", "score": 0.4}])
    assert result["sentiment"] == 0
    assert result["confidence"] == 0.4

def test_hf_service_init_env(mock_inference_client):
    with patch("os.getenv", return_value="env_key"):
        service = HuggingFaceService()
        assert service.api_key == "env_key"

def test_hf_service_init_error():
    with patch("os.getenv", return_value=None):
        with pytest.raises(ValueError):
            HuggingFaceService()

def test_hf_service_result_with_to_dict(mock_inference_client):
    mock_instance = mock_inference_client.return_value
    
    # Mocking an object with to_dict()
    mock_result_obj = MagicMock()
    mock_result_obj.to_dict.return_value = {"label": "positive", "score": 0.9}
    mock_instance.text_classification.return_value = [mock_result_obj]
    
    service = HuggingFaceService(api_key="test_key")
    # This triggers the path where we call to_dict() in batch_analyze_sentiment
    results = service.batch_analyze_sentiment(["text"])
    assert results[0]["sentiment"] == 1

# --- Neo4jService Tests ---

@patch("app.services.neo4j_service.GraphDatabase.driver")
def test_neo4j_service_init(mock_driver):
    from app.services.neo4j_service import Neo4jService
    service = Neo4jService()
    assert mock_driver.called

@patch("app.services.neo4j_service.neo4j_service.driver")
def test_neo4j_service_run_query(mock_driver):
    from app.services.neo4j_service import neo4j_service
    mock_session = mock_driver.session.return_value.__enter__.return_value
    mock_session.run.return_value = [{"a": 1}]
    
    result = neo4j_service.run_query("MATCH (n) RETURN n")
    assert result == [{"a": 1}]

@patch("app.services.neo4j_service.neo4j_service.driver")
def test_neo4j_service_close(mock_driver):
    from app.services.neo4j_service import neo4j_service
    neo4j_service.close()
    assert mock_driver.close.called

# --- Sentiment Workflow Tests ---

@pytest.mark.asyncio
@patch("app.services.sentiment_workflow.get_hf_service")
@patch("app.services.sentiment_workflow.neo4j_service.run_query")
async def test_process_missing_sentiments_hf_init_error(mock_run, mock_get_hf):
    from app.services.sentiment_workflow import process_missing_sentiments
    mock_get_hf.side_effect = Exception("HF Init Failed")
    
    result = await process_missing_sentiments(api_key="bad_key")
    assert result["status"] == "error"
    assert "Failed to initialize HuggingFace service" in result["message"]

@pytest.mark.asyncio
@patch("app.services.sentiment_workflow.get_hf_service")
@patch("app.services.sentiment_workflow.neo4j_service.run_query")
async def test_process_missing_sentiments_fetch_error(mock_run, mock_get_hf):
    from app.services.sentiment_workflow import process_missing_sentiments
    mock_get_hf.return_value = MagicMock()
    mock_run.side_effect = Exception("Neo4j Fetch Error")
    
    result = await process_missing_sentiments()
    assert result["status"] == "error"
    assert "Error fetching tweets" in result["message"]

@pytest.mark.asyncio
@patch("app.services.sentiment_workflow.get_hf_service")
@patch("app.services.sentiment_workflow.neo4j_service.run_query")
async def test_process_missing_sentiments_date_parsing_logic(mock_run, mock_get_hf):
    from app.services.sentiment_workflow import process_missing_sentiments
    mock_hf = mock_get_hf.return_value
    mock_hf.batch_analyze_sentiment.return_value = []
    # Mock at least one tweet to reach the final return
    mock_run.return_value = [{"id": "t1", "text": "sample"}]
    
    # Test date inclusion logic
    result = await process_missing_sentiments(start_date="2023-01-01", end_date="2023-01-02")
    assert result["status"] == "success"
    # Check if end_date was appended with time
    assert "2023-01-02T23:59:59" in result["debug_params"]["end_date"]

@pytest.mark.asyncio
@patch("app.services.sentiment_workflow.get_hf_service")
@patch("app.services.sentiment_workflow.neo4j_service.run_query")
async def test_process_missing_sentiments_end_date_with_time(mock_run, mock_get_hf):
    from app.services.sentiment_workflow import process_missing_sentiments
    mock_get_hf.return_value = MagicMock()
    mock_run.return_value = [{"id": "t1", "text": "sample"}]
    # Dates with "T" should not be modified
    result = await process_missing_sentiments(end_date="2023-01-02T12:00:00")
    assert result["debug_params"]["end_date"] == "2023-01-02T12:00:00"

@pytest.mark.asyncio
@patch("app.services.sentiment_workflow.get_hf_service")
@patch("app.services.sentiment_workflow.neo4j_service.run_query")
async def test_process_missing_sentiments_batch_update_error(mock_run, mock_get_hf):
    from app.services.sentiment_workflow import process_missing_sentiments
    mock_hf = mock_get_hf.return_value
    mock_hf.batch_analyze_sentiment.return_value = [{"sentiment": 1, "confidence": 0.9}]
    
    # First call: Fetch tweets
    # Second call: Update (fails)
    mock_run.side_effect = [
        [{"id": "t1", "text": "sample"}], # Fetch
        Exception("Update failed") # Update
    ]
    
    result = await process_missing_sentiments(batch_size=1)
    assert result["status"] == "success"
    assert result["errors"] == 1

@patch("app.services.neo4j_service.neo4j_service.driver")
def test_neo4j_service_create_constraints(mock_driver):
    from app.services.neo4j_service import neo4j_service
    mock_session = mock_driver.session.return_value.__enter__.return_value
    
    neo4j_service.create_constraints()
    assert mock_session.run.call_count > 0

@pytest.mark.asyncio
@patch("app.services.sentiment_workflow.get_hf_service")
@patch("app.services.sentiment_workflow.neo4j_service.run_query")
async def test_process_missing_sentiments_individual_fallback(mock_run, mock_get_hf):
    from app.services.sentiment_workflow import process_missing_sentiments
    mock_hf = mock_get_hf.return_value
    # Force batch failure
    mock_hf.batch_analyze_sentiment.side_effect = Exception("Batch Error")
    # Mock individual success
    mock_hf.analyze_sentiment.return_value = {"sentiment": 1, "confidence": 0.9}
    
    # 1. Fetch
    # 2. Individual Update
    mock_run.side_effect = [
        [{"id": "t1", "text": "sample"}], # Fetch
        [{"updated": 1}] # Update
    ]
    
    result = await process_missing_sentiments(batch_size=1)
    assert result["status"] == "success"
    assert result["tweets_updated"] == 1

def test_hf_service_unexpected_format(mock_inference_client):
    service = HuggingFaceService(api_key="test_key")
    # Unexpected outer result type (not list)
    assert service._process_single_result("not a list") == {"sentiment": 0, "confidence": 0.0}

def test_hf_service_get_hf_service_cache():
    from app.services.huggingface_service import get_hf_service
    with patch("app.services.huggingface_service.HuggingFaceService") as mock_class:
        # Each call returns a new mock
        mock_class.side_effect = [MagicMock(), MagicMock()]
        with patch("os.getenv", return_value="some_key"):
            # Clear cache if needed (it's a global in the module, might stay between tests)
            # But let's assume it starts fresh or we test logic
            s1 = get_hf_service()
            s2 = get_hf_service()
            assert s1 == s2
            assert mock_class.call_count == 1
            # Test with explicit key (should create new)
            s3 = get_hf_service(api_key="new_key")
            assert s3 != s1
            assert mock_class.call_count == 2

@pytest.mark.asyncio
@patch("app.services.sentiment_workflow.get_hf_service")
@patch("app.services.sentiment_workflow.neo4j_service.run_query")
async def test_process_missing_sentiments_no_tweets(mock_run, mock_get_hf):
    from app.services.sentiment_workflow import process_missing_sentiments
    mock_get_hf.return_value = MagicMock()
    mock_run.return_value = [] # No tweets
    result = await process_missing_sentiments()
    assert result["status"] == "success"
    assert "No tweets found" in result["message"]

@pytest.mark.asyncio
@patch("app.services.sentiment_workflow.get_hf_service")
@patch("app.services.sentiment_workflow.neo4j_service.run_query")
async def test_process_missing_sentiments_with_limit_and_missing_text(mock_run, mock_get_hf):
    from app.services.sentiment_workflow import process_missing_sentiments
    mock_hf = mock_get_hf.return_value
    mock_hf.batch_analyze_sentiment.return_value = []
    
    # 1 tweet with text, 1 without
    mock_run.return_value = [
        {"id": "t1", "text": "valid"},
        {"id": "t2", "text": ""}
    ]
    
    result = await process_missing_sentiments(limit=10)
    assert result["errors"] == 1 # The one without text
    assert result["status"] == "success"

@pytest.mark.asyncio
@patch("app.services.sentiment_workflow.get_hf_service")
@patch("app.services.sentiment_workflow.neo4j_service.run_query")
async def test_process_missing_sentiments_individual_error(mock_run, mock_get_hf):
    from app.services.sentiment_workflow import process_missing_sentiments
    mock_hf = mock_get_hf.return_value
    mock_hf.batch_analyze_sentiment.side_effect = Exception("Batch Error")
    mock_hf.analyze_sentiment.side_effect = Exception("Individual Error")
    
    mock_run.side_effect = [
        [{"id": "t1", "text": "sample"}], # Fetch
        Exception("Update error") # Should not be hit but good practice
    ]
    
    result = await process_missing_sentiments()
    assert result["errors"] == 1

def test_hf_service_batch_unexpected_item_format(mock_inference_client):
    mock_instance = mock_inference_client.return_value
    # Mocking something that has neither to_dict nor dict nor is a dict
    mock_item = "not a dict or object"
    mock_instance.text_classification.return_value = [mock_item]
    
    service = HuggingFaceService(api_key="test_key")
    # This triggers the 'else' branch in batch result processing (line 126-127)
    results = service.batch_analyze_sentiment(["text"])
    assert results[0]["sentiment"] == 0

def test_hf_service_batch_error_complete_fallback(mock_inference_client):
    mock_instance = mock_inference_client.return_value
    # Force generic Exception for complete fallback (line 150)
    mock_instance.text_classification.side_effect = [
        Exception("Generic Failure"), # Batch call
        [{"label": "positive", "score": 0.9}] # Individual call
    ]
    
    service = HuggingFaceService(api_key="test_key")
    results = service.batch_analyze_sentiment(["text"])
    assert results[0]["sentiment"] == 1

@pytest.mark.asyncio
@patch("app.services.sentiment_workflow.get_hf_service")
@patch("app.services.sentiment_workflow.neo4j_service.run_query")
async def test_process_missing_sentiments_empty_text_list(mock_run, mock_get_hf):
    from app.services.sentiment_workflow import process_missing_sentiments
    mock_get_hf.return_value = MagicMock()
    # 1 tweet with NO text at all
    mock_run.return_value = [{"id": "t1", "text": ""}]
    result = await process_missing_sentiments()
    assert result["errors"] == 1
    assert result["tweets_processed"] == 0

@pytest.mark.asyncio
@patch("app.services.sentiment_workflow.get_hf_service")
@patch("app.services.sentiment_workflow.neo4j_service.run_query")
async def test_process_missing_sentiments_individual_fallback_missing_text(mock_run, mock_get_hf):
    from app.services.sentiment_workflow import process_missing_sentiments
    mock_hf = mock_get_hf.return_value
    mock_hf.batch_analyze_sentiment.side_effect = Exception("Batch Error")
    # Mock individual success for the fallback
    mock_hf.analyze_sentiment.return_value = {"sentiment": 1, "confidence": 0.8}
    
    # Return 1 valid, 1 missing text
    mock_run.side_effect = [
        [{"id": "t1", "text": "valid"}, {"id": "t2", "text": ""}], # Fetch
        [{"updated": 1}] # Individual Update for valid one
    ]
    
    result = await process_missing_sentiments(batch_size=1)
    assert result["errors"] == 1 # Only t2 is an error
    assert result["tweets_updated"] == 1
