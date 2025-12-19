# Stock Sentiment Graph API

<div align="center">
  <img src="img/cover.png" alt="Cover" width="60%">
</div>

FastAPI service that loads stock price data, social tweets, and AI-generated sentiment scores into a Neo4j knowledge graph for analysis. The API exposes endpoints to import tweets, sync historical OHLC data, and analyze sentiment using **Hugging Face (FinBERT)**.

[![GitHub](https://img.shields.io/badge/GitHub-Repo-black?logo=github)](https://github.com/ArthurrMrv/graph_project.git)

<div align="center">
  <img src="img/contributor.png" alt="contributors" width="60%">
</div>

## Graph Model

The schema is dynamic based on your dataset richness.

### Core Schema (Always created)
Standard financial and social graph structure.
- **`Stock`** `{ ticker }`
- **`TradingDay`** `{ date }`
- **`Tweet`** `{ id, text, date, sentiment (float), confidence (float) }`
- **`HashTag`** `{ tag }`
- `(:Stock)-[:PRICE_ON { close, volume, daily_change, volatility }]->(:TradingDay)`
- `(:Tweet)-[:DISCUSSES]->(:Stock)`
- `(:Tweet)-[:ON_DATE]->(:TradingDay)`
- `(:Tweet)-[:TAGGED_WITH]->(:HashTag)`

### Extended Schema (Optional)
If your dataset includes `User`, `Topic`, or `EventId` columns, the pipeline automatically upgrades the graph:
- **`User`** `{ user_id }` linked via `[:POSTED_BY]`
- **`Topic`** `{ name }` linked via `[:MENTIONS]`
- **`NewsEvent`** `{ event_id }` linked via `[:REFERENCES]`

## Project Structure

```
graph_project/
├── app/
│   ├── main.py                # FastAPI entrypoint
│   ├── config.py              # Env vars
│   ├── routers/
│   │   ├── pipeline.py        # UNIFIED INGESTION (Dataset -> Graph)
│   │   ├── analytics.py       # Graph Algos (Communities, Influence)
│   │   ├── sentiment.py       # On-demand Sentiment (Hugging Face)
│   │   └── quantitative.py    # Quant analysis (Correlations, Volatility)
│   └── services/
│       ├── neo4j_service.py   # Neo4j Driver
│       └── huggingface_service.py
├── data/                      # CSV Datasets
├── docker-compose.yml         # Neo4j Container
├── Makefile                   # Automation
└── tests/                     # Pytest Suite
```

## Setup & Run (using Makefile)

We have a `Makefile` to simplify all common tasks.

### 1. Installation
Creates a virtual environment (`graph_env`) and installs dependencies.
```bash
make install
```

### 2. Environment Variables
Create a `.env` file for your credentials:
```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
# HF_TOKEN=hf_... (Optional: for Hugging Face API rate limits)
```

### 3. Start Neo4j (Docker)
```bash
make up
```
*Wait a few seconds for the database to start.*

### 4. Run API Server
```bash
make run
```
Access docs at: `http://localhost:8000/docs`

## Testing & Quality

We prioritize high code quality (Pylint 10/10) and robust testing.

### 1. Unified Quality Check (Recommended)
Run all tests (Unit + Integration) and Pylint in one go using our portable script:
```bash
./scripts/verify_quality.sh
```
*Note: Integration tests will automatically skip if Neo4j is not running.*

### 2. Dockerized Testing (Full Isolation)
To run the entire verification pipeline (including Integration tests with a real Neo4j DB) in a clean container:
```bash
docker compose -f docker-compose.test.yml up --build --exit-code-from tester
docker compose -f docker-compose.test.yml down -v
```

### 3. Makefile Commands
```bash
make test           # Unit tests (Mocked)
make test-integration # Integration tests (Local Neo4j)
make docker-test    # Everything inside Docker (Tests + Pylint)
make verify         # Run ./scripts/verify_quality.sh
make lint           # Check code quality (Pylint 10/10)
make ingest-demo    # Load sample Tesla data to the unified pipeline
```


## Ingestion (One-Shot)
Run the full ingestion pipeline (stocks + tweets) for a specific ticker:
```bash
curl -X POST "http://localhost:8000/api/pipeline/dataset_to_graph" \
  -H "Content-Type: application/json" \
  -d '{
    "stock": "TSLA",
    "start_date": "2021-09-30",
    "end_date": "2022-09-30"
  }'
```

## Quantitative Features

- **Correlation**: `GET /api/correlation/sentiment-price/{stock}` (Pearson r)
- **Trending**: `GET /api/trending/stocks` (Volume + Sentiment score)
- **Influencers**: `GET /api/influencers/{stock}` (Network impact)
- **Prediction**: `GET /api/prediction/sentiment-based/{stock}` (Bull/Bear based on sentiment trends)
- **Volatility**: `GET /api/volatility/social-driven` (Sentiment variance)

<div style="display: flex; gap: 10px;">
  <img src="img/end1.jpeg" alt="meme1" width="50%">
  <img src="img/end2.jpeg" alt="meme2" width="50%">
</div>