from fastapi import APIRouter
from typing import List, Dict, Any
from app.services.neo4j_service import neo4j_service

router = APIRouter()


@router.get("/network/influence/{user_id}")
async def network_influence(user_id: str, limit: int = 20):
    """
    Return the top influencers near a user based on out-degree in a local ego graph.
    """
    cypher = """
    MATCH (u:User {user_id: $user_id})
    CALL {
      WITH u
      MATCH (u)-[:INFLUENCES*1..2]->(v:User)
      RETURN collect(DISTINCT v) AS neigh
    }
    WITH neigh
    UNWIND neigh AS v
    MATCH (v)-[r:INFLUENCES]->(w:User)
    WITH DISTINCT v, count(r) AS out_deg
    ORDER BY out_deg DESC
    LIMIT $limit
    RETURN v.user_id AS user_id, out_deg
    """
    result = neo4j_service.run_query(cypher, {"user_id": user_id, "limit": limit})
    return {"user": user_id, "top_influencers": [dict(r) for r in result]}


@router.get("/cascade/sentiment/{tweet_id}")
async def cascade_sentiment(tweet_id: str, depth: int = 3):
    """
    Explore a cascade of references (REFERENCES->Tweet) and compute simple sentiment stats downstream.
    """
    depth = max(1, min(depth, 5))
    cypher = """
    MATCH (t:Tweet {id: $tweet_id})
    OPTIONAL MATCH path = (t)<-[:REFERENCES*1..$depth]-(child:Tweet)
    WITH collect(DISTINCT child) AS tweets, t
    WITH tweets + t AS allTweets
    UNWIND allTweets AS tw
    WITH tw WHERE exists(tw.sentiment)
    RETURN count(tw) AS n, avg(tw.sentiment) AS avg_sentiment, avg(tw.confidence) AS avg_confidence
    """
    result = neo4j_service.run_query(cypher, {"tweet_id": tweet_id, "depth": depth})
    stats = dict(result[0]) if result else {"n": 0, "avg_sentiment": None, "avg_confidence": None}
    return {"tweet_id": tweet_id, "depth": depth, "stats": stats}


@router.get("/clusters/stocks")
async def clusters_stocks(limit: int = 10):
    """
    Simplified example: return hashtag co-occurrences between stocks as a light clustering proxy.
    """
    cypher = """
    MATCH (s:Stock)<-[:DISCUSSES]-(t:Tweet)-[:TAGGED_WITH]->(h:HashTag)
    WITH s, h, count(*) AS freq
    MATCH (s2:Stock)<-[:DISCUSSES]-(t2:Tweet)-[:TAGGED_WITH]->(h)
    WHERE s <> s2
    WITH s.ticker AS a, s2.ticker AS b, sum(freq) AS score
    ORDER BY score DESC
    LIMIT $limit
    RETURN a, b, score
    """
    result = neo4j_service.run_query(cypher, {"limit": limit})
    return {"clusters": [dict(r) for r in result]}


@router.get("/timeline/events/{stock}")
async def timeline_events(stock: str, limit: int = 50):
    """
    Return events linked to a ticker, ordered by date when available.
    """
    cypher = """
    MATCH (s:Stock {ticker: $ticker})<-[:DISCUSSES]-(t:Tweet)-[:REFERENCES]->(n:NewsEvent)
    WITH n, count(t) AS mentions
    RETURN n.event_id AS event_id, n.title AS title, n.published_at AS published_at, mentions
    ORDER BY mentions DESC, n.published_at DESC
    LIMIT $limit
    """
    result = neo4j_service.run_query(cypher, {"ticker": stock, "limit": limit})
    return {"stock": stock, "events": [dict(r) for r in result]}


@router.get("/gds/influence/global")
async def gds_global_influence(limit: int = 20):
    """
    Use Neo4j GDS to compute global PageRank on the user influence graph.
    Requires the Graph Data Science plugin.
    """
    cypher = """
    CALL gds.graph.project(
      'userInfluence',
      'User',
      {
        INFLUENCES: {
          type: 'INFLUENCES',
          orientation: 'NATURAL'
        }
      }
    )
    YIELD graphName
    CALL gds.pageRank.stream(graphName)
    YIELD nodeId, score
    WITH gds.util.asNode(nodeId) AS u, score
    RETURN u.user_id AS user_id, score
    ORDER BY score DESC
    LIMIT $limit
    """
    result = neo4j_service.run_query(cypher, {"limit": limit})
    return {"algorithm": "gds.pageRank", "top_users": [dict(r) for r in result]}


@router.get("/gds/communities/stocks")
async def gds_stock_communities():
    """
    Use GDS Louvain to detect stock communities on a simplified co-mention graph.
    """
    cypher = """
    CALL gds.graph.project.cypher(
      'stockCoMention',
      'MATCH (s:Stock) RETURN id(s) AS id',
      'MATCH (s1:Stock)<-[:DISCUSSES]-(t:Tweet)-[:DISCUSSES]->(s2:Stock) WHERE id(s1) < id(s2) RETURN id(s1) AS source, id(s2) AS target, count(t) AS weight'
    )
    YIELD graphName
    CALL gds.louvain.stream(graphName, { relationshipWeightProperty: 'weight' })
    YIELD nodeId, communityId
    WITH gds.util.asNode(nodeId) AS s, communityId
    RETURN s.ticker AS ticker, communityId
    ORDER BY communityId, ticker
    """

    # Check if graph exists and drop it to ensure fresh projection
    neo4j_service.run_query("CALL gds.graph.drop('stockCoMention', false)")

    result = neo4j_service.run_query(cypher)
    return {"algorithm": "gds.louvain", "stocks": [dict(r) for r in result]}


@router.get("/gds/similarity/stocks/{ticker}")
async def gds_stock_similarity(ticker: str, k: int = 10):
    """
    Use GDS Node Similarity on a stock graph to return the most similar tickers.
    The GDS projection 'stockSimilarity' must exist beforehand.
    """
    cypher = """
    CALL gds.nodeSimilarity.stream('stockSimilarity')
    YIELD node1, node2, similarity
    WITH gds.util.asNode(node1) AS s1, gds.util.asNode(node2) AS s2, similarity
    WHERE s1.ticker = $ticker
    RETURN s2.ticker AS similar_ticker, similarity
    ORDER BY similarity DESC
    LIMIT $k
    """
    result = neo4j_service.run_query(cypher, {"ticker": ticker, "k": k})
    return {"algorithm": "gds.nodeSimilarity", "ticker": ticker, "similar": [dict(r) for r in result]}
