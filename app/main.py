from fastapi import FastAPI
from app.routers import sentiment, analytics, ingestion

app = FastAPI(title="Stock Sentiment Graph API")

app.include_router(ingestion.router, prefix="/api", tags=["Ingestion"])
app.include_router(sentiment.router, prefix="/api/sentiment", tags=["Sentiment"])
app.include_router(analytics.router, prefix="/api", tags=["Analytics"])

@app.get("/")
def read_root():
    return {"message": "Stock Sentiment Graph API is running"}
