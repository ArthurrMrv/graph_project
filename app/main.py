from fastapi import FastAPI
from app.routers import social, stocks, sentiment

app = FastAPI(title="Stock Sentiment Graph API")

app.include_router(social.router, prefix="/api/social", tags=["Social"])
app.include_router(stocks.router, prefix="/api/stocks", tags=["Stocks"])
app.include_router(sentiment.router, prefix="/api/sentiment", tags=["Sentiment"])

@app.get("/")
def read_root():
    return {"message": "Stock Sentiment Graph API is running"}
