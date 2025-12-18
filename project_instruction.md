9. Social Media Sentiment & Stock Market Correlation Analysis
Use Case: Quantitative analysis of how social media sentiment correlates with stock price movements

Graph Model: Stock, Tweet/Post, User, HashTag, Topic, TradingDay, NewsEvent; relationships: MENTIONS, POSTED_BY, TAGGED_WITH, DISCUSSES, INFLUENCES, CORRELATES_WITH, PRICE_ON, AFFECTS, PRECEDES
API Features:
Data ingestion
e.g. POST /api/social/import (tweets/posts with sentiment)
e.g. POST /api/stocks/sync (sync prices/indicators)
e.g. POST /api/sentiment/analyze (analyze raw text)
Quantitative analysis
e.g. GET /api/correlation/sentiment-price/{stock}
e.g. GET /api/trending/stocks?window=daily
e.g. GET /api/influencers/{stock}
e.g. GET /api/prediction/sentiment-based/{stock}
e.g. GET /api/volatility/social-driven
Graph analytics
e.g. GET /api/network/influence/{user}
e.g. GET /api/cascade/sentiment/{tweet_id}
e.g. GET /api/clusters/stocks
e.g. GET /api/timeline/events/{stock}
Visualization helpers
e.g. GET /api/dashboard/sentiment-vs-price/{stock}
e.g. GET /api/heatmap/correlation-matrix
e.g. GET /api/network/visualization/{stock}
Difficulty: 3 for the braves 🥷
Data Sources
Twitter/Reddit Stock Sentiment Datasets

Stock Tweets Dataset (Kaggle): https://www.kaggle.com/datasets/equinxx/stock-tweets-for-sentiment-analysis-and-prediction
80,000+ tweets with stock ticker symbols, timestamps, engagement metrics
WallStreetBets Reddit Dataset (Kaggle): https://www.kaggle.com/datasets/gpreda/wallstreetbets-2022
Millions of posts/comments (2012-2024) with upvotes, awards, user information
Stock Market Sentiment Dataset (Kaggle): https://www.kaggle.com/datasets/yash612/stockmarket-sentiment-dataset
5,791 labeled tweets with sentiment labels (positive/negative)
Historical Stock Price Data APIs

Yahoo Finance (yfinance library): https://github.com/ranaroussi/yfinance
Free & unlimited (unofficial but reliable)
Historical prices, real-time quotes, dividends, splits, company fundamentals