from typing import Optional, List, Any, Dict
from pydantic import BaseModel


class SentimentRequest(BaseModel):
    text: str
    api_key: Optional[str] = None


class SentimentResponse(BaseModel):
    sentiment: float
    confidence: float


class StockSyncRequest(BaseModel):
    stock: str = "TSLA"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    chunk_size: int = 1000


class SocialImportRequest(BaseModel):
    stock: str = "TSLA"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    chunk_size: int = 1000


class SyncSentimentsRequest(BaseModel):
    stock: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: Optional[int] = None
    overwrite: bool = False
    batch_size: int = 50
    api_key: Optional[str] = None


class SyncSentimentsResponse(BaseModel):
    tweets_processed: int
    tweets_updated: int
    errors: int
    stock: Optional[str] = None
    date_range: Optional[Dict[str, Any]] = None


# Pipeline Models
class PipelineRequest(BaseModel):
    stock: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    chunk_size: int = 2000


class PipelineResponse(BaseModel):
    status: str
    stock: str
    prices_synced: int
    tweets_imported: int
    notes: Optional[str] = None
    sentiment_processing: Optional[Dict[str, Any]] = None


# Analytics Models
class InfluenceItem(BaseModel):
    user_id: str
    out_deg: int


class InfluenceResponse(BaseModel):
    user: str
    top_influencers: List[InfluenceItem]


class CascadeStats(BaseModel):
    n: int
    avg_sentiment: Optional[float] = None
    avg_confidence: Optional[float] = None


class SentimentCascadeResponse(BaseModel):
    tweet_id: str
    depth: int
    stats: CascadeStats


class ClusterItem(BaseModel):
    a: str
    b: str
    score: int


class StockClustersResponse(BaseModel):
    clusters: List[ClusterItem]


class TimelineEventItem(BaseModel):
    event_id: str
    title: str
    published_at: Optional[str] = None
    mentions: int


class TimelineEventsResponse(BaseModel):
    stock: str
    events: List[TimelineEventItem]


class GDSPageRankItem(BaseModel):
    user_id: str
    score: float


class GDSGlobalInfluenceResponse(BaseModel):
    algorithm: str
    top_users: List[GDSPageRankItem]


class GDSLouvainItem(BaseModel):
    ticker: str
    communityId: int


class GDSStockCommunitiesResponse(BaseModel):
    algorithm: str
    stocks: List[GDSLouvainItem]


class GDSSimilarityItem(BaseModel):
    similar_ticker: str
    similarity: float


class GDSStockSimilarityResponse(BaseModel):
    algorithm: str
    ticker: str
    similar: List[GDSSimilarityItem]


# Quantitative Models
class DailyDataItem(BaseModel):
    date: str
    close_price: Optional[float] = None
    trading_volume: Optional[int] = None
    avg_sentiment: Optional[float] = None
    tweet_count: int


class CorrelationResponse(BaseModel):
    stock: str
    start_date: str
    end_date: str
    correlation_coefficient: Optional[float] = None
    data_points: int
    daily_data: List[DailyDataItem]
    interpretation: str


class TrendingStockItem(BaseModel):
    ticker: str
    tweet_volume: int
    avg_sentiment: Optional[float] = None
    sentiment_count: int
    trend_score: float


class TrendingStocksResponse(BaseModel):
    window: str
    start_time: str
    trending_stocks: List[TrendingStockItem]


class InfluencerDetailItem(BaseModel):
    user_id: str
    tweet_count: int
    avg_sentiment: float
    sentiment_count: int
    influence_count: int
    influence_score: float


class TopInfluencersResponse(BaseModel):
    stock: str
    top_influencers: List[InfluencerDetailItem]


class PredictionResponse(BaseModel):
    stock: str
    lookback_days: int
    prediction: str
    confidence: float
    avg_sentiment: Optional[float] = None
    tweet_volume: int
    sentiment_volatility: Optional[float] = None
    interpretation: Optional[str] = None
    message: Optional[str] = None


class VolatileStockItem(BaseModel):
    ticker: str
    tweet_count: int
    avg_sentiment: float
    sentiment_std: float
    volatility_score: float
    interpretation: str


class VolatilityResponse(BaseModel):
    min_tweets_threshold: int
    volatile_stocks: List[VolatileStockItem]
