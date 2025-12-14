# Stock Sentiment Graph API

FastAPI service that loads stock price data, social tweets, and AI-generated sentiment scores into a Neo4j knowledge graph for analysis. The API exposes endpoints to import tweets, sync historical OHLC data, and call Gemini for on-demand sentiment classification.

## Project Structure

```
graph_project/
├── app/
│   ├── main.py                # FastAPI app and router wiring
│   ├── config.py              # .env-powered Neo4j settings
│   ├── models.py              # Pydantic request/response schemas
│   ├── routers/
│   │   ├── social.py          # Tweet import + hashtag extraction
│   │   ├── stocks.py          # OHLC sync into TradingDay nodes
│   │   └── sentiment.py       # Gemini-powered sentiment endpoint
│   └── services/
│       ├── neo4j_service.py   # Shared Neo4j driver + constraints
│       └── gemini_service.py  # Wrapper for google-generativeai SDK
├── data/
│   ├── Stock Tweets Sentiment Analysis/
│   │   ├── stock_tweets.csv           # Raw tweets referenced by /social
│   │   └── stock_yfinance_data.csv    # Price history referenced by /stocks
│   ├── Stock Tweets Sentiment Analysis.zip
│   └── neo4j/                         # Local Neo4j volume (when dockerized)
├── docker-compose.yml         # Neo4j 5.x w/ APOC helper
├── requirements.txt           # Python dependencies
├── verify_mvp.py              # Smoke test script using mocked services
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
   Ensure the CSV files shipped in `data/Stock Tweets Sentiment Analysis/` stay in place—`social.py` and `stocks.py` read them directly when filtering by ticker.

## Run Commands

Start the FastAPI server (reload optional during development):
```bash
uvicorn app.main:app --reload
```

Available endpoints once the server is running:
- `GET /` – health check.
- `POST /api/stocks/sync` – body `{ "stock": "TSLA" }`; upserts `Stock` and `TradingDay` nodes.
- `POST /api/social/import` – body `{ "stock": "TSLA" }`; creates `Tweet` nodes + `HashTag` relationships and links to stocks.
- `POST /api/sentiment/analyze` – body `{ "text": "...", "api_key": "<GEMINI_KEY>" }`; returns `{ sentiment, confidence }`.

Run the lightweight verification script (mocks external services) if you want to check wiring without live dependencies:
```bash
python verify_mvp.py
```

With Neo4j running and data accessible, you can now import tweets/prices and explore the resulting graph in the Neo4j Browser.

