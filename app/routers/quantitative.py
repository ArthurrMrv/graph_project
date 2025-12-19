import statistics
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from app.services.neo4j_service import neo4j_service

# pylint: disable=too-many-locals

router = APIRouter()


@router.get("/correlation/sentiment-price/{stock}")
async def sentiment_price_correlation(
    stock: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    window_days: int = Query(default=7, ge=1, le=90),  # pylint: disable=unused-argument
):
    """
    Calculate correlation between average daily sentiment and stock price changes.
    Returns Pearson correlation coefficient and daily aggregated data.

    Args:
        stock: Stock ticker symbol (e.g., 'TSLA')
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
        window_days: Rolling window size for correlation calculation (default: 7)

    Returns:
        {
            "stock": ticker,
            "correlation_coefficient": float between -1 and 1,
            "data_points": int,
            "daily_data": [{date, close_price, avg_sentiment, tweet_count}, ...]
        }
    """

    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # Query to get daily price and sentiment data
    # Optimized to use [:ON_DATE] relationship created by pipeline
    cypher = """
    MATCH (s:Stock {ticker: $ticker})-[p:PRICE_ON]->(d:TradingDay)
    WHERE d.date >= $start_date AND d.date <= $end_date
    WITH s, d, p
    ORDER BY d.date
    OPTIONAL MATCH (d)<-[:ON_DATE]-(t:Tweet)-[:DISCUSSES]->(s)
    WHERE t.sentiment IS NOT NULL
    WITH d.date AS date,
         p.close AS close_price,
         p.volume AS trading_volume,
         avg(t.sentiment) AS avg_sentiment,
         count(t) AS tweet_count
    RETURN date, close_price, trading_volume, avg_sentiment, tweet_count
    ORDER BY date
    """

    result = neo4j_service.run_query(cypher, {"ticker": stock, "start_date": start_date, "end_date": end_date})

    data = [dict(r) for r in result]

    # Calculate Pearson correlation coefficient
    correlation = None
    if len(data) >= 2:
        prices = []
        sentiments = []

        for i in range(len(data) - 1):
            if data[i]["avg_sentiment"] is not None and data[i + 1]["close_price"]:
                # Calculate percentage price change from day i to day i+1
                price_change = ((data[i + 1]["close_price"] - data[i]["close_price"]) / data[i]["close_price"]) * 100
                prices.append(price_change)
                sentiments.append(data[i]["avg_sentiment"])

        if len(prices) >= 2 and len(sentiments) >= 2:
            try:
                n = len(prices)
                mean_price = statistics.mean(prices)
                mean_sentiment = statistics.mean(sentiments)

                numerator = sum((prices[i] - mean_price) * (sentiments[i] - mean_sentiment) for i in range(n))

                price_std = statistics.stdev(prices)
                sentiment_std = statistics.stdev(sentiments)

                # Pearson correlation = covariance / (std_x * std_y)
                if price_std > 0 and sentiment_std > 0:
                    correlation = numerator / (n * price_std * sentiment_std)
            except Exception:  # pylint: disable=broad-exception-caught
                correlation = None

    return {
        "stock": stock,
        "start_date": start_date,
        "end_date": end_date,
        "correlation_coefficient": round(correlation, 4) if correlation else None,
        "data_points": len(data),
        "daily_data": data,
        "interpretation": _interpret_correlation(correlation) if correlation else "Insufficient data",
    }


def _interpret_correlation(corr: float) -> str:
    """Helper function to interpret correlation coefficient"""
    if corr >= 0.7:
        return "Strong positive correlation - sentiment strongly predicts price increases"
    if corr >= 0.3:
        return "Moderate positive correlation - sentiment somewhat predicts price increases"
    if corr >= -0.3:
        return "Weak/no correlation - sentiment does not reliably predict price movement"
    if corr >= -0.7:
        return "Moderate negative correlation - positive sentiment predicts price decreases"

    return "Strong negative correlation - sentiment inversely predicts price movement"


@router.get("/trending/stocks")
async def trending_stocks(
    window: str = Query(default="daily", pattern="^(hourly|daily|weekly)$"), limit: int = Query(default=10, ge=1, le=50)
):
    """
    Return trending stocks based on tweet volume and sentiment in a time window.

    Args:
        window: Time window - 'hourly', 'daily', or 'weekly' (default: daily)
        limit: Maximum number of trending stocks to return (default: 10, max: 50)

    Returns:
        {
            "window": time window used,
            "start_time": ISO timestamp of window start,
            "trending_stocks": [
                {
                    "ticker": stock symbol,
                    "tweet_volume": number of tweets,
                    "avg_sentiment": average sentiment score,
                    "sentiment_count": tweets with sentiment,
                    "trend_score": calculated ranking score
                },
                ...
            ]
        }
    """
    # Calculate time window
    now = datetime.now()
    if window == "hourly":
        start_time = (now - timedelta(hours=1)).isoformat()
    elif window == "daily":
        start_time = (now - timedelta(days=1)).isoformat()
    else:  # weekly
        start_time = (now - timedelta(weeks=1)).isoformat()

    cypher = """
    MATCH (t:Tweet)-[:DISCUSSES]->(s:Stock)
    WHERE t.date >= $start_time
    WITH s,
         count(t) AS tweet_volume,
         avg(CASE WHEN t.sentiment IS NOT NULL THEN t.sentiment ELSE null END) AS avg_sentiment,
         count(CASE WHEN t.sentiment IS NOT NULL THEN 1 ELSE null END) AS sentiment_count
    WHERE tweet_volume > 0
    WITH s.ticker AS ticker,
         tweet_volume,
         avg_sentiment,
         sentiment_count,
         (tweet_volume * 0.6 + coalesce(avg_sentiment, 0.5) * sentiment_count * 0.4) AS trend_score
    ORDER BY trend_score DESC
    LIMIT $limit
    RETURN ticker, tweet_volume, avg_sentiment, sentiment_count, trend_score
    """

    result = neo4j_service.run_query(cypher, {"start_time": start_time, "limit": limit})

    return {"window": window, "start_time": start_time, "trending_stocks": [dict(r) for r in result]}


@router.get("/influencers/{stock}")
async def top_influencers(stock: str, limit: int = Query(default=20, ge=1, le=100)):
    """
    Return top influencers for a specific stock based on:
    - Number of tweets about the stock
    - Network influence (INFLUENCES relationships)
    - Sentiment impact (average sentiment of their tweets)

    Args:
        stock: Stock ticker symbol (e.g., 'TSLA')
        limit: Maximum number of influencers to return (default: 20, max: 100)

    Returns:
        {
            "stock": ticker symbol,
            "top_influencers": [
                {
                    "user_id": user identifier,
                    "tweet_count": number of tweets about this stock,
                    "avg_sentiment": average sentiment of their tweets,
                    "sentiment_count": tweets with sentiment data,
                    "influence_count": number of users they influence,
                    "influence_score": calculated ranking score
                },
                ...
            ]
        }
    """
    cypher = """
    MATCH (t:Tweet)-[:DISCUSSES]->(s:Stock {ticker: $ticker})
    MATCH (t)-[:POSTED_BY]->(u:User)
    WITH u,
         count(t) AS tweet_count,
         avg(CASE WHEN t.sentiment IS NOT NULL THEN t.sentiment ELSE 0.5 END) AS avg_sentiment,
         count(CASE WHEN t.sentiment IS NOT NULL THEN 1 ELSE null END) AS sentiment_count
    OPTIONAL MATCH (u)-[:INFLUENCES]->(other:User)
    WITH u,
         tweet_count,
         avg_sentiment,
         sentiment_count,
         count(other) AS influence_count
    WITH u.user_id AS user_id,
         tweet_count,
         avg_sentiment,
         sentiment_count,
         influence_count,
         (tweet_count * 0.4 + influence_count * 0.3 + sentiment_count * 0.3) AS influence_score
    ORDER BY influence_score DESC
    LIMIT $limit
    RETURN user_id, tweet_count, avg_sentiment, sentiment_count, influence_count, influence_score
    """

    result = neo4j_service.run_query(cypher, {"ticker": stock, "limit": limit})

    return {"stock": stock, "top_influencers": [dict(r) for r in result]}


@router.get("/prediction/sentiment-based/{stock}")
async def sentiment_based_prediction(stock: str, lookback_days: int = Query(default=7, ge=1, le=30)):
    """
    Simple sentiment-based price movement prediction using recent sentiment trends.
    Returns predicted direction and confidence based on sentiment analysis.

    Args:
        stock: Stock ticker symbol (e.g., 'TSLA')
        lookback_days: Number of days to analyze (default: 7, max: 30)

    Returns:
        {
            "stock": ticker symbol,
            "lookback_days": days analyzed,
            "prediction": "bullish" | "bearish" | "neutral",
            "confidence": float between 0 and 1,
            "avg_sentiment": average sentiment score,
            "tweet_volume": total tweets analyzed,
            "sentiment_volatility": standard deviation of sentiment
        }
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    cypher = """
    MATCH (t:Tweet)-[:DISCUSSES]->(s:Stock {ticker: $ticker})
    WHERE t.date >= $start_date AND t.date <= $end_date
      AND t.sentiment IS NOT NULL
    WITH s,
         avg(t.sentiment) AS avg_sentiment,
         count(t) AS tweet_count,
         stDev(t.sentiment) AS sentiment_volatility
    RETURN avg_sentiment, tweet_count, sentiment_volatility
    """

    result = neo4j_service.run_query(cypher, {"ticker": stock, "start_date": start_date, "end_date": end_date})

    if not result or not result[0]["avg_sentiment"]:
        return {
            "stock": stock,
            "lookback_days": lookback_days,
            "prediction": "insufficient_data",
            "confidence": 0.0,
            "avg_sentiment": None,
            "tweet_volume": 0,
            "sentiment_volatility": None,
            "message": "Not enough sentiment data for prediction",
        }

    data = dict(result[0])
    avg_sentiment = data.get("avg_sentiment", 0.5)
    tweet_count = data.get("tweet_count", 0)
    sentiment_volatility = data.get("sentiment_volatility", 0) or 0

    # Prediction logic based on sentiment thresholds
    if avg_sentiment > 0.6 and tweet_count > 10:
        prediction = "bullish"

        confidence = min(0.9, avg_sentiment * (1 - min(sentiment_volatility, 0.5)))
    elif avg_sentiment < 0.4 and tweet_count > 10:
        prediction = "bearish"

        confidence = min(0.9, (1 - avg_sentiment) * (1 - min(sentiment_volatility, 0.5)))
    else:
        prediction = "neutral"
        confidence = 0.5

    return {
        "stock": stock,
        "lookback_days": lookback_days,
        "prediction": prediction,
        "confidence": round(confidence, 3),
        "avg_sentiment": round(avg_sentiment, 3),
        "tweet_volume": tweet_count,
        "sentiment_volatility": round(sentiment_volatility, 3) if sentiment_volatility else None,
        "interpretation": _interpret_prediction(prediction, confidence),
    }


def _interpret_prediction(prediction: str, confidence: float) -> str:
    """Helper function to interpret prediction results"""
    if prediction == "bullish":
        if confidence > 0.7:
            return "Strong bullish signal - high positive sentiment suggests price increase likely"

        return "Moderate bullish signal - positive sentiment but with some uncertainty"

    if prediction == "bearish":
        if confidence > 0.7:
            return "Strong bearish signal - high negative sentiment suggests price decrease likely"

        return "Moderate bearish signal - negative sentiment but with some uncertainty"

    if prediction == "neutral":
        return "Neutral signal - sentiment is mixed or inconclusive"

    return "Insufficient data for prediction"


@router.get("/volatility/social-driven")
async def social_driven_volatility(
    min_tweets: int = Query(default=50, ge=10), limit: int = Query(default=20, ge=1, le=50)
):
    """
    Identify stocks with high volatility driven by social media activity.
    Returns stocks with high sentiment variance and tweet volume.

    Volatility is calculated as: sentiment_std × sqrt(tweet_count)
    This amplifies volatility for stocks with both high variance AND high volume.

    Args:
        min_tweets: Minimum tweet threshold to consider (default: 50)
        limit: Maximum number of stocks to return (default: 20, max: 50)

    Returns:
        {
            "min_tweets_threshold": minimum tweets required,
            "volatile_stocks": [
                {
                    "ticker": stock symbol,
                    "tweet_count": total tweets,
                    "avg_sentiment": average sentiment,
                    "sentiment_std": standard deviation of sentiment,
                    "volatility_score": calculated volatility metric
                },
                ...
            ]
        }
    """
    cypher = """
    MATCH (t:Tweet)-[:DISCUSSES]->(s:Stock)
    WHERE t.sentiment IS NOT NULL
    WITH s,
         count(t) AS tweet_count,
         avg(t.sentiment) AS avg_sentiment,
         stDev(t.sentiment) AS sentiment_std
    WHERE tweet_count >= $min_tweets AND sentiment_std IS NOT NULL
    WITH s.ticker AS ticker,
         tweet_count,
         avg_sentiment,
         sentiment_std,
         (sentiment_std * sqrt(toFloat(tweet_count))) AS volatility_score
    ORDER BY volatility_score DESC
    LIMIT $limit
    RETURN ticker, tweet_count, avg_sentiment, sentiment_std, volatility_score
    """

    result = neo4j_service.run_query(cypher, {"min_tweets": min_tweets, "limit": limit})

    volatile_stocks = []
    for r in result:
        stock_data = dict(r)
        stock_data["interpretation"] = _interpret_volatility(stock_data["sentiment_std"], stock_data["tweet_count"])
        volatile_stocks.append(stock_data)

    return {"min_tweets_threshold": min_tweets, "volatile_stocks": volatile_stocks}


def _interpret_volatility(sentiment_std: float, tweet_count: int) -> str:
    """Helper function to interpret volatility metrics"""
    if sentiment_std > 0.3:
        return f"Very high volatility - sentiment is highly unpredictable ({tweet_count} tweets)"
    if sentiment_std > 0.2:
        return f"High volatility - sentiment varies significantly ({tweet_count} tweets)"
    if sentiment_std > 0.1:
        return f"Moderate volatility - some sentiment variation ({tweet_count} tweets)"

    return f"Low volatility - sentiment is relatively stable ({tweet_count} tweets)"
