import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import sentiment, analytics, quantitative, pipeline

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("graph_app")


app = FastAPI(title="Stock Sentiment Graph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(ingestion.router, prefix="/api", tags=["Ingestion"]) -> Removed
app.include_router(sentiment.router, prefix="/api/sentiment", tags=["Sentiment"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["Pipeline"])
app.include_router(quantitative.router, prefix="/api", tags=["Quantitative Analysis"])


@app.get("/")
def read_root():
    return {"message": "Stock Sentiment Graph API is running"}
