"""
Simple data quality checks for the CSV sources before ingestion.
Run directly:
  python -m app.utils.data_quality --prices "data/Stock Tweets Sentiment Analysis/stock_yfinance_data.csv" \
                                   --social "data/Stock Tweets Sentiment Analysis/stock_tweets.csv"
"""

import argparse
import os
from typing import Dict, Any, List

import pandas as pd


PRICES_DEFAULT = "data/Stock Tweets Sentiment Analysis/stock_yfinance_data.csv"
SOCIAL_DEFAULT = "data/Stock Tweets Sentiment Analysis/stock_tweets.csv"


def _check_required_columns(df: pd.DataFrame, required: List[str]) -> List[str]:
    missing = [c for c in required if c not in df.columns]
    return missing


def check_prices(csv_path: str = PRICES_DEFAULT) -> Dict[str, Any]:
    if not os.path.exists(csv_path):
        return {"status": "error", "message": f"Prices CSV not found at {csv_path}"}

    df = pd.read_csv(csv_path)
    required = ["Date", "Stock Name", "Close", "Volume"]
    missing = _check_required_columns(df, required)
    report: Dict[str, Any] = {
        "status": "ok" if not missing else "missing_columns",
        "rows": len(df),
        "missing_columns": missing,
    }
    if missing:
        return report

    # Date parsing
    parsed_dates = pd.to_datetime(df["Date"], errors="coerce")
    invalid_dates = parsed_dates.isna().sum()

    # Numeric checks
    close_bad = (df["Close"] <= 0).sum()
    volume_bad = (df["Volume"] < 0).sum()

    # Duplicate check on (Date, Stock Name)
    dup_keys = df.duplicated(subset=["Date", "Stock Name"]).sum()

    report.update(
        {
            "invalid_dates": int(invalid_dates),
            "bad_close": int(close_bad),
            "bad_volume": int(volume_bad),
            "duplicate_keys": int(dup_keys),
        }
    )
    return report


def check_social(csv_path: str = SOCIAL_DEFAULT) -> Dict[str, Any]:
    if not os.path.exists(csv_path):
        return {"status": "error", "message": f"Social CSV not found at {csv_path}"}

    df = pd.read_csv(csv_path, on_bad_lines="skip")
    required = ["Date", "Tweet", "Stock Name"]
    missing = _check_required_columns(df, required)
    report: Dict[str, Any] = {
        "status": "ok" if not missing else "missing_columns",
        "rows": len(df),
        "missing_columns": missing,
    }
    if missing:
        return report

    parsed_dates = pd.to_datetime(df["Date"], errors="coerce")
    invalid_dates = parsed_dates.isna().sum()

    # Simple null checks on critical fields
    null_tweet = df["Tweet"].isna().sum()
    null_stock = df["Stock Name"].isna().sum()

    # Duplicate tweet text + date key as a rough indicator
    df["_date"] = parsed_dates.dt.date
    dup_keys = df.duplicated(subset=["Tweet", "_date"]).sum()
    df.drop(columns=["_date"], inplace=True)

    report.update(
        {
            "invalid_dates": int(invalid_dates),
            "null_tweet": int(null_tweet),
            "null_stock": int(null_stock),
            "duplicate_text_per_day": int(dup_keys),
        }
    )
    return report


def main():
    parser = argparse.ArgumentParser(description="Run data quality checks on CSV inputs.")
    parser.add_argument("--prices", default=PRICES_DEFAULT, help="Path to prices CSV")
    parser.add_argument("--social", default=SOCIAL_DEFAULT, help="Path to social/tweets CSV")
    args = parser.parse_args()

    prices_report = check_prices(args.prices)
    social_report = check_social(args.social)

    print("Prices CSV report:")
    print(prices_report)
    print("\nSocial CSV report:")
    print(social_report)


if __name__ == "__main__":
    main()
