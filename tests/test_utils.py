import os
import pytest
import pandas as pd
from app.utils.data_quality import check_prices, check_social

@pytest.fixture
def temp_csv(tmp_path):
    def _create_csv(filename, data):
        path = tmp_path / filename
        pd.DataFrame(data).to_csv(path, index=False)
        return str(path)
    return _create_csv

def test_check_prices_valid(temp_csv):
    data = {
        "Date": ["2023-01-01", "2023-01-02"],
        "Stock Name": ["TSLA", "TSLA"],
        "Open": [100, 101],
        "High": [105, 106],
        "Low": [95, 96],
        "Close": [102, 103],
        "Volume": [1000, 1100]
    }
    path = temp_csv("prices.csv", data)
    report = check_prices(path)
    assert report["status"] == "ok"
    assert report["rows"] == 2
    assert report["invalid_dates"] == 0
    assert report["bad_close"] == 0

def test_check_prices_missing_columns(temp_csv):
    data = {"Date": ["2023-01-01"]}
    path = temp_csv("prices_missing.csv", data)
    report = check_prices(path)
    assert report["status"] == "missing_columns"
    assert "Stock Name" in report["missing_columns"]

def test_check_prices_invalid_data(temp_csv):
    data = {
        "Date": ["invalid", "2023-01-02"],
        "Stock Name": ["TSLA", "TSLA"],
        "Close": [-1, 103],
        "Volume": [-10, 1100]
    }
    path = temp_csv("prices_bad.csv", data)
    report = check_prices(path)
    assert report["invalid_dates"] == 1
    assert report["bad_close"] == 1
    assert report["bad_volume"] == 1

def test_check_prices_file_not_found():
    report = check_prices("non_existent.csv")
    assert report["status"] == "error"

def test_check_social_valid(temp_csv):
    data = {
        "Date": ["2023-01-01 10:00:00", "2023-01-01 11:00:00"],
        "Tweet": ["Buy $TSLA", "Hold $TSLA"],
        "Stock Name": ["TSLA", "TSLA"]
    }
    path = temp_csv("social.csv", data)
    report = check_social(path)
    assert report["status"] == "ok"
    assert report["rows"] == 2
    assert report["null_tweet"] == 0

def test_check_social_duplicates(temp_csv):
    data = {
        "Date": ["2023-01-01", "2023-01-01"],
        "Tweet": ["Same tweet", "Same tweet"],
        "Stock Name": ["TSLA", "TSLA"]
    }
    path = temp_csv("social_dup.csv", data)
    report = check_social(path)
    assert report["duplicate_text_per_day"] == 1

def test_check_social_missing_columns(temp_csv):
    data = {"Tweet": ["Hello"]}
    path = temp_csv("social_missing.csv", data)
    report = check_social(path)
    assert report["status"] == "missing_columns"

def test_check_social_file_not_found():
    report = check_social("non_existent.csv")
    assert report["status"] == "error"
