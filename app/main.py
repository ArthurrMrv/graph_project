from fastapi import FastAPI
from app.routers import sentiment, analytics, ingestion, quantitative, pipeline

app = FastAPI(title="Stock Sentiment Graph API")

app.include_router(ingestion.router, prefix="/api", tags=["Ingestion"])
app.include_router(sentiment.router, prefix="/api/sentiment", tags=["Sentiment"])
app.include_router(analytics.router, prefix="/api", tags=["Analytics"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["Pipeline"])
app.include_router(quantitative.router, prefix="/api", tags=["Quantitative Analysis"])

@app.get("/")
def read_root():
    return {"message": "Stock Sentiment Graph API is running"}
