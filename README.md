# Stock Sentiment Graph API

FastAPI service that loads stock price data, social tweets, and AI-generated sentiment scores into a Neo4j knowledge graph for analysis. The API exposes endpoints to import tweets, sync historical OHLC data, and call Gemini for on-demand sentiment classification.

## Graph Model (current)

Nodes
- `Stock { ticker }`
- `TradingDay { date }`
- `Tweet { id, text, date }`
- `HashTag { tag }`
- `User { user_id }`
- `Topic { name }`
- `NewsEvent { event_id, title?, published_at? }`
- `Factor { name }`  *(placeholder for derived signals/indicators)*

Key Relationships
- `(:Tweet)-[:DISCUSSES]->(:Stock)`
- `(:Tweet)-[:TAGGED_WITH]->(:HashTag)`
- `(:Stock)-[:PRICE_ON { close, volume }]->(:TradingDay)`
- `(:Tweet)-[:POSTED_BY]->(:User)`
- `(:Tweet)-[:MENTIONS]->(:Topic)`
- `(:Tweet)-[:REFERENCES]->(:NewsEvent)`
- `(:NewsEvent)-[:AFFECTS]->(:Stock)`
- `(:Topic)-[:CORRELATES_WITH]->(:Stock)`
- `(:User)-[:INFLUENCES]->(:User)`  *(social graph)*
- `(:Factor)-[:DERIVED_FROM]->(:TradingDay)`  *(technical/quant factors)*

Uniqueness Constraints (created at startup)
- `Tweet.id`, `Stock.ticker`, `TradingDay.date`, `HashTag.tag`, `User.user_id`, `Topic.name`, `NewsEvent.event_id`, `Factor.name`

## Project Structure

```
graph_project/
├── app/
│   ├── main.py                # FastAPI app and router wiring
│   ├── config.py              # .env-powered Neo4j settings
│   ├── models.py              # Pydantic request/response schemas
│   ├── routers/
│   │   ├── ingestion.py       # Stock + social ingestion endpoints (batch UNWIND)
│   │   ├── analytics.py       # Network/cascade/clusters + GDS endpoints
│   │   └── sentiment.py       # Gemini-powered sentiment endpoint
│   └── services/
│       ├── neo4j_service.py   # Shared Neo4j driver + constraints
│       └── gemini_service.py  # Wrapper for google-generativeai SDK
│   └── utils/
│       └── data_quality.py    # CSV quality checks (dates, nulls, duplicates)
├── data/
│   ├── Stock Tweets Sentiment Analysis/
│   │   ├── stock_tweets.csv           # Raw tweets referenced by /social
│   │   └── stock_yfinance_data.csv    # Price history referenced by /stocks
│   ├── Stock Tweets Sentiment Analysis.zip
│   └── neo4j/                         # Local Neo4j volume (when dockerized)
├── docker-compose.yml         # Neo4j 5.x with APOC + GDS + API service
├── requirements.txt           # Python dependencies
├── verify_mvp.py              # Smoke test script using mocked services
├── tests/                     # Pytest suite (mocked Neo4j/Gemini)
└── venv/                      # (Optional) local Python virtualenv
```

## Setup

1. **Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment variables**
   Create a `.env` file (loaded by `app/config.py`) for your Neo4j credentials:
   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=password
   ```
   You will also need a Google Gemini API key when calling `/api/sentiment/analyze`.

3. **Neo4j**
   The quickest way to boot a local graph database is via Docker:
   ```bash
   docker compose up -d neo4j
   ```
   The container exposes `7687` (bolt) and `7474` (browser) and persists data to `data/neo4j/`.

4. **Datasets**
   Ensure the CSV files in `data/Stock Tweets Sentiment Analysis/` stay in place—`ingestion.py` reads them directly when filtering by ticker.

## Run Commands

Start the FastAPI server (reload optional during development):
```bash
uvicorn app.main:app --reload
# or with venv
venv/bin/uvicorn app.main:app --reload
```

Available endpoints (single ingestion path via FastAPI):
- `GET /` – health check.
- `POST /api/stocks/sync` – body `{"stock": "TSLA", "start_date": "2021-09-30", "end_date": "2022-09-30", "chunk_size": 1000}` (dates/chunk optional); upserts `Stock` and `TradingDay` and creates `PRICE_ON` relationships.
- `POST /api/social/import` – body `{"stock": "TSLA", "start_date": "2021-09-30", "end_date": "2022-09-30", "chunk_size": 1000}` (dates/chunk optional); creates `Tweet`, `HashTag`, `User`, `Topic`, `NewsEvent` and relationships (`DISCUSSES`, `TAGGED_WITH`, `POSTED_BY`, `MENTIONS`, `REFERENCES`).
- `POST /api/sentiment/analyze` – body `{ "text": "...", "api_key": "<GEMINI_KEY>" }`; returns `{ sentiment, confidence }`.
- `GET /api/network/influence/{user_id}?limit=20` – top influencers in the ego graph (out-degree on `INFLUENCES`).
- `GET /api/cascade/sentiment/{tweet_id}?depth=3` – sentiment stats along a tweet reference cascade up to `depth`.
- `GET /api/clusters/stocks?limit=10` – ticker pairs correlated via hashtag co-occurrence (lightweight clustering proxy).
- `GET /api/timeline/events/{stock}?limit=50` – events referenced for a ticker, ordered by date if available.
- `GET /api/gds/influence/global` – PageRank via Neo4j GDS on the user influence graph.
- `GET /api/gds/communities/stocks` – Louvain via GDS on a co-mention stock graph.
- `GET /api/gds/similarity/stocks/{ticker}` – Node similarity via GDS for related tickers.

Quantitative Analysis endpoints:
- `GET /api/correlation/sentiment-price/{stock}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` – calculate Pearson correlation between sentiment and price changes.
- `GET /api/trending/stocks?window=daily&limit=10` – find trending stocks by tweet volume and sentiment (windows: hourly/daily/weekly).
- `GET /api/influencers/{stock}?limit=20` – top influencers for a stock ranked by tweets, network influence, and sentiment impact.
- `GET /api/prediction/sentiment-based/{stock}?lookback_days=7` – predict bullish/bearish/neutral direction based on recent sentiment trends.
- `GET /api/volatility/social-driven?min_tweets=50&limit=20` – stocks with highest social media sentiment volatility.

Run the lightweight verification script (mocks external services) if you want to check wiring without live dependencies:
```bash
python verify_mvp.py
```

With Neo4j running and data accessible, you can import tweets/prices and explore the resulting graph in the Neo4j Browser.

## Data quality checks (optional)
Run simple CSV checks before ingesting:
```bash
python -m app.utils.data_quality \
  --prices "data/Stock Tweets Sentiment Analysis/stock_yfinance_data.csv" \
  --social "data/Stock Tweets Sentiment Analysis/stock_tweets.csv"
```

## Tests
Run the mocked API tests with pytest:
```bash
pytest
```
Tests patch Neo4j/Gemini to avoid external dependencies and use temp CSVs for ingestion paths.

## Testing Quantitative Analysis Endpoints

Before testing the quantitative endpoints, you need to load Tesla data into Neo4j:

**Option A: Using curl in terminal**
```bash
# Import stock prices
curl -X POST "http://localhost:8000/api/stocks/sync" \
  -H "Content-Type: application/json" \
  -d '{"stock": "TSLA", "start_date": "2021-09-30", "end_date": "2022-09-30"}'

# Import tweets and social data
curl -X POST "http://localhost:8000/api/social/import" \
  -H "Content-Type: application/json" \
  -d '{"stock": "TSLA", "start_date": "2021-09-30", "end_date": "2022-09-30"}'
```

**Option B: Using the interactive API docs**
Navigate to `http://localhost:8000/docs` test each end points.

1. Open `http://localhost:8000/docs` in your browser
2. All endpoints are organized by tags: `Ingestion`, `Quantitative Analysis`, `Analytics`, `Sentiment`
3. For each endpoint:
   - Click to expand
   - Click "Try it out"
   - Modify parameters as needed
   - Click "Execute"
   - View response with syntax highlighting

**Example workflow in `/docs`:**
1. Navigate to **Quantitative Analysis** section
2. Test `GET /api/correlation/sentiment-price/{stock}`:
   - Set `stock` = `TSLA`
   - Set `start_date` = `2021-10-01`
   - Set `end_date` = `2022-09-30`
   - Execute and observe correlation metrics
3. Test `GET /api/trending/stocks`:
   - Set `window` = `daily`
   - Set `limit` = `10`
   - Execute to see which stocks are trending
4. Continue with other endpoints